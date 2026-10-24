"""Render RI-02-DATA audit documents from frozen evidence; no network/DB access."""
import json, xml.etree.ElementTree as ET
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[1]; DOC=ROOT/'docs'; E=DOC/'qa/ri02/data01'
def read(name):return json.loads((E/name).read_text())
def save(name,text):(DOC/name).write_text(text.strip()+'\n')
def fmt(v):
 if v is None:return 'null'
 if isinstance(v,float):return f'{v:.10g}'
 if isinstance(v,(list,dict)):return json.dumps(v,ensure_ascii=False).replace('|','\\|')
 return str(v).replace('|','\\|').replace('\n',' ')
def table(headers,rows):return '\n'.join(['| '+' | '.join(headers)+' |','|'+'---|'*len(headers)]+['| '+' | '.join(fmt(v) for v in row)+' |' for row in rows])+'\n'
symbols=read('code_symbols.json')
def ref(file,name):
 found=next(x for x in symbols if x['file']==file and x['symbol']==name)
 return f'[{file}:{found["line"]}]({ROOT/file}:{found["line"]}) `{name}`'
base=read('baseline.json'); traces=read('traces.json'); api=read('api_comparison.json'); census=read('census.json'); coverage=read('coverage.json'); sources=read('source_evidence.json')
header=f'**RI-02-CAL-01-DATA / READY FOR QA.** Дата: 24.10.2026. HEAD `{base["head"]}`. Исследуется рабочее дерево с уже существующими незакоммиченными RI/PL/UI изменениями, а не чистый HEAD. Код, настройки, сохранённые матчи и прежние отчёты не изменены.\n\n'
evidence='[Воспроизводимые свидетельства](qa/ri02/data01/) · [Матрица](RI_02_DATA_01_FIELD_MATRIX.csv) · [QA](RI_02_DATA_01_QA_REPORT.md)'
code=header+'''## Границы и источники

Изучены актуальный доступный `Downloads/Dota_Hub_Master_Plan_v0_1.md` (23.10.2026), RI-02-DIAG-01, RI-02-FIX-01, RI-04-FIX-01 и предыдущий CAL-01. Master Plan является планом: его прежние статусы не доказывают исправность. Он не изменялся.

Источник двух пилотов — PostgreSQL `matches.raw_payload` в транзакции `SET TRANSACTION READ ONLY`. Оба canonical SHA совпали с сохранёнными CAL-01 snapshots. Ещё десять матчей взяты из прежнего исследования, их наличие в рабочей БД не утверждается. Оригинальные HTTP bytes до sanitizer не сохранены: отсутствие account_id в этих snapshots нельзя объявлять отсутствием у OpenDota. Свежие матчи не запрашивались, `/request` не вызывался. Replay 120 игроков выполнен только в памяти.

```mermaid
flowchart TD
  A[Telegram /match или локальный POST analyze] --> B[MatchAnalysisService.process]
  B --> C[MatchIngestionService.ingest_match]
  C --> D{TTL cache}
  D -->|hit| E[Сохранённый sanitized snapshot]
  D -->|miss| F[mark_pending → OpenDota GET matches/id]
  F --> G[parse_match_response и sanitize]
  G --> H[save_result → matches.raw_payload JSONB]
  H --> E
  E --> I[normalize_match_snapshot в памяти]
  I --> J[Обзор / Игроки / Драфт / Индекс / Timeline]
  J --> K[match_analyses JSONB: по одной записи на секцию]
  K --> L[GET stored → DTO → project_preliminary → envelope]
```

## Функции и точки вызова

'''
entries=[
('backend/app/bot/services.py','start_request','Telegram update','service.process','команда после разрешений/лимитов'),
('backend/app/api/v1/local_alpha.py','analyze','POST local ID','service.process','loopback-only; аудит POST не вызывает'),
('backend/app/services/match_analysis.py','_process','ID, previous flow','source_digest, normalized, reports','вызван process; writes queued/running before ingestion'),
('backend/app/services/match_ingestion.py','ingest_match','ID','OpenDotaResult','process: per-ID lock, cache→pending→fetch→save'),
('backend/app/services/match_ingestion.py','_read_cache','Match.raw_payload','result or None','TTL, timezone, player_public_data_version'),
('backend/app/services/match_ingestion.py','_mark_pending','ID','pending raw placeholder','replaces previous raw via upsert_match'),
('backend/app/integrations/opendota.py','get_json','path','status/body/retry','bounded HTTP retries, JSON parsing'),
('backend/app/integrations/opendota.py','fetch_match','ID','OpenDotaResult','GET /matches/{id}'),
('backend/app/integrations/opendota.py','parse_match_response','HTTP object, time','snapshot','type/id/duration/core/arrays/team presence checks'),
('backend/app/integrations/opendota.py','_sanitize','match dict','deep copy','remove private player identifiers/chat; nickname whitespace/max80'),
('backend/app/services/match_ingestion.py','_save_result','result','JSONB snapshot/cache metadata','errors also replace raw'),
('backend/app/db/repositories.py','upsert_match','payload/status/time','Match','ON CONFLICT replace, no history'),
('backend/app/services/match_normalization.py','normalize_match_snapshot','sanitized snapshot','NormalizedMatch','summary/players/raw draft+events/derived, no DB normalized table'),
('backend/app/services/match_normalization.py','_player','one raw player','PlayerStat','rename, ranges, integers, finite stuns, estimated farm role'),
('backend/app/services/match_normalization.py','_players','players','sorted roster','unique slot 0..255, <=5 per side; does not require only standard slots'),
('backend/app/services/match_normalization.py','_draft','picks_bans','DraftRawData','source_order and source order kept; duplicates/gaps flagged'),
('backend/app/services/match_normalization.py','_events','event arrays','MatchEventRawData','deepcopy lists; only kills/buyback/purchase player logs mapped'),
('backend/app/services/match_normalization.py','_derived','players/scores','KDA and counter-ratio','round4, explicit missing/zero status'),
('backend/app/services/performance.py','participation_assessment','player/match/config','usable,raw,reason','counter arithmetic separate from suitability'),
('backend/app/services/performance.py','observed','PlayerStat','metrics','per-minute rates; original GPM/XPM; null preserved'),
('backend/app/services/performance.py','evaluate','NormalizedMatch','RuinerReport','cohorts→compare→axes→credit→coverage→index→selection'),
('backend/app/services/performance.py','compare','one observation/peer observations','bad or credit-only good','nested evaluate function; median excluding self, floors/clamp'),
('backend/app/services/performance.py','select_team','five reports','strict selection','all medium/full coverage + threshold/margin/signals'),
('backend/app/services/performance_preliminary.py','select_preliminary','same-team reports, optional leaver context','preliminary projection','production caller does not supply leaver context'),
('backend/app/services/match_analysis.py','public_base','normalized','OverviewReport/PlayersReport','catalog metadata/item details; selective public fields'),
('backend/app/services/timeline.py','analyze_timeline','normalized.raw.events','TimelineReport','times, event dedupe, provenance, coverage'),
('backend/app/services/match_analysis.py','digest','snapshot subset/config','SHA256','sorted JSON no NaN; no implementation-code digest'),
('backend/app/db/repositories.py','save_analysis','report wrapper','MatchAnalysis','upsert unique match/version; source/config metadata'),
('backend/app/api/v1/matches.py','stored','ID/section/session','JSONResponse','source digest vs flow, DTO validation, no refetch/reanalysis'),
('backend/app/services/performance_preliminary.py','project_preliminary','persisted RuinerReport','read-time projection','legacy computed; inconsistent semantic choice -> none; DB untouched'),
('backend/app/api/v1/matches.py','response','envelope/status','JSON','Cache-Control no-store; retry header'),
('backend/app/api/v1/auth.py','current_user','session token→existing user','authorized user','Telegram JWT validation + DB lookup; no per-match ownership filter'),
('backend/app/api/v1/local_alpha.py','section','loopback GET','stored(...)','same public section DTOs; generic local OpenAPI response'),
]
rows=[]
for f,n,i,o,c in entries:
 try:r=ref(f,n)
 except StopIteration:
  # Emit exact file inventory when the entry point uses a different symbol, no guessed line.
  matches=[x for x in symbols if x['file']==f]; r=f'`{f}`; see code_symbols.json ('+', '.join(x['symbol'] for x in matches if x['symbol'] not in ('__init__',))[:200]+')'
 rows.append([r,i,o,c])
