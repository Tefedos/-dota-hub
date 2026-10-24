**RI-02-CAL-01-DATA / READY FOR QA.** Дата: 24.10.2026. HEAD `f222ee9dc322e98b8890ec642c9038244fe1e5a2`. Исследуется рабочее дерево с уже существующими незакоммиченными RI/PL/UI изменениями, а не чистый HEAD. Код, настройки, сохранённые матчи и прежние отчёты не изменены.

## Вердикт

**MIXED CAUSES.** Для действующих численных осей необходимые имеющиеся scalar данные поступают и преобразуются без обнаруженной потери на12 snapshots. Для20 пилотных игроков сохранённые индексы соответствуют offline replay. Полного положительного ответа всей цепочке дать нельзя: last-good raw не защищён от неудачного refresh, leaver evidence не доходит до решения, новая диагностика может навсегда остаться за старым cache key, wrapper metadata допускает противоречие с data. Объяснение Oracle требует семантики игровых счётчиков, а не ослабления guard. Неприсутствующие parsed поля второго матча — ограничение источника, а не исправляемая подстановка нулей.

Приоритеты ниже относятся к последствиям дефекта, а не к P0/P1/P2 инвентаризации полей. P0 критического искажения действующих численных оценок на этих snapshots **не найдено**. Отсутствие находки не доказывает исправность всех произвольных матчей.

## F01 — P1 — PERSISTENCE_ISSUE

| Пункт | Свидетельство |
|---|---|
| Файлы/функции | backend/app/services/match_ingestion.py:_mark_pending,_save_result; backend/app/db/repositories.py:upsert_match |
| Поле | raw_payload |
| Ожидание | Сохранить последний успешный snapshot при временной ошибке refresh. |
| Факт | PENDING, затем API_UNAVAILABLE заменяют весь raw; history нет. |
| Доказательство | experiments.json expired_good_snapshot_then_503: final_has_match=false; код UPSERT, live schema. |
| Воспроизведение | Запустить experiments; использует только MemorySession и expired copy. |
| Влияние | После сбоя нельзя восстановить исходные признаки из matches; старые analyses ещё могут остаться. На реальной БД такую потерю не провоцировали. |
| Минимальная рекомендация, НЕ реализована | Разделить последний успешный raw и состояние/ошибку попытки. Минимально не перезаписывать успешный payload pending/error, хранить fetch status отдельно. |
| Зависимости/уверенность | Нужно согласовать TTL/retry/stale политику, проверить timeout/429/404/cancel/restart и последующий success. API/формулу менять не требуется. Высокая уверенность. |

## F02 — P1 — NORMALIZATION_ISSUE

| Пункт | Свидетельство |
|---|---|
| Файлы/функции | backend/app/services/match_normalization.py:_player; models/matches.py:PlayerStat; services/performance.py:evaluate; performance_preliminary.py:select_preliminary |
| Поле | leaver_status |
| Ожидание | Сохранять явный статус источника и использовать согласованный trusted context. |
| Факт | 100/120 raw игроков имеют статус, включая0 всех20 пилотов; typed PlayerStat и RuinerReport его не несут. Production caller не передаёт leaver_context. |
| Доказательство | matrix LOST_IN_BACKEND; experiments leaver_end_to_end unchanged_report=true при замене0 на2; existing direct-context test отказывает. |
| Воспроизведение | offline + experiments; смена значения только deep copy. |
| Влияние | Подтверждённый источник может не блокировать предварительный выбор; leaver_context_unknown даже при raw0. Формула не штрафует leaver. |
| Минимальная рекомендация, НЕ реализована | Отдельно нормализовать source status/evidence, передавать контекст в предварительный выбор и сохранять provenance. |
| Зависимости/уверенность | Сначала закрепить семантику кодов/unknown/disconnect по источнику; не считать любой disconnect уходом. Модель scores менять не нужно, contract/storage version для контекста — отдельное решение. Высокая уверенность в потере. |

## F03 — P1 — API_MAPPING_ISSUE

| Пункт | Свидетельство |
|---|---|
| Файлы/функции | backend/app/api/v1/matches.py:stored; models/performance.py:RuinerReport |
| Поле | model_version/config_version/schema_version wrapper |
| Ожидание | Согласованный envelope/data или безопасный отказ. |
| Факт | wrapper model= different_model, data model=ruiner_v1 выдан HTTP200; то же для config; wrapper schema999 игнорируется и envelope schema1. |
| Доказательство | experiments stored_model_mismatch/config_mismatch/schema_mismatch; baseline200. |
| Воспроизведение | experiments на fake session без БД writes. |
| Влияние | Клиент может приписать индекс иной формуле/настройкам. На реальных20 несогласованность metadata не найдена. |
| Минимальная рекомендация, НЕ реализована | При чтении сверять модель/config wrapper с data, явно поддерживать версии wrapper; иначе REPORT_UNAVAILABLE. |
| Зависимости/уверенность | Тесты обоих GET, legacy policy, не мигрировать данные автоматически. Высокая уверенность. |

