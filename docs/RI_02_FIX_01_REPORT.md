# RI-02-FIX-01 — контракт kill_participation

**Статус: IN PROGRESS.** Безопасная контрактная часть выполнена; численное восстановление индексов **BLOCKED** до подтверждения семантики превышения 100%. Коммит не создан.

## A. Исходное состояние

HEAD `f222ee9dc322e98b8890ec642c9038244fe1e5a2`. Перед работой дерево уже содержало незакоммиченный RI-04 (изменения `backend/app/api/v1/matches.py`, `backend/app/models/performance.py`, `backend/app/services/performance.py`, OpenAPI-фикстуры, ряда frontend-файлов; новые `performance_preliminary.py`, RI-04 тесты/отчёты) и отчёт RI-02-DIAG-01. Эти изменения не сброшены и не присвоены данному багфиксу. Текущее состояние подтверждено `git status --short`; из-за прежних незакоммиченных изменений обычный diff от HEAD не является чистым diff RI-02-FIX-01.

Путь: `parse_match_response()` → `matches.raw_payload` → `normalize_match_snapshot()` / `_derived()` → `PlayerStat` / `PlayerDerivedStats` → `observed()` / `RoleAwarePerformanceEvaluator.evaluate()` → `RuinerReport` → сохранённый `match_analyses` → общий `stored()` для authenticated и local-alpha GET. Исходный snapshot матча `9051271323` присутствует в локальной PostgreSQL: `source=opendota`, `status=FOUND_FULL`, получен 2026-10-23 19:19:54 UTC, score Radiant/Dire 10/45, duration 1933, mode 22, 10 игроков. Он читался без записи и без повторного обращения к OpenDota. Сохранённый отчёт ruiner имеет `model_version=ruiner_v1`.

## B. Семантика и источники

Наше поле `(kills+assists)/team_score` — **отношение счётчиков**, а не проверенная доля уникальных командных убийств. Нормализатор хранит результат арифметики с округлением до 4 знаков и статусом `available`, означающим только наличие числителя и ненулевого знаменателя. Оценщик использует неокруглённое отношение при пригодных данных. Он не использует значение выше 1 как сравнимую participation-ось, поскольку неизвестно, отражает ли оно игровые ассисты за особые события, несогласованность счётчиков или ошибку источника. Обрезания до 1 нет.