code+=table(['Файл / функция','Вход','Выход','Преобразование / caller'],rows)
code+='''
## HTTP и хранение

Runtime OpenDota endpoints: `GET /api/matches/{match_id}`; дополнительно `GET /api/heroes/{hero_id}/matchups` для Draft. RI не получает benchmark, proMatches, players/history, POST parse. Предыдущий автономный CAL-01 обращался к `/publicMatches` и `/benchmarks?hero_id=...`; это исследовательский скрипт, не pipeline RI. Справочники героев/предметов/режимов/патчей читаются из закреплённых локальных JSON через player_catalog. API key опционален, передаётся Authorization, в логах/отчётах отсутствует.

Match HTTP timeout по умолчанию 15s, max_retries=2 (всего до3 попыток), backoff .25s exponential при network/5xx; 404/429 не повторяются автоматически. Retry-After поддерживает только целые секунды 1..3600, не HTTP-date. Match cache success3600s/notfound300s/error60s, rate-limit TTL=Retry-After. TTL — срок повторного получения данных, не гарантия свежести анализа. Per-match single-flight ограничен процессом; между worker и web экземплярами общего lock нет. Matchup cache в памяти, отдельный общий для героев cooldown429. В процессе аудита внешних игровых запросов не было.

Live схема проверена через information_schema (capture.json). `matches`: BIGINT PK match_id; fetch_status varchar с CHECK; raw_payload JSONB nullable; fetched_at/created_at/updated_at timestamptz. `match_analyses`: UUID PK; BIGINT FK match_id RESTRICT; algorithm_version varchar64; JSONB report_payload; status/completeness CHECK; computed_at timestamptz; UNIQUE(match_id,algorithm_version). Секции имеют ключи `group_flow_v1:overview|players|draft|ruiner|timeline`, flow — `group_flow_v1`. Значение `ruiner_v1` находится внутри report, а не является SQL ключом секции. Для нормализованных игроков отдельной таблицы нет. Live определения constraints/indexes сохранены в db_verification.json. DTO: backend/app/models/matches.py (PlayerStat, NormalizedMatch, DerivedMetric), models/performance.py (PlayerPerformance, TeamPerformanceReport, RuinerReport), models/match_api.py (MatchEnvelope, PublicPlayer, OverviewReport). История snapshot/report не ведётся. Фактические колонки сохранены в capture.json, ограничения и операции подтверждены db/models.py, migrations и существующими PostgreSQL-тестами.

Sanitized raw сохраняется целиком в JSONB до нормализации, включая неизвестные поля. NormalizedMatch.raw содержит **только** DraftRawData и MatchEventRawData, не весь исходный snapshot. Поэтому NOT_MAPPED означает, что поле осталось в raw БД, но отсутствует в typed pipeline. LOST_IN_BACKEND для leaver означает утрату по пути к решению, а не исчезновение из JSONB. account_id и chat удаляются раньше: намеренная политика приватности. Отсутствие персонального поля в публичном DTO не дефект.

Source digest связывает report с flow, но GET не сверяет текущий Match.raw_payload и не проверяет согласованность model/config версии оболочки с data. source_digest учитывает match/status/schema_version, не время fetch. config digest учитывает значения настроек, не код: старый report и новый replay могут иметь тот же ruiner_v1/digest. Сохранённый report после обновления кода не становится автоматически новым.

## P1: события, draft и публичные поля

Overview сохраняет базовые score/winner/mode/patch/rosters; towers_destroyed/roshan_kills остаются null с объяснением. Players передаёт K/D/A, GPM/XPM, damage/healing/net_worth, obs_placed/sen_placed, items/backpack/neutral, level, stuns, buyback_count, позиции; observer_kills/sentry_kills есть в RI metrics, но нет в PublicPlayer. account/Steam IDs намеренно не выдаются. Нули item IDs означают empty, null — отсутствие данных, неизвестный catalog ID — unmapped.

Draft сохраняет явные hero_id/team/is_pick/order и исходный индекс, не восстанавливает порядок по slots. draft_timings остаётся в raw и не используется. Режим/патч ограничивают достоверность; aggregate matchups не доказывают статистику конкретного патча.

Timeline использует objectives, teamfights, radiant_gold_adv/xp_adv, общие и player kills/buyback/purchase logs. Секунды [-3600,duration+60] сохраняют pregame; графики индексируются minute*60. Slots игроков 0..4/128..132, `slot` событий может означать индекс 0..9 — требуется различать пространства. Dedupe сохраняет original_refs; purchase добавляет source ref в ключ, чтобы не слить две покупки одного предмета в секунду. Кривая отрицательна для преимущества Dire, не отбрасывается как невалидная статистика. game_mode/patch/picks не влияют на RI через Timeline.

Серии gold_t/xp_t/lh_t, deaths_log, connection_log, ward logs/maps, lane_pos, hero_damage_t/healing_t, ability/item usage/targets/upgrades, neutral_item_history остаются только в raw (если присутствуют). Их наличие само по себе не разрешает придумывать новую аналитику. P2 инвентаризирован автоматически по всем прочим фактическим match/player ключам. Большие массивы в CSV представлены длиной, SHA, sample и точным путём к сохранённому полному значению.

## Проверенные внешние первоисточники

'''
for s in sources:
 if 'url' in s:code+=f'- [{s["repo"]} {s["commit"]}]({s["url"]}), прочитан {s["read_at"]}, SHA bytes `{s["sha256"]}`.\n'
code+='''
[Документация OpenDota](https://docs.opendota.com/) проверена 24.10.2026, страница динамическая и не дала читаемую схему через web extraction. Не использовалась как доказательство обязательности каждого поля. Схема core разделяет match и player counters, хранит stuns как real, GPM/XPM как integer, отдельно leaver_status и parsed fields. Parser получает teamfight_participation из игрового свойства отдельно от K/D/A. Это не доказывает, что 1.2 является долей уникальных убийств. Семантика конкретного спорного assist остаётся UNVERIFIED. dotaconstants проверен как источник режима, но runtime использует локальную закреплённую ревизию, а не скачанный master.

'''+evidence
save('RI_02_DATA_01_CODE_MAP.md',code)