## F04 — P1 — PERSISTENCE_ISSUE

| Пункт | Свидетельство |
|---|---|
| Файлы/функции | backend/app/services/match_analysis.py:__init__,_process; performance_config.py |
| Поле | config_version/model_version/cache identity |
| Ожидание | Смена диагностической реализации должна иметь различимую ревизию и управляемую инвалидацию. |
| Факт | Oracle live не имеет counter_ratio1.2 и точного reason, новый replay имеет. source и config совпадают; existing ready branch повторно выдаст прежний report. |
| Доказательство | api_comparison: replay_vs_stored два пути, flow_config_matches_current=true; текущий source совпадает. |
| Воспроизведение | offline; сравнить сохранённый report vs текущий evaluator, ветку cache изучать read-only. POST не вызывался. |
| Влияние | Числа корректно сохранены, но RI-02-FIX диагностика не гарантированно достигает пользователя даже после повторного запроса. |
| Минимальная рекомендация, НЕ реализована | Добавить явную implementation/diagnostic revision в cache identity; отдельно разрешить адресный пересчёт после утверждения. |
| Зависимости/уверенность | Не менять веса. Определить политику версии модели/схемы и совместимости старых отчётов; тест unchanged inputs+new revision. Высокая уверенность в условии cache-hit. |

## F05 — P2 — API_DIAGNOSTIC_GAP

| Пункт | Свидетельство |
|---|---|
| Файлы/функции | backend/app/api/v1/matches.py:stored; models/match_api.py:MatchEnvelope |
| Поле | source_digest/source_fetched_at/stale |
| Ожидание | Позволять различить исторический report и текущий raw. |
| Факт | GET сравнивает report с flow, не с Match.raw_payload. Modified raw copy всё ещё HTTP200; API не показывает source digest. |
| Доказательство | experiments stored_stale_raw; actual two digests match, stale real не найден. |
| Воспроизведение | experiments; изменяется копия Match только в fake session. |
| Влияние | Потенциальное неверное понимание свежести, а не доказанная неверная арифметика старого report. |
| Минимальная рекомендация, НЕ реализована | Зафиксировать контракт historical vs current; при необходимости expose source timestamp/digest или явный stale marker в отдельной задаче. |
| Зависимости/уверенность | Требует продуктового решения, API change согласовать. Высокая уверенность в коде, риск зависит от refresh/concurrency. |

## F06 — P2 — API_DIAGNOSTIC_GAP

| Пункт | Свидетельство |
|---|---|
| Файлы/функции | backend/app/services/performance.py:compare,evaluate |
| Поле | negative_signals/positive_signals/credit |
| Ожидание | Различать continuous contribution и показанный сильный сигнал. |
| Факт | Spectre6 при negative_signals=[]; positive signal по survival/KP может не давать credit; descriptive contribution при ref0 magnitude0 не даёт credit. |
| Доказательство | MATCH_TRACE Spectre6.135271; 5/120 nonzero indexes без negative signals. |
| Воспроизведение | offline и соответствующие строки traces.json. |
| Влияние | Объяснение результата неполно, но математического дефекта нет. |
| Минимальная рекомендация, НЕ реализована | Документировать signal_threshold и credit-only метрики; при отдельном UI/API задании показывать вклад осей. |
| Зависимости/уверенность | Не менять коэффициенты ради совпадения текста с индексом; новая аналитика не нужна. EXPECTED BEHAVIOR + diagnostic gap. |

## F07 — P2 — NORMALIZATION_ISSUE

| Пункт | Свидетельство |
|---|---|
| Файлы/функции | backend/app/services/match_normalization.py:_int,_float,_player |
| Поле | invalid value vs missing |
| Ожидание | Сохранять причину отклонения malformed input. |
| Факт | Negative/string/float GPM становится null, как absent; available_fields отличает наличие usable, но не причину отказа. |
| Доказательство | experiments negative_stats,float_gpm,numeric_string_gpm; реальные P0 mapped nonnull->null =0 в12 snapshots. |
| Воспроизведение | experiments; не менять существующие fixtures. |
| Влияние | Сейчас отвергаются неподходящие типы безопасно; диагностика не отличает потерю/ошибку источника от отсутствия. |
| Минимальная рекомендация, НЕ реализована | В отдельной задаче добавить field validation diagnostics/provenance, не приводить float/string к int молча. |
| Зависимости/уверенность | Схема OpenDota GPM integer; принятие других типов не обосновано. Высокая уверенность; P2 объяснимость, не доказанная потеря валидного числа. |