[Парсер OpenDota](https://github.com/odota/parser/blob/master/src/main/java/opendota/Parse.java#L3410-L3425) читает `m_flTeamFightParticipation`, `m_iKills`, `m_iAssists` как отдельные игровые поля. [Схема OpenDota](https://github.com/odota/core/blob/master/sql/create_tables.sql) хранит их отдельно от `radiant_score`/`dire_score`. Поэтому совпавшее в этом снимке `teamfight_participation=1.2` **не является независимой валидацией** `(1+11)/10=1.2`. [Сообщение пользователя в issue-трекере Valve](https://github.com/ValveSoftware/Dota2-Gameplay/issues/7060) фиксирует другой случай индивидуальных assists выше счёта команды, но не объясняет правило и не подтверждает сопоставимость. Несколько союзников могут получить assist на одном убийстве, что объясняет превышение **суммы** командных assists; это само по себе не доказывает индивидуальную долю выше 100%. В сохранённом снимке нет полного журнала assist→kill, поэтому долю уникальных убийств для Oracle восстановить нельзя.

Отказы оценщика разделены на: отсутствие K; отсутствие A; отсутствие team_score; team_score=0; team_score<10; превышение счётчиков, несовместимое с полным числом смертей в матче или индивидуальные kills>team_score; умеренное `K+A>team_score` с неподтверждённым смыслом. Последняя категория сохраняет исходное число, но не превращает его в оценку. Диагностическая проверка явной аномалии использует фактические смерти **всех десяти** игроков только при полном roster/deaths; это защитная классификация, не новая шкала индекса и не доказательство причин аномалии. Численные значения в диапазоне до 1 и прежний минимум team score обрабатываются как раньше.

## C. Изменения

| Файл | Изменение |
|---|---|
| `backend/app/services/match_normalization.py` | Единая функция `kill_participation_counter_ratio()` даёт неокруглённое отношение; `_derived()` через неё хранит арифметическое значение с прежним округлением/статусом. |
| `backend/app/models/matches.py` | Явно задокументировано, что derived KP — отношение счётчиков, а `available` не означает пригодность для `ruiner_v1`. |
| `backend/app/services/performance.py` | `participation_assessment()` отдельно возвращает пригодное значение, исходное отношение и точный код причины. При отказе `observed_metrics.kill_participation` остаётся `null`, а исходное число доступно как `kill_participation_counter_ratio`. Причины вместо общего `team_kills_missing_small_or_inconsistent` разделены. Сравнение peer и формула не изменены. |
| `backend/tests/test_performance_participation_contract.py` | Новые граничные, ролевые, DTO, persisted-report и оба REST GET тесты. |
| `backend/tests/test_performance_preliminary.py` | Старый численный snapshot продолжает сравниваться полностью после исключения **только** ожидаемых новых диагностических полей Oracle; сам snapshot не переписан. |
| `docs/RI_02_FIX_01_REPORT.md` | Этот отчёт. |

`ruiner_v1`, config digest, веса, minimum cohort/axes/coverage, survival/economy/impact, strict/preliminary selection и API envelope не менялись. Новые ключ `observed_metrics` и коды `reason_codes` уже допускаются текущими открытыми полями DTO, поэтому структурную версию API и математическую версию модели не повышали. Старые persisted-отчёты читаются дословно; GET не пересчитывает и не переписывает их. При возможной будущей смене численного правила потребуется **новая** версия модели и отдельная процедура анализа без скрытого изменения старых записей.

## D. Реальные расчёты до/после

Для матча `9051271323` (только read-only replay сохранённого raw):

| Player | KP raw `(K+A)/score` | KP normalized | KP observed до→после | Participation axis до→после | Error index до→после |
|---|---:|---:|---|---|---|
| Hoodwink, slot 0 | `8/10=0.8` | `0.8 available` | `0.8→0.8` | `null→null`: peer Oracle непригоден | `null→null` |
| Oracle, slot 1 | `12/10=1.2` | `1.2 available` | `null→null`; новое `counter_ratio=1.2` | `null→null`: смысл превышения не подтверждён | `null→null` |

Все значения осей ниже показаны как S/P/E/I = survival/participation/economy/impact; `—` означает отсутствие оси. Числа для чтения округлены до 4 знаков, а машинное сравнение выполнялось без округления. В колонке сигналов указаны количества `positive/negative`; **содержимое каждого сигнала** также сравнивалось и совпало. `reason_codes` совпали полностью, кроме указанной замены у Oracle.

| Slot | Index до→после | Confidence | Coverage | Оси S/P/E/I до→после | Credit | +/− signals | Missing | Reasons |
|---:|---|---|---|---|---|---|---|---|
| 0 | null→null | low→low | 0.5→0.5 | 0.5/—/—/—→то же | 3.9942→3.9942 | 2/1→2/1, без изменений | —→— | без изменений |
| 1 | null→null | low→low | 0.5→0.5 | 0/—/—/—→то же | 15→15 | 6/0→6/0, без изменений | KP→KP | `team_kills_missing_small_or_inconsistent` → `kill_participation_over_team_score_unverified`; прочие без изменений |
| 2 | 12→12 | low→low | 1→1 | 0.8462/0.0769/0/0→то же | 15→15 | 7/1→7/1, без изменений | —→— | без изменений |
| 3 | 6→6 | low→low | 1→1 | 0/0.0769/0.1083/0.0752→то же | 0→0 | 0/0→0/0 | —→— | без изменений |
| 4 | 15→15 | low→low | 1→1 | 0/0/0.1722/0.5297→то же | 0→0 | 1/1→1/1, без изменений | —→— | без изменений |
| 128 | 12→12 | low→low | 1→1 | 0/0.1389/0.2278/0.1503→то же | 0→0 | 0/2→0/2, без изменений | —→— | без изменений |
| 129 | 15→15 | low→low | 1→1 | 1/0/0/0→то же | 15→15 | 3/1→3/1, без изменений | —→— | без изменений |
| 130 | 0→0 | low→low | 1→1 | 0/0.069/—/—→то же | 15→15 | 4/0→4/0, без изменений | —→— | без изменений |
| 131 | 9→9 | low→low | 1→1 | 0/0/0.089/0.3234→то же | 0→0 | 1/1→1/1, без изменений | —→— | без изменений |
| 132 | 35→35 | low→low | 1→1 | 1/0/—/—→то же | 15→15 | 4/1→4/1, без изменений | —→— | без изменений |

Radiant preliminary остаётся `none/incomplete_player_scores`; Dire preliminary `single/slot 132/index 35/margin 20`; строгий `selection` обеих команд остаётся `no_confident_selection`. У обоих support позиции остаются `estimated`, уверенность `low`. Одной доступной оси и coverage 0.5 недостаточно при `minimum_axes=2` и `minimum_coverage=0.7`.

Независимый реальный матч `9057722463`: сохранённый raw `source=opendota`, `FOUND_PARTIAL`, получен 2026-10-23 13:37:42 UTC; duration 4349, mode 22, счёт 44/42, 10 игроков, K/D/A и командные счета присутствуют. У всех десяти `(K+A)/score <=1`. Read-only replay показал **полное равенство всех 10 player-полей** (`error_index`, confidence, coverage, axes, credit, оба списка сигналов, missing/reasons/observed) сохранённому отчёту: индексы Radiant `[50,0,0,0,42]`, Dire `[0,0,0,31,6]`. Строгие selections не изменились. Сохранённый legacy-отчёт не содержит preliminary; текущая совместимая проекция даёт Radiant group `(0,4)`, Dire single `(131)`. Это не изменение численного правила.

## E. QA

| ID | Статус | Фактический результат |
|---|---|---|
| KP-QA-01 | PASS | `6/10=0.6` пригодно; normalized/observed согласованы. |
| KP-QA-02 | PASS | `10/10=1.0` пригодно. |
| KP-QA-03 | PASS | `11/10=1.1` сохранено как raw, но ось отклонена с причиной `over_team_score_unverified`. |
| KP-QA-04 | PASS | `12/10=1.2` сохранено как raw; Oracle не теряет исходное число, но score остаётся null. |
| KP-QA-05 | PASS | `10000/10=1000` не оценивается, отдельная причина `counter_anomaly`; дополнительно проверено `kills=11` при team score 10. |
| KP-QA-06 | PASS | score=0: нет деления на ноль, причина `team_score_zero`. |
| KP-QA-07 | PASS | score=9: raw отношение доступно, ось отклонена как `team_score_small`. |
| KP-QA-08/09 | PASS | Отдельные опыты с отсутствующим `kills` и `assists`: соответственно `kills_missing` и `assists_missing`. |
| KP-QA-10 | PASS | При одном пригодном support KP у второго нет peer; participation обеих null. |
| KP-QA-11 | PASS | При двух пригодных support KP participation обеих вычисляется. |
| KP-QA-12 | PASS | Estimated position оставляет confidence low даже с двумя осями. |
| KP-QA-13 | PASS | Одна доступная ось и coverage 0.5 оставляют индекс null. |
| KP-QA-14 | PASS | Две оси и coverage 1 дают число по существующей формуле на синтетических данных. |
| KP-QA-15 | PASS | Замена только Oracle KP в синтетическом снимке меняет доступность оси Hoodwink. Числа не приписываются реальному матчу. |
| KP-QA-16 | PASS | Другие Radiant core не меняются. |
| KP-QA-17 | PASS | Все Dire players не меняются. |
| KP-QA-18 | PASS | Preliminary использует фактические индексы; для реального матча selection не меняется. |
| KP-QA-19 | PASS | Строгий selection сохраняет отказ при low confidence. |
| KP-QA-20 | PASS | Старый persisted report сериализуется/читается без подмены; GET не пишет в БД. |

Команды: `../.venv/bin/python -m pytest tests/test_performance_participation_contract.py tests/test_match_normalization.py tests/test_performance.py tests/test_performance_preliminary.py -m 'not postgres' -q --tb=short` — PASS; `../.venv/bin/python -m pytest tests/test_performance_participation_contract.py -m postgres -q --tb=short` — PASS, authenticated и local-alpha REST; `../.venv/bin/python -m pytest -q --tb=short` — **PASS, 408 тестов**; `../.venv/bin/python -m mypy app/models/matches.py app/services/match_normalization.py app/services/performance.py tests/test_performance_participation_contract.py tests/test_performance_preliminary.py` — PASS; `git diff --check` — PASS. Единственное предупреждение полного набора: существующая `StarletteDeprecationWarning` для `httpx`/`starlette.testclient`. Снимки исходных данных и сохранённые отчёты не обновлялись; запросов к OpenDota не было.

## F. Риски и ограничения

- Происхождение 11 ассистов Oracle неизвестно. Нужно подтвердить события assist→kill либо формальную спецификацию счётчиков. `teamfight_participation=1.2` не решает вопрос независимо.
- Support cohort содержит только двух игроков, позиции 4/5 лишь estimated. Даже при валидных значениях покрытие не равнозначно надёжной популяционной норме.
- Внешней игровой калибровки индекса нет; диагностическая классификация явной аномалии использует наблюдаемые смерти как sanity check, а не статистическую норму.
- Старые сохранённые отчёты остаются с прежним кодом причины до **явно инициированного** нового анализа; GET их не переписывает. При будущем изменении численного правила нужна новая версия модели и отдельный анализ последствий.
- Отсутствие event-level assist-журнала блокирует достоверную долю уникальных убийств. Новый подсервис здесь не создавался.

## G. Итог

Исправлена контрактная неясность: исходное отношение счётчиков больше 1 больше не исчезает из нового отчёта, а непригодность для оси получает точную причину. Уточнены причины пропуска других входов. Численное поведение не менялось, индексы Hoodwink и Oracle остаются `null` **обоснованно при текущих данных**, а зависимость их peer-сравнения подтверждена. Версия `ruiner_v1` сохранена; новых коэффициентов и специальных правил для матча/героев нет. Полный численный багфикс остаётся **BLOCKED**, задача RI-02-FIX-01 — **IN PROGRESS** до согласования смысла метрики или появления проверяемых событий.

Следующее решение: (1) считать `(K+A)/score` отношением счётчиков с допуском >1 и доказать его сопоставимость для peer-оси, или (2) считать participation долей **уникальных** убийств и получать event-level доказательство. Ни один путь не выбран только ради появления числа.