trace=header+'''## Методика и формула

В таблицах ниже — фактические сохранённые inputs, новый **offline** replay текущим кодом, а не перезаписанные live отчёты. `traces.json` содержит полную точность всех 120 расчётов; здесь подробно приведены 20 игроков двух пилотов. В JSON `comparisons` содержит также контрольные математические сравнения GPM/XPM для support/unknown: evaluator их **не вызывает** и штрафов по ним нет. Наличие сравнения в диагностике не означает использование в модели.

`minutes=duration/60`; DPM=D/minutes; HDPM=hero_damage/minutes; TDPM=tower_damage/minutes; HPM=hero_healing/minutes. GPM/XPM уже имеют минутную единицу, передаются как float без повторного деления. Wards — исходные четыре счётчика, а не purchase/maps/log lengths. Oracle имеет obs_placed9 при purchase_ward_observer10 и sen_placed22 при purchase_ward_sentry23: сохраняются именно9/22, покупки не подставляются. KDA=(K+A)/D только при D>0, иначе null. Normalized derived округляет KDA/counter-ratio до4 знаков; observed считает из исходных целых с float точностью.

Counter ratio=(K+A)/team_score, если K,A и положительный score известны. Participation usable дополнительно требует score>=10, K<=score, при полных10 deaths K+A<=sum(all deaths); превышение score при пройденном sanity-check даёт over_team_score_unverified. Raw ratio не обрезается. В observed отдельный counter_ratio появляется **только при отказе usable** и доступной арифметике; normalized derived имеет историческое имя kill_participation, но статус available означает доступность арифметики, не оси.

Peers — союзники того же role_group без самого игрока; unknown сравнивается со всеми союзниками. Ref=median(доступных peer значений), minimum_cohort=2 включая себя. У смерти higher=bad, у остальных lower=bad. Floor=60/duration для rates, 1/team_score для KP, 1 для прочего. `bad=clip((own-ref)/max(ref,floor),0,1)` для смертей, иначе `clip((ref-own)/max(ref,floor),0,1)`. `good` — противоположное отклонение. При ref=0 для positive-oriented метрики сравнение null, наблюдаемый ненулевой вклад получает descriptive signal без кредитной величины.

Core weights S=.30,P=.25,E=.25,I=.20. Support/unknown S=.50,P=.50. Economy=mean(GPM_bad,XPM_bad), только если оба известны. Impact=HDPM_bad. Credit=15*max(good) для tower/healing/четырёх ward counters и для hero damage у noncore. Смерти/участие/economy good могут давать положительный сигнал, но не входят в credit. Credit-only bad не штрафуется. Coverage=sum(weights доступных осей). Нужно >=2 осей, coverage>=.70, разрешённый mode1/2/22, duration>=900 и валидная команда. Index=int(max(0,100*Σ(w*axis)/coverage-credit)+.5), иначе null. Округление credit в DTO до4 не используется обратно в расчёте. Signals показываются от .20; это не порог включения вклада в формулу. Confidence medium требует полных осей и confirmed ролей всей cohort. В этих12 матчах все low. Победитель в формулу не входит.

'''
trace+=table(['Матч','Raw fetched UTC','duration s','score R/D','status','Индексов'],[[c['match_id'],c['source_fetched_at'],next(t['summary']['duration'] for t in traces if t['match_id']==c['match_id']),str(next(t['summary']['radiant']['score'] for t in traces if t['match_id']==c['match_id']))+'/'+str(next(t['summary']['dire']['score'] for t in traces if t['match_id']==c['match_id'])),c['status'],c['scored']] for c in census])
for mid in (9051271323,9057722463):
 ts=[t for t in traces if t['match_id']==mid]
 trace+=f'\n## Матч {mid}: все10 игроков\n\n'
 trace+=table(['Slot','Hero','Team','K/D/A raw=normalized','GPM/XPM','Role','Axes S/P/E/I','Coverage','Credit','Base','Index','confidence'],[[t['slot'],t['hero'],t['report']['team'],'/'.join(str(t['source'][k]) for k in ('kills','deaths','assists')),str(t['source']['gold_per_min'])+'/'+str(t['source']['xp_per_min']),t['report']['role_group']+' '+fmt(t['report']['position']['position']),'/'.join(fmt(t['report']['axes'].get(k)) for k in ('survival','participation','economy','impact')),t['report']['evidence_coverage'],t['credit_full_precision'],t['base_before_credit'],t['report']['error_index'],t['report']['confidence']] for t in ts])
 for t in ts:
  r=t['report'];trace+=f'\n### {t["hero"]}, slot {t["slot"]}\n\n'
  trace+=f'Role evidence: `{fmt(r["position"])}`; peer slots `{t["cohort_slots"]}`; weights `{fmt(t["weights"])}`.\n\n'
  fields=['kills','deaths','assists','hero_damage','tower_damage','hero_healing','gold_per_min','xp_per_min','obs_placed','sen_placed','observer_kills','sentry_kills','stuns','leaver_status','position_est']
  aliases={'gold_per_min':'gpm','xp_per_min':'xpm','stuns':'stun_duration_seconds','position_est':'performance_position'}
  trace+=table(['Raw field','Raw value','Normalized field/value'],[[k,t['source'].get(k),aliases.get(k,k)+'='+fmt(t['normalized'].get(aliases.get(k,k),'NOT_MAPPED'))] for k in fields])
  trace+=table(['Metric','Observed','Peer slot:value','Median','Floor','Bad','Good','Использование'],[[m,r['observed_metrics'].get(m),c['peer_values'],c['reference'],c['denominator_floor'],c['bad'],c['good'],('survival' if m=='deaths_per_min' else 'participation' if m=='kill_participation' else 'economy' if m in ('gpm','xpm') and r['role_group']=='core' else 'impact' if m=='hero_damage_per_min' and r['role_group']=='core' else 'descriptive only; no compare in evaluator' if m in ('gpm','xpm') else 'positive credit only')] for m,c in t['comparisons'].items()])
  trace+=f'\nKDA observed={fmt(r["observed_metrics"]["kda"])}; normalized derived={fmt(t["normalized_derived"])}. Weighted sum={fmt(t["weighted_sum"])}; base={fmt(t["base_before_credit"])}; credit(full)={fmt(t["credit_full_precision"])}; index={fmt(r["error_index"])}. При недостающих осях base приведена только как промежуточная арифметика, не как разрешённая оценка.\n\n'
  trace+='Negative: '+fmt([s['code'] for s in r['negative_signals']])+'. Positive: '+fmt([s['code'] for s in r['positive_signals']])+'.\n\nMissing metrics: '+fmt(r['missing_metrics'])+'. Reasons: '+fmt(r['reason_codes'])+'.\n'
 trace+='\n### Командный выбор\n\n'
 trace+=table(['Team','scored','strict','preliminary'],[[side,ts[0 if side=='radiant' else 5]['team_report']['scored_players'],ts[0 if side=='radiant' else 5]['team_report']['selection'],ts[0 if side=='radiant' else 5]['team_report']['preliminary_selection']] for side in ('radiant','dire')])
trace+='''
## Три ключевых случая

**Oracle:** raw 1/8/11, score10, duration1933, raw teamfight_participation=1.2. Normalized KDA=1.5, counter ratio=1.2 AVAILABLE. Current observed usable=null, diagnostic counter ratio=1.2, exact reason over_team_score_unverified. Survival0, participation null; coverage.5 и одна ось, поэтому index null независимо от credit15. Сохранённый REST пока не имеет diagnostic ratio и использует прежний team_kills_missing_small_or_inconsistent. Это старый report, не потеря при нынешнем HTTP serializer. Code/config version не различают эти реализации.

**Hoodwink:** raw1/12/7 → usable KP=.8. Единственный другой support Oracle имеет KP null; доступных peers0, сравнение не проходит minimum_cohort2. DPM .372478 против .248319 → survival .5. Coverage.5, credit3.99421128799, index null. `missing_metrics=[]` говорит о наличии собственных observed inputs, а не достаточности peers/осей. Estimated position формирует support корректно, ограничивает confidence, не создаёт этот null.

**Spectre:** raw1/8/5, GPM358,XPM386,hero_damage13258,duration1933. Peers core slots2,4. KP .6 против median.65 → .0769230769231. Economy среднее((386−358)/386,(451−386)/451)=.108331514309. Impact=(14336−13258)/14336=.0751953125. Survival0. `100*(.30*0+.25*.0769230769231+.25*.108331514309+.20*.0751953125)−0=6.1352710308`, half-up → **6**. Все составляющие bad ниже .20, поэтому negative_signals=[] закономерно. Это объяснимость модели, не арифметический дефект. Low confidence при coverage1 обусловлена estimated ролями. Никаких коэффициентов для этого героя или Match ID нет.

Тот факт, что несколько союзников могут получить ассист на одно убийство, объясняет сумму ассистов команды выше score, но не доказывает превышение индивидуальной доли уникальных убийств. Parser хранит собственный игровой teamfight_participation отдельно. Без полного assist→kill события происхождение Oracle11 assists не установлено, 1.2 нельзя автоматически считать процентом или обрезать до1.

'''+evidence
save('RI_02_DATA_01_MATCH_TRACE.md',trace)