## F08 — P3 — API_CONTRACT_GAP

| Пункт | Свидетельство |
|---|---|
| Файлы/функции | backend/app/integrations/opendota.py:parse_match_response; match_normalization.py |
| Поле | FOUND_FULL/source_status |
| Ожидание | Чётко понимать область completeness. |
| Факт | Empty arrays, missing hero,9 roster и duplicate slot могут получить FOUND_FULL по наличию top-level полей; дальше нормализатор/RI отдельно отвергают или ограничивают. |
| Доказательство | experiments empty_arrays,missing_hero,incomplete_roster,duplicate_slot. |
| Воспроизведение | experiments; duplicate normalization raises MatchNormalizationError. |
| Влияние | Нельзя трактовать FOUND_FULL как пригодность всех метрик, но RI не выдаёт уверенный результат по этому флагу. |
| Минимальная рекомендация, НЕ реализована | Документировать source-shape vs stats/roles/analysis quality; при будущих правках отдельные completeness dimensions. |
| Зависимости/уверенность | EXPECTED limitation текущего определения; не менять source flag без совместимости. |

## F09 — P1 — MODEL_SEMANTICS_ISSUE / SOURCE_ISSUE

| Пункт | Свидетельство |
|---|---|
| Файлы/функции | backend/app/services/performance.py:participation_assessment; match_normalization.py:_participation_counter_metric |
| Поле | Oracle KP1.2; peer participation |
| Ожидание | Сохранить наблюдение, не утверждать недоказанную долю. |
| Факт | Raw1.2 доступен арифметически, usable null; Oracle/Hoodwink остаются с одной осью и null index. |
| Доказательство | MATCH_TRACE, current replay, primary parser field mapping. |
| Воспроизведение | offline без корректировки K/D/A. |
| Влияние | Два отсутствующих индекса не вызваны потерей счётчиков. Двух support peers недостаточно для статистической нормы даже при KP available. |
| Минимальная рекомендация, НЕ реализована | Продолжать исследование event-level assist→kill или согласовать counter-ratio определение с доказательством сопоставимости; guard не снимать сейчас. |
| Зависимости/уверенность | Происхождение11 assists UNVERIFIED, полноценный event-level assist журнал отсутствует. BUG в игровой статистике источника НЕ доказан. Любое изменение оси требует новой версии/калибровки. |

## F10 — P1 — DERIVATION_ISSUE

| Пункт | Свидетельство |
|---|---|
| Файлы/функции | backend/app/services/timeline.py:_objective,analyze_timeline |
| Поле | tower event team / actor |
| Ожидание | Не выдавать уверенную противоречивую атрибуцию стороны. |
| Факт | 9051271323 time1048: raw goodguys tower1_top и player_slot2 (Radiant Death Prophet); API event.team=Dire, actors[0].team=Radiant, evidence_quality=confirmed. |
| Доказательство | timeline_checks.json real objective и actual event; live Timeline тот же event. |
| Воспроизведение | timeline action, только replay snapshot. |
| Влияние | На RI влияния нет. Timeline полагает attacker противоположным owner даже при своем actor; возможен deny. |
| Минимальная рекомендация, НЕ реализована | Отделить owner/actor, распознавать доказанный deny или помечать conflict/unknown, не назначать вражескую сторону без проверки. |
| Зависимости/уверенность | Реальный конфликт подтверждён; точная игровая причина требует replay/source semantics. Проверить deny, creep kill, unknown actor, Roshan codes2/3, slot vs player_slot. Исправление другого блока только отдельным заданием. |

## F11 — P3 — DATA_UNAVAILABLE

| Пункт | Свидетельство |
|---|---|
| Файлы/функции | backend/app/services/match_normalization.py:_events,_player |
| Поле | parsed fields 9057722463 |
| Ожидание | Не заполнять отсутствующие статистики нулями. |
| Факт | stuns/wards/positions/event arrays отсутствуют; Players extended null, Timeline unavailable. |
| Доказательство | matrix, capture, MATCH_TRACE. |
| Воспроизведение | offline, local GET. |
| Влияние | 53/120 scores не равно полноте raw;11/12 snapshots partial. |
| Минимальная рекомендация, НЕ реализована | Получать parsed evidence отдельным согласованным процессом, учитывать rate budget; POST parse не выполнялся. |
| Зависимости/уверенность | Доступность нового parsed snapshot не гарантирована. EXPECTED BEHAVIOR, не backend дефект. |


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

[Воспроизводимые свидетельства](qa/ri02/data01/) · [Матрица](RI_02_DATA_01_FIELD_MATRIX.csv) · [QA](RI_02_DATA_01_QA_REPORT.md)