contract=header+'''## Фактическая выдача

Локальный сервер `127.0.0.1:8000`: выполнены20 GET (две схемы маршрутов × два матча × пять разделов), без POST. Local-alpha10/10 HTTP200, защищённые10/10 без токена HTTP401 AUTH_REQUIRED. Авторизованный live HTTP200 **BLOCKED**: действующая пользовательская Telegram-сессия для аудита не предоставлена. Обход auth и выдача токена от имени пользователя не выполнялись. Авторизованный путь, JWT/пользователь и паритет с local-alpha подтверждены существующими тестами в отдельной `dota_hub_test` с тестовыми credential; это не Telegram WebView и не live login.

Оба маршрута вызывают один stored(), но условия доступа различаются. Authenticated требует сессию существующего TelegramUser; история запроса/членство в чате для GET конкретного матча не проверяется (публичная ссылка доступна другому аутентифицированному пользователю, это существующая политика, проверенная test_forwarded_match_link_is_public_to_other_authenticated_user). Local-alpha зарегистрирован только при local_alpha, требует loopback host/client и разрешённый Origin. Тело результата не содержит account_id/Steam ID/raw payload.

'''
contract+=table(['Матч','Раздел','Local HTTP','status','completeness / quality','DB→API отличия','Read projection→API'],[[x['match_id'],x['section'],200,x['status'],str(x['completeness'])+' / '+str(x['quality']),x['db_to_api_diffs'] or 'нет',x['projection_to_api_diffs'] or 'нет'] for x in api])
contract+='''
Во всех десяти ответах data соответствует сохранённому DTO после разрешённой read-time проекции. Для9057722463 legacy preliminary отсутствует в JSONB, появляется только в HTTP; БД не меняется. Для9051271323 даже старые reason_codes возвращаются как сохранены. Replay меняет два поля Oracle: diagnostic counter_ratio появляется, общий код отказа заменяется точным. Индексы всех20 совпадают. `model_version=ruiner_v1`, config_digest и source_digest при этом одинаковы. Flow config digest тоже равен текущему; при неизменном snapshot `_process` может вернуть старый report из кэша даже после явного analyze. Это доказанный пробел инвалидации при смене реализации, не отказ OpenDota и не потеря JSON поля на GET.

## Envelope: ожидаемое = фактическое наличие

'''
envs={mid:read(f'private/api_local-alpha_matches_{mid}_ruiner.json') for mid in (9051271323,9057722463)}
expected=['schema_version','match_id','status','available_sections','data','error','limitations','model_version','config_version','analyzed_at','completeness','retry_after_seconds']
contract+=table(['Поле','JSON type','9051271323','9057722463','Проверка / смысл'],[[k,type(envs[9051271323][k]).__name__,('{RuinerReport}' if k=='data' else envs[9051271323][k]),('{RuinerReport}' if k=='data' else envs[9057722463][k]),'present; DTO JSON validate PASS; no null->0'] for k in expected])
contract+='\n`analyzed_at` — время сохранения, не GET/replay; `status=ready` — отчёт доступен, не обещание десяти оценок. `completeness=partial` и `data.quality=partial` согласованы. `retry_after_seconds=null` и Retry-After отсутствует при200. Cache-Control no-store присутствует на всех20 запросах.\n\n## RuinerReport / team / player\n\n'
for title,obj in [('data',envs[9051271323]['data']),('data.teams.radiant',envs[9051271323]['data']['teams']['radiant']),('data.players[slot=0]',envs[9051271323]['data']['players'][0])]:
 contract+=f'### {title}\n\n'
 contract+=table(['Ожидаемое поле DTO','Фактический type','Значение / краткое представление','Сохранённый report'],[[k,type(v).__name__,f'{len(v)} records; полный JSON в live_ruiner_responses.json' if k in ('players','teams') else v,'совпадает; legacy projection см. выше'] for k,v in obj.items()])
contract+='''
Все scalar/axes/observed/signals/null каждого из20 участников можно сопоставить с `live_ruiner_responses.json` и MATCH_TRACE. Player DTO содержит slot/team/team_number/hero_id/position/role_group/index/confidence/coverage/axes/observed/credit/signals/missing/reasons/limitations. duration, team_score, leaver_status, source_fetched_at, raw-vs-usable отдельный статус не являются обязательными полями текущего /ruiner. Их отсутствие классифицируется как API_DIAGNOSTIC_GAP, а не потеря обязательного API поля. Runtime response model authenticated типизирован MatchEnvelope[RuinerReport], local generic route в OpenAPI не описывает все section DTO — документационный долг, фактическая сериализация общая.

## Повреждённые и устаревшие данные: изолированные эксперименты

Это копии сохранённого report и fake read-only session, не запросы к изменённой рабочей БД. Baseline200 проверен перед мутациями. Эмуляция возвращает datetime, как SQLAlchemy, и проходит тот же stored()/DTO serializer.

'''
ex=read('experiments.json')
contract+=table(['Вариант','HTTP','Факт','Вердикт'],[[x['id'],x.get('http'), ('envelope='+str(x.get('model_version'))+', data='+str(x.get('data_model')) if 'model' in x['id'] else x.get('code') or x.get('dire_projection',{}).get('reason_codes') or 'данные выдаются'),('FAIL: противоречивый metadata принят' if x['id'] in ('stored_model_mismatch','stored_config_mismatch','stored_schema_mismatch') else 'PASS: source mismatch отвергнут' if x['id']=='stored_source_digest_mismatch' else 'PASS: conservative repair/legacy' if x['id'] in ('stored_corrupt_preliminary','stored_legacy_preliminary') else 'исторический report принят; свежесть отдельно не проверена' if x['id']=='stored_stale_raw' else 'PASS')] for x in ex if x['id'].startswith('stored_')])
contract+='''
GET валидирует структуру DTO и совпадение section.source_digest с flow.source_digest; не валидирует wrapper schema/model/config против data и raw Match. При противоречивой, но структурно допустимой preliminary выдаётся none/stored_projection_inconsistent. При структурной порче DTO возвращается503 REPORT_UNAVAILABLE (проверено существующими тестами). Оси/индексы не пересчитываются, сохранённые строки не меняются.

## Прочие разделы

Overview и Players обоих пилотов full по своей области core stats; это не означает availability ward/parsed/roles для каждого поля. Timeline первого complete, второго missing/unavailable; ограничения второго отражают отсутствие событий. Draft обоих partial. Basic fields не скрываются из-за слабого Draft/Timeline. Все пять data DTO совпадают с JSONB, кроме описанного legacy preliminary. Найдена отдельная семантическая проблема Timeline team attribution для уничтоженной своей башни — см. F10; она не участвует в RI.

'''+evidence
save('RI_02_DATA_01_API_CONTRACT_AUDIT.md',contract)
(E/'live_ruiner_responses.json').write_text(json.dumps(envs,ensure_ascii=False,indent=2)+'\n')

findings=header+'''## Вердикт

**MIXED CAUSES.** Для действующих численных осей необходимые имеющиеся scalar данные поступают и преобразуются без обнаруженной потери на12 snapshots. Для20 пилотных игроков сохранённые индексы соответствуют offline replay. Полного положительного ответа всей цепочке дать нельзя: last-good raw не защищён от неудачного refresh, leaver evidence не доходит до решения, новая диагностика может навсегда остаться за старым cache key, wrapper metadata допускает противоречие с data. Объяснение Oracle требует семантики игровых счётчиков, а не ослабления guard. Неприсутствующие parsed поля второго матча — ограничение источника, а не исправляемая подстановка нулей.

Приоритеты ниже относятся к последствиям дефекта, а не к P0/P1/P2 инвентаризации полей. P0 критического искажения действующих численных оценок на этих snapshots **не найдено**. Отсутствие находки не доказывает исправность всех произвольных матчей.

'''
items=[
('F01','P1','PERSISTENCE_ISSUE','backend/app/services/match_ingestion.py:_mark_pending,_save_result; backend/app/db/repositories.py:upsert_match','raw_payload','Сохранить последний успешный snapshot при временной ошибке refresh.','PENDING, затем API_UNAVAILABLE заменяют весь raw; history нет.','experiments.json expired_good_snapshot_then_503: final_has_match=false; код UPSERT, live schema.','Запустить experiments; использует только MemorySession и expired copy.','После сбоя нельзя восстановить исходные признаки из matches; старые analyses ещё могут остаться. На реальной БД такую потерю не провоцировали.','Разделить последний успешный raw и состояние/ошибку попытки. Минимально не перезаписывать успешный payload pending/error, хранить fetch status отдельно.','Нужно согласовать TTL/retry/stale политику, проверить timeout/429/404/cancel/restart и последующий success. API/формулу менять не требуется. Высокая уверенность.'),
('F02','P1','NORMALIZATION_ISSUE','backend/app/services/match_normalization.py:_player; models/matches.py:PlayerStat; services/performance.py:evaluate; performance_preliminary.py:select_preliminary','leaver_status','Сохранять явный статус источника и использовать согласованный trusted context.','100/120 raw игроков имеют статус, включая0 всех20 пилотов; typed PlayerStat и RuinerReport его не несут. Production caller не передаёт leaver_context.','matrix LOST_IN_BACKEND; experiments leaver_end_to_end unchanged_report=true при замене0 на2; existing direct-context test отказывает.','offline + experiments; смена значения только deep copy.','Подтверждённый источник может не блокировать предварительный выбор; leaver_context_unknown даже при raw0. Формула не штрафует leaver.','Отдельно нормализовать source status/evidence, передавать контекст в предварительный выбор и сохранять provenance.','Сначала закрепить семантику кодов/unknown/disconnect по источнику; не считать любой disconnect уходом. Модель scores менять не нужно, contract/storage version для контекста — отдельное решение. Высокая уверенность в потере.'),
('F03','P1','API_MAPPING_ISSUE','backend/app/api/v1/matches.py:stored; models/performance.py:RuinerReport','model_version/config_version/schema_version wrapper','Согласованный envelope/data или безопасный отказ.','wrapper model= different_model, data model=ruiner_v1 выдан HTTP200; то же для config; wrapper schema999 игнорируется и envelope schema1.','experiments stored_model_mismatch/config_mismatch/schema_mismatch; baseline200.','experiments на fake session без БД writes.','Клиент может приписать индекс иной формуле/настройкам. На реальных20 несогласованность metadata не найдена.','При чтении сверять модель/config wrapper с data, явно поддерживать версии wrapper; иначе REPORT_UNAVAILABLE.','Тесты обоих GET, legacy policy, не мигрировать данные автоматически. Высокая уверенность.'),
('F04','P1','PERSISTENCE_ISSUE','backend/app/services/match_analysis.py:__init__,_process; performance_config.py','config_version/model_version/cache identity','Смена диагностической реализации должна иметь различимую ревизию и управляемую инвалидацию.','Oracle live не имеет counter_ratio1.2 и точного reason, новый replay имеет. source и config совпадают; existing ready branch повторно выдаст прежний report.','api_comparison: replay_vs_stored два пути, flow_config_matches_current=true; текущий source совпадает.','offline; сравнить сохранённый report vs текущий evaluator, ветку cache изучать read-only. POST не вызывался.','Числа корректно сохранены, но RI-02-FIX диагностика не гарантированно достигает пользователя даже после повторного запроса.','Добавить явную implementation/diagnostic revision в cache identity; отдельно разрешить адресный пересчёт после утверждения.','Не менять веса. Определить политику версии модели/схемы и совместимости старых отчётов; тест unchanged inputs+new revision. Высокая уверенность в условии cache-hit.'),
('F05','P2','API_DIAGNOSTIC_GAP','backend/app/api/v1/matches.py:stored; models/match_api.py:MatchEnvelope','source_digest/source_fetched_at/stale','Позволять различить исторический report и текущий raw.','GET сравнивает report с flow, не с Match.raw_payload. Modified raw copy всё ещё HTTP200; API не показывает source digest.','experiments stored_stale_raw; actual two digests match, stale real не найден.','experiments; изменяется копия Match только в fake session.','Потенциальное неверное понимание свежести, а не доказанная неверная арифметика старого report.','Зафиксировать контракт historical vs current; при необходимости expose source timestamp/digest или явный stale marker в отдельной задаче.','Требует продуктового решения, API change согласовать. Высокая уверенность в коде, риск зависит от refresh/concurrency.'),
('F06','P2','API_DIAGNOSTIC_GAP','backend/app/services/performance.py:compare,evaluate','negative_signals/positive_signals/credit','Различать continuous contribution и показанный сильный сигнал.','Spectre6 при negative_signals=[]; positive signal по survival/KP может не давать credit; descriptive contribution при ref0 magnitude0 не даёт credit.','MATCH_TRACE Spectre6.135271; 5/120 nonzero indexes без negative signals.','offline и соответствующие строки traces.json.','Объяснение результата неполно, но математического дефекта нет.','Документировать signal_threshold и credit-only метрики; при отдельном UI/API задании показывать вклад осей.','Не менять коэффициенты ради совпадения текста с индексом; новая аналитика не нужна. EXPECTED BEHAVIOR + diagnostic gap.'),
('F07','P2','NORMALIZATION_ISSUE','backend/app/services/match_normalization.py:_int,_float,_player','invalid value vs missing','Сохранять причину отклонения malformed input.','Negative/string/float GPM становится null, как absent; available_fields отличает наличие usable, но не причину отказа.','experiments negative_stats,float_gpm,numeric_string_gpm; реальные P0 mapped nonnull->null =0 в12 snapshots.','experiments; не менять существующие fixtures.','Сейчас отвергаются неподходящие типы безопасно; диагностика не отличает потерю/ошибку источника от отсутствия.','В отдельной задаче добавить field validation diagnostics/provenance, не приводить float/string к int молча.','Схема OpenDota GPM integer; принятие других типов не обосновано. Высокая уверенность; P2 объяснимость, не доказанная потеря валидного числа.'),
('F08','P3','API_CONTRACT_GAP','backend/app/integrations/opendota.py:parse_match_response; match_normalization.py','FOUND_FULL/source_status','Чётко понимать область completeness.','Empty arrays, missing hero,9 roster и duplicate slot могут получить FOUND_FULL по наличию top-level полей; дальше нормализатор/RI отдельно отвергают или ограничивают.','experiments empty_arrays,missing_hero,incomplete_roster,duplicate_slot.','experiments; duplicate normalization raises MatchNormalizationError.','Нельзя трактовать FOUND_FULL как пригодность всех метрик, но RI не выдаёт уверенный результат по этому флагу.','Документировать source-shape vs stats/roles/analysis quality; при будущих правках отдельные completeness dimensions.','EXPECTED limitation текущего определения; не менять source flag без совместимости.'),
('F09','P1','MODEL_SEMANTICS_ISSUE / SOURCE_ISSUE','backend/app/services/performance.py:participation_assessment; match_normalization.py:_participation_counter_metric','Oracle KP1.2; peer participation','Сохранить наблюдение, не утверждать недоказанную долю.','Raw1.2 доступен арифметически, usable null; Oracle/Hoodwink остаются с одной осью и null index.','MATCH_TRACE, current replay, primary parser field mapping.','offline без корректировки K/D/A.','Два отсутствующих индекса не вызваны потерей счётчиков. Двух support peers недостаточно для статистической нормы даже при KP available.','Продолжать исследование event-level assist→kill или согласовать counter-ratio определение с доказательством сопоставимости; guard не снимать сейчас.','Происхождение11 assists UNVERIFIED, полноценный event-level assist журнал отсутствует. BUG в игровой статистике источника НЕ доказан. Любое изменение оси требует новой версии/калибровки.'),
('F10','P1','DERIVATION_ISSUE','backend/app/services/timeline.py:_objective,analyze_timeline','tower event team / actor','Не выдавать уверенную противоречивую атрибуцию стороны.','9051271323 time1048: raw goodguys tower1_top и player_slot2 (Radiant Death Prophet); API event.team=Dire, actors[0].team=Radiant, evidence_quality=confirmed.','timeline_checks.json real objective и actual event; live Timeline тот же event.','timeline action, только replay snapshot.','На RI влияния нет. Timeline полагает attacker противоположным owner даже при своем actor; возможен deny.','Отделить owner/actor, распознавать доказанный deny или помечать conflict/unknown, не назначать вражескую сторону без проверки.','Реальный конфликт подтверждён; точная игровая причина требует replay/source semantics. Проверить deny, creep kill, unknown actor, Roshan codes2/3, slot vs player_slot. Исправление другого блока только отдельным заданием.'),
('F11','P3','DATA_UNAVAILABLE','backend/app/services/match_normalization.py:_events,_player','parsed fields 9057722463','Не заполнять отсутствующие статистики нулями.','stuns/wards/positions/event arrays отсутствуют; Players extended null, Timeline unavailable.','matrix, capture, MATCH_TRACE.','offline, local GET.','53/120 scores не равно полноте raw;11/12 snapshots partial.','Получать parsed evidence отдельным согласованным процессом, учитывать rate budget; POST parse не выполнялся.','Доступность нового parsed snapshot не гарантирована. EXPECTED BEHAVIOR, не backend дефект.'),
]
for id,severity,kind,files,field,expected,actual,proof,repro,impact,fix,deps in items:
 findings+=f'## {id} — {severity} — {kind}\n\n'
 findings+=table(['Пункт','Свидетельство'],[['Файлы/функции',files],['Поле',field],['Ожидание',expected],['Факт',actual],['Доказательство',proof],['Воспроизведение',repro],['Влияние',impact],['Минимальная рекомендация, НЕ реализована',fix],['Зависимости/уверенность',deps]])+'\n'
findings+='''
## Неиспользуемые доступные показатели и намеренные исключения

В raw первого пилота присутствуют teamfight_participation, hero_variant, lane/is_roaming, gold/gold_spent/total_gold/total_xp, stacks, roshan/tower/courier/neutral kill counters, lane_efficiency_pct, ward maps/purchases/logs, ability/item details и временные серии. Большая часть не имеет typed поля и не участвует в RI, но остаётся в JSONB. В текущей формуле нет отрицательного требования к healing/wards/stuns, поддержки причинных выводов, population baseline или штрафа за проигрыш. Добавление этих факторов не является багфиксом маппинга. raw teamfight_participation не следует молча подменять нашим KP.

`isRadiant` не используется: команда определяется каноническим player_slot. Для20 пилотов принадлежность совпала. `is_radiant` — альтернативное имя из задания, в этих snapshots отсутствует; отсутствие alias не дефект. match_id намеренно переводится в строку DTO. account_id намеренно удаляется sanitizer, personaname нормализуется и ограничивается80. Нет оснований требовать эти идентификаторы на /ruiner.

## Последовательность минимальных дальнейших задач

1. Исправить F01 отдельно с тестом восстановления и сохранения последнего успешного snapshot.
2. Согласовать и провести F02: источник/evidence leaver→preliminary, не менять formula.
3. Закрыть F03/F04: согласованность metadata и явная diagnostic revision для cache, затем адресная проверка нового отчёта. Массовую миграцию/пересчёт сейчас не выполнять.
4. Разрешить политику свежести F05 и объяснимость F06/F07. Игровое определение participation F09 требует отдельного решения на основе данных.
5. Передать F10 в отдельную Timeline-задачу; исправлений в соседнем модуле в этом аудите нет.

Никакое из предложений не реализовано автоматически. Таблица findings не меняет статус прежних задач и не объявляет алгоритм откалиброванным.

'''+evidence
save('RI_02_DATA_01_FINDINGS.md',findings)

suite=ET.parse(E/'pytest.xml').getroot().find('testsuite'); tests=list(suite.findall('testcase'))
qa=header+'''## Ответ на основной вопрос

**Частично.** Численные scalar inputs существующих осей на доступных snapshots корректно доходят до evaluator; произвольный «полный raw→все решения» путь не подтверждён. Найдены дефекты/риски сохранения last-good snapshot, потери leaver context, согласованности version metadata и инвалидации диагностического кэша. На реальных20 игроках current replay совпал с сохранёнными индексами, все10 local section responses совпали с сохранёнными DTO после штатной проекции. Отдельная проблема Timeline не влияет на RI. Обоснованности самих весов и причинной интерпретации индекса этот технический аудит не доказывает.

## Репозиторий и область изменений

HEAD приведён выше. Полные Git status до/после — `qa/ri02/data01/baseline.json` и `scope_verification.json`. Исходное дерево уже содержало изменения backend/api/models/normalization/performance, frontend и тестов предыдущих задач. Они сохранены. В этом задании добавлены только шесть документов ниже, evidence под `docs/qa/ri02/data01/` и три standalone audit scripts. Нет коммита, изменений production/config/API/UI/миграций/существующих fixtures. Raw и все report rows двух пилотов сравнены до/после read-only SQL: одинаковы. Проверка SHA production/frontend/существующих tests — в scope_verification.json. Тесты писали только в выделенные тестовые БД по существующим защитным fixtures.

## Полнота P0: три разных знаменателя

Матрица содержит58 различных имён P0:11 match-полей и47 player-полей. На каждый10-player snapshot приходится481 проверяемый путь (включая альтернативный is_radiant). Инвентаризация **58/58=100%**, заполнено5772 P0 строк для12 матчей. Проверяемость исходного HTTP account_id ограничена sanitizer:120 строк UNVERIFIED, остальные5652/5772=97.921% классифицированы по сохранённому источнику. Это полнота аудита, не полнота данных или доказательств модели.

'''
matrix=read('matrix_rows.json')['rows']; rawstats=[]
for mid in (9051271323,9057722463):
 rs=[r for r in matrix if r['priority']=='P0' and f'match_id={mid}' in r['evidence']]
 counts=Counter(r['status'] for r in rs); nonnull=sum(r['source_presence']=='present' for r in rs)
 rawstats.append([mid,len(rs),nonnull,f'{100*nonnull/len(rs):.2f}%',counts['PRESENT_CORRECT'],counts['NOT_MAPPED'],counts['LOST_IN_BACKEND'],counts['MISSING_IN_SOURCE'],counts['UNVERIFIED']])
qa+=table(['Матч','P0 paths','Non-null raw','Raw presence %','Typed mapped','Not mapped','Leaver lost to model','Missing/null source','HTTP unverified'],rawstats)
qa+='''
Счёт raw presence: «не-null поле / все перечисленные пути». В знаменатель намеренно входит альтернативный alias и приватный account_id, поэтому это описательная доля, не норматив готовности. Убедительно восстановить original HTTP completeness нельзя. Даже100% полей не означает минимум usable осей. Matched source_status: первый FOUND_FULL, второй FOUND_PARTIAL; summary/stats первого и второго могут быть complete при недостатке roles/timeline.

На12 матчах:1947 P0 PRESENT_CORRECT,868 NOT_MAPPED,100 LOST_IN_BACKEND (leaver по пути к решению, raw сохранён),2737 MISSING_IN_SOURCE,120 UNVERIFIED. На этом наборе нет PRESENT_INCORRECT для mapped ненулевого scalar. Полная матрица содержит13750 строк P0/P1/P2, включая вложенные draft actions. Source path и match ID находятся в source_json_path/evidence, для игрока указан player_slot. NOT_MAPPED — не автоматически дефект. Огромные logs/maps не скопированы в каждую CSV ячейку: сохранены SHA/размер/sample и ссылка на полный frozen raw.

## Потери, null и нули

- Подтверждена потеря leaver_status из typed normalization/evaluator/preliminary, при сохранении raw. Остальные unmapped P0/P1 перечислены в CSV; многие не нужны текущей формуле (teamfight_participation, stuns в RI, stacks, gold totals, ability/item logs, variant).
- K/A остаются1/11 для Oracle. **Usable** participation становится null из-за unverified превышения, исходное1.2 сохранено в current normalized/observed diagnostic; live старый report ещё без нового поля. Hoodwink собственный KP .8 известен, null появляется только в peer axis.
- Missing и явный null остаются null. Некорректный negative/bool/numeric-string/float для integer-поля отклоняется в null. В experiments GPM211.5 и строка211 не округляются; real snapshots не содержали такого валидного scalar, потерянного при маппинге.
- Неподтверждённой подстановки исходного отсутствующего показателя в0 не найдено. Индекс0 может получиться из clip(base−credit), это итог модели. Credit0 означает отсутствие пригодного положительного кредита, а не доказанный нулевой вклад игрока. Empty item0 сохраняет семантику пустого слота, не заменяет missing item.
- В9057722463 team scores44/42, сумма личных kills43/40, сумма смертей противника44/42. Эти разные счётчики сохраняются, один не подменяется другим; причина разницы не доказана этим snapshot. В9051271323 соответствующие три величины совпадают10/45. Предположение «sum(player kills) обязано равняться score» не используется для коррекции.

Производные метрики, единицы и полная формула приведены в MATCH_TRACE: DPM, HDPM, TDPM, healing/min, descriptive KDA, raw counter-ratio, usable participation, неизменные GPM/XPM, ward counters. Нормализатор round4; evaluator использует исходную float точность, signals magnitude round6/value round4, credit DTO round4, индекс half-up integer. Rates не вычисляются повторно из уже per-minute GPM/XPM.

## Реальные проверки и существующие тесты

'''
qa+=f'Выполнен полный backend pytest: **{suite.attrib["tests"]} PASS, {suite.attrib["failures"]} FAIL, {suite.attrib["errors"]} ERROR, {suite.attrib["skipped"]} SKIP**, время {suite.attrib["time"]}s. JUnit `pytest.xml`, stdout `pytest.log`. Одно существующее StarletteDeprecationWarning об httpx/TestClient. Новые production-тесты не добавлялись. Дополнительная команда validate выполнила3864 элементарных сверки raw/scalar/rates/derived/axes/CSV/ссылок без расхождений (это не3864 новых pytest-теста); artifact_checks.json содержит счётчики. Offline evidence/дополнительные experiments находятся в самостоятельном audit script.\n\n'
groups=Counter(t.attrib['classname'] for t in tests)
qa+=table(['Существующий файл / группа','Фактически PASS'],[[k.replace('.','/')+'.py',v] for k,v in sorted(groups.items())])
qa+='\nПолный поимённый список parametrized случаев и результатов:\n\n'
qa+=table(['Test node','Результат'],[[t.attrib['classname']+'::'+t.attrib['name'],'PASS' if not list(t) else 'см. pytest.xml'] for t in tests])
qa+='''
## 28 граничных сценариев

PASS означает совпадение с заявленным безопасным поведением. Проверка, успешно воспроизводящая дефект, помечена FAIL для целевого инварианта. Синтетические значения относятся исключительно к копиям в памяти, не к реальному матчу.

'''
boundaries=[
('B01','Полный snapshot','baseline full сохранён; 10 players','PASS','test_full_match_keeps_public_nickname_and_removes_private_identifiers; offline9051271323'),
('B02','Частичный snapshot','null сохранён, доступные оси доступны','PASS','test_partial_match_keeps_zero_and_marks_unknown_as_unavailable;9057722463'),
('B03','Нераспарсенный','нет fabricated events/wards','PASS','test_missing_wards_unparsed_match_and_missing_damage_do_not_imply_zero'),
('B04','Нет match ID','MALFORMED_RESPONSE/MatchNormalizationError','PASS','experiments missing_match_id; test_malformed_and_wrong_match_are_rejected'),
('B05','OpenDota404','NOT_FOUND, no fabricated data','PASS','test_http_status_mapping; test_provider_errors_and_no_fabricated_reports'),
('B06','429','RATE_LIMITED, Retry-After bounded; no immediate retry','PASS','test_rate_limit_respects_retry_after_without_retry'),
('B07','Timeout','bounded retries, API_UNAVAILABLE','PASS','test_transient_failures_have_bounded_backoff'),
('B08','Unexpected JSON','MALFORMED_RESPONSE','PASS','test_malformed_json_and_api_key_do_not_leak'),
('B09','Неполный roster','incomplete_team; нет вымышленных игроков','PASS','experiments incomplete_roster; test_partial_roster_keeps_available_overview_without_fabrication'),
('B10','Duplicate slot','normalization rejects','PASS','experiments duplicate_slot; test_invalid_or_duplicate_player_slots_are_rejected'),
('B11','Missing hero','hero null, invalid team unscored','PASS','experiments missing_hero'),
('B12','Unknown account','no ID invention, anonymous only missing nickname','PASS','test_full_match_keeps_public_nickname_and_removes_private_identifiers; test_public_nickname_is_used_only_when_present'),
('B13','Missing K/D/A','observed null, explicit reasons','PASS','experiments missing_kda; test_missing_counter_has_distinct_reason'),
('B14','Team score0','no division; team_score_zero','PASS','test_ratio_contract_and_refusal_reasons[KP-QA-06]; experiments zero_score'),
('B15','Score below10','raw ratio retained; usable null','PASS','test_ratio_contract_and_refusal_reasons[KP-QA-07]; experiments small_score'),
('B16','K+A>score и boundary=score','raw>1 retained, usable null; equality accepted','PASS','test_ratio_contract_and_refusal_reasons; experiments kp_boundary_equal/kp_over_score'),
('B17','Negative values','invalid->null без отрицательного score','PASS','experiments negative_stats; validation diagnostics missing F07'),
('B18','Duration0','parser rejects; direct normalization duration null, RI unavailable','PASS','experiments zero_duration; test_short_or_missing_duration_never_amplifies_rates_into_scores'),
('B19','Missing damage','не0, no fabricated impact/credit','PASS','experiments missing_damage_wards; test_low_missing_metrics_are_not_replaced_by_zero_penalties'),
('B20','Missing wards','не0','PASS','test_missing_wards_unparsed_match_and_missing_damage_do_not_imply_zero'),
('B21','Missing events','Timeline unavailable/partial','PASS','test_partial_without_fights_and_missing_sources; test_empty_arrays_are_available_but_no_events_or_curves_is_unavailable'),
('B22','Estimated position','group assigned; low confidence','PASS','test_unconfirmed_position_never_confidently_selects;20-player traces'),
('B23','Unknown position','no inferred farm role, unknown cohort','PASS','test_no_role_no_farm_inference_from_hero_or_gpm; experiments unknown_position'),
('B24','Confirmed/unknown leaver','direct context works; raw end-to-end ignored','FAIL','test_incomplete_team_and_leaver_evidence PASS, experiments leaver_end_to_end unchanged ->F02'),
('B25','Stale analysis','cached historical data accepted; new implementation not invalidated','FAIL','api_comparison flow_config_matches_current plus stale diagnostic ->F04; experiments stale_raw ->F05'),
('B26','Model/config mismatch','contradictory metadata must fail safely; actual200','FAIL','experiments stored_model_mismatch/config_mismatch/schema_mismatch ->F03'),
('B27','Legacy preliminary missing','read-time projection, DB unchanged','PASS','9057722463 live; test_preliminary_storage_cached_read_api_and_legacy_projection'),
('B28','Corrupt preliminary','semantic none or structural503','PASS','test_api_rejects_inconsistent_persisted_preliminary; test_api_rejects_structurally_invalid_saved_projection; experiments'),
]
qa+=table(['ID','Сценарий','Ожидаемое / фактическое','Статус','Доказательство'],boundaries)
qa+='''
## DATA-QA-01…25

'''
checks=[
('01','Полная цепочка OpenDota','PASS','CODE_MAP, actual symbols, parser/ingestion/group_flow tests'),
('02','Место сохранения raw','PASS','JSONB подтверждено; найден F01, а не потеря scalar в parser'),
('03','PostgreSQL схема','PASS','capture.schema + db_verification.constraints/indexes; migrations/repository tests'),
('04','Все P0 поля','PASS','58/58 inventoried; account original120 UNVERIFIED явно выделены'),
('05','Все20 игроков','PASS','MATCH_TRACE + independently reconstructed120 indexes'),
('06','Teams/slots','PASS','raw isRadiant agrees slot; same-team cohorts; отдельный event-space риск F10'),
('07','K/D/A/team scores','PASS','raw=normalized; расхождения aggregate counters второго матча описаны, не исправлялись'),
('08','GPM/XPM units','PASS','нет повторного деления на duration; число type сохранено'),
('09','Damage/healing','PASS','rates full precision, scalar сохранён'),
('10','Observer/sentry','PASS','four counts preserved, no purchase/log substitution; отсутствующие null'),
('11','Position/role','PASS','estimated≠confirmed lane; second unknown; конфликт duplicate positions tested'),
('12','Leaver storage/use','FAIL','raw сохранён, typed decision path теряет — F02'),
('13','Null vs zero','PASS','source null not replaced0; gates/clamp объяснены'),
('14','Все derived metrics','PASS','formulas and120 reconstructions; normalized round4 ≠ observed precision'),
('15','Oracle1.2','PASS','trace source→current diagnostic; game semantics остаётся UNVERIFIED'),
('16','Spectre6','PASS','6.135271030802414→6; signals threshold.20'),
('17','Ruiner serialization','PASS','real local responses + current/legacy DTO tests; F03 corruption отдельно FAIL'),
('18','Оба REST маршрута live авторизованно','BLOCKED','local200 и auth401 реальны; authenticated200 только существующие isolated tests'),
('19','Quality/status/limitations','FAIL','семантика охватов исследована, но Timeline confirmed противоречит actor/team F10; stale diagnostic F04'),
('20','Legacy reports','PASS','9057722463 projection only, unchanged DB'),
('21','P1 other sections inventory','PASS','CSV поля и draft nested; API all sections, Timeline F10 отмечен'),
('22','Backend vs source','PASS','F01–F11 classifications; отсутствующее parsed не названо потерей'),
('23','Нет production edits','PASS','scope SHA, live raw/reports unchanged, no commit'),
('24','Воспроизводимость','PASS','frozen local raw/hash, scripts, JUnit; перенос на чужую машину требует gitignored snapshots'),
('25','Findings с evidence','PASS','F01–F11, files/functions/steps/impact/minimal fixes/dependencies'),
]
qa+=table(['ID','Проверка','Результат','Основание'],[['DATA-QA-'+i,n,s,e] for i,n,s,e in checks])
qa+='''
## Не выполненные / ограниченные проверки

- Live authenticated HTTP200 и Telegram Mini App: BLOCKED отсутствующей сессией, изолированный auth-тест не заменяет это.
- Верификация первоначальных raw HTTP bytes до удаления приватных полей: UNVERIFIED; новые API ответы не могут восстановить прежний ответ.
- Причина Oracle11 assists и event-level уникальная kill participation: UNVERIFIED, полный assist журнал отсутствует. Простое число teamfight_participation1.2 не независимая верификация.
- Платные сервисы, POST parsing, новые live fetch матчей, массовый persisted reanalysis, frontend/UI/browser QA: NOT RUN, вне read-only задания.
- Реальное аварийное обновление рабочей БД: NOT RUN намеренно; F01 доказан MemorySession и UPSERT-кодом. Успех существующих408 тестов не покрывает этот инвариант, новую продуктивную регрессионную проверку следует добавить в багфиксе.
- Roshan source team2/3 без actor: synthetic _side возвращает unknown; корректная кодировка должна быть отдельно закреплена primary source/spec перед исправлением. Real snapshot подтверждает team3 для miniboss, но это не доказательство Roshan semantics. Slot0..9 vs player_slot пространство — отдельный риск, не установленная массовая порча этих20 игроков.
- Смысл team scores vs сумма personal kills второго матча не восстановлен; пользовательские счётчики не корректировались.

## Воспроизведение

Из корня dota-hub:

```sh
.venv/bin/python scripts/ri02_data01.py offline
.venv/bin/python scripts/ri02_data01.py experiments
.venv/bin/python scripts/ri02_data01.py timeline
.venv/bin/python scripts/ri02_data01_report.py
.venv/bin/python scripts/ri02_data01.py verify
.venv/bin/python scripts/ri02_data01.py validate
```

`capture` был выполнен один раз; повторная запись frozen capture запрещена самим скриптом. Он читает рабочую БД только после `SET TRANSACTION READ ONLY`, делает только GET локального API. `verifydb` повторно читает и сравнивает raw/reports, без writes. `sources` читает только публичные GitHub исходники. Не вызывать POST /analyze для повторения аудита. Raw/cal snapshots и private API/DB captures gitignored; перед переносом проверки нужен доступ к этим локальным исходникам. Не подменять их частичной test fixture.

Существующий тестовый запуск из backend:

```sh
../.venv/bin/python -m pytest -q --tb=short --junitxml=../docs/qa/ri02/data01/pytest.xml
```

TEST_DATABASE_URL должен указывать на отдельную localhost `dota_hub_test`, MIGRATION_TEST_DATABASE_URL — отдельную migration test DB. Existing checked_test_url запрещает совпадение с рабочей БД. Секреты в команды/логи не подставляются.

CSV создаётся из matrix_rows.json через bundled Artifact Tool:13,750 строк ×17 колонок, верифицирован round-trip ячеек, UTF-8 quoted CSV. Ячейки содержат диагностические данные/JSON, не выполняемые формулы. Пользователь запросил CSV, поэтому XLSX и визуальный редизайн таблицы не создавались. Для воспроизведения builder `scripts/ri02_data01_matrix.mjs` скопировать в временную папку с node_modules symlink на bundle; запустить bundled node с абсолютным root проекта аргументом. Набор dependencies берётся из load_workspace_dependencies. Пакетные директории не изменяются. Проверки структуры CSV и machine evidence сохранены рядом с отчётами.

## Шесть итоговых артефактов

1. [FIELD_MATRIX.csv](RI_02_DATA_01_FIELD_MATRIX.csv) —13750 строк, точные source paths, mappings, status/evidence.
2. [CODE_MAP.md](RI_02_DATA_01_CODE_MAP.md) — цепочка, функции, storage, HTTP и источники.
3. [MATCH_TRACE.md](RI_02_DATA_01_MATCH_TRACE.md) —20 детальных трасс, Oracle/Hoodwink/Spectre, формулы.
4. [API_CONTRACT_AUDIT.md](RI_02_DATA_01_API_CONTRACT_AUDIT.md) — DB→REST, legacy/current, auth граница.
5. [FINDINGS.md](RI_02_DATA_01_FINDINGS.md) — классифицированные дефекты, риски, рекомендации без реализации.
6. [QA_REPORT.md](RI_02_DATA_01_QA_REPORT.md) — фактические408 тестов,28 сценариев,25 критериев, ограничения.

**Итоговый статус: READY FOR QA.** DONE не присваивался. Аудит пригоден для независимой проверки, но полная исправность backend data pipeline и готовность RI к достоверным игровым выводам не подтверждены. Следующий шаг — согласование отдельных точечных багфиксов; ни один не применён этим заданием.
'''
save('RI_02_DATA_01_QA_REPORT.md',qa)
# Short machine test index is useful to check every claim against JUnit without parsing Markdown.
(E/'test_results.json').write_text(json.dumps({'summary':suite.attrib,'tests':[{'node':t.attrib['classname']+'::'+t.attrib['name'],'status':'PASS' if not list(t) else 'SEE_XML'} for t in tests]},ensure_ascii=False,indent=2)+'\n')
