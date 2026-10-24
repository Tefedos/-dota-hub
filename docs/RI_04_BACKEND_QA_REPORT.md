# RI-04 — Backend QA-аудит предварительного выбора

Дата: 23 октября 2026 г. Вердикт: **IN PROGRESS**. Исходники приложения не исправлялись; подтверждён один дефект целостности сохранённого результата. Статус DONE не присваивался.

## A. Реализация и ревизия

Текущий Git HEAD: `f222ee9dc322e98b8890ec642c9038244fe1e5a2` (`main`). RI-04 находится в **незакоммиченных изменениях рабочего дерева** поверх этого HEAD; поэтому HEAD сам по себе не содержит аудируемую реализацию. Перед аудитом в рабочем дереве уже находились файлы RI-01 и RI-04, UI и тесты. В этом аудите добавлены только `backend/tests/test_performance_preliminary_qa.py`, `backend/tests/fixtures/performance/9051271323_live_ri04_envelope.json`, пояснение к новой фикстуре в `backend/tests/fixtures/performance/README.md` и этот отчёт. Production-код, UI, бот, существующие тесты и рабочие данные не менялись.

Фактические точки:

| Файл и строки | Функция / ответственность |
|---|---|
| `backend/app/services/performance_preliminary.py:15-75` | `select_preliminary(players, team, leaver_context=None)` — чистый выбор по готовым `error_index` |
| `backend/app/services/performance_preliminary.py:78-85` | `project_preliminary(report)` — добавление поля отсутствующим legacy-отчётам только в памяти |
| `backend/app/services/performance.py:51-65` | `select_team` — существующий строгий выбор; в аудируемом diff не изменён |
| `backend/app/services/performance.py:72-220` | `RoleAwarePerformanceEvaluator.evaluate`; число/оси/сигналы рассчитываются прежде RI-04; вызов `select_preliminary` на строках 205–211 отдельно для Radiant и Dire |
| `backend/app/models/performance.py:45-94` | конечные `PreliminaryReason`, строгий `PreliminarySelection`, nullable `TeamPerformanceReport.preliminary_selection` |
| `backend/app/services/match_analysis.py:216,240-259` | единый pipeline вызывает `analyze_performance`, сохраняет `report.model_dump(mode='json')` в существующую строку секции |
| `backend/app/api/v1/matches.py:95-109,134-136` | `stored` десериализует RuinerReport, проецирует старые записи и выдаёт GET `/api/v1/matches/{match_id}/ruiner` |
| `backend/app/api/v1/local_alpha.py:15-34` | тот же `stored` для локального read-only GET |
| `frontend/src/features/matches/RuinerSection.tsx:29-57` | приоритет подтверждённого `selection` над `preliminary_selection` реализован в представлении, а не backend; frontend в этом аудите не изменялся |

Алгоритм проверяет ровно пять различных слотов правильной команды (0–4 или 128–132), пять разных положительных hero_id, числовые индексы 0–100, положительный максимум, отрицательный сигнал у **каждого** игрока с максимальным индексом, отсутствие блокирующих reason codes и подтверждённого leaver. `null` даёт `none` до сортировки. Сортировка: индекс по убыванию и слот только для детерминированного порядка. Отрыв `highest-second ≥15` даёт `single`; при меньшем отрыве `group` содержит всех с `index>0` и `highest-index<15`. При `none` числовых полей не выдаётся. `low` допускается и сохраняется. Радиант и Дайр вычисляются независимо. Входные `PlayerPerformance` не мутируются.

`leaver_context`: внутренний доверенный аргумент `Mapping[int, bool | None]`; `True` блокирует, `False` явно подтверждает отсутствие выхода, пропуск/`None` даёт `leaver_context_unknown`. Рабочий pipeline не передаёт его: достоверной информации о leaver нет. Тест с явно заданным контекстом проверяет ветвление функции; это **не** end-to-end поддержка leaver.

Версия `ri_preliminary_v1` и порог 15 находятся внутри `PreliminarySelection`. Основные `model_version=ruiner_v1`, `config_digest`, строгие `threshold=70`, `minimum_margin=15` не изменились. Новая версия не увеличивает номер persisted schema/FLOW_VERSION; совместимость достигается nullable полем и проекцией при чтении. При уже сохранённом ненулевом `preliminary_selection` проекция оставляет его как есть. Это и создаёт обнаруженный ниже риск целостности.

## B. Результаты проверок

Все RI-QA-01…12 **реально выполнены** изолированными тестами. Искусственные индексы ниже применены **только к функции выбора**; они не являются результатами матчей или проверкой игровой калибровки.

| ID | Сценарий | Ожидание | Факт | Статус |
|---|---|---|---|---|
| RI-QA-01 | 70,50,20,0,0 | single, слот 0, отрыв 20 | single, `[0]`, 70/20 | PASS |
| RI-QA-02 | 50,35,10,0,0 | single на границе 15 | single, `[0]`, 50/15 | PASS |
| RI-QA-03 | 50,36,10,0,0 | group 2, отрыв 14 | group `[0,1]`, 50/14 | PASS |
| RI-QA-04 | 50,45,40,20,0 | group 3 | group `[0,1,2]`, 50/5 | PASS |
| RI-QA-05 | 50,50,10,0,0 | group 2, равенство | group `[0,1]`, 50/0 | PASS |
| RI-QA-06 | 0,0,0,0,0 | none | none, `all_indices_zero`, значения null | PASS |
| RI-QA-07 | 50,40,null,0,0 | none | none, `incomplete_player_scores`, значения null | PASS |
| RI-QA-08 | 50,20,10,0,0; у первого нет negative_signals | none | none, `leader_signals_missing` | PASS |
| RI-QA-09 | 50,36,35,0,0 | group `[50,36]` | group `[0,1]`, 50/14 | PASS |
| RI-QA-10 | 50,36,36,0,0 | group `[50,36,36]` | group `[0,1,2]`, 50/14 | PASS |
| RI-QA-11 | 50,34,10,0,0 | single, отрыв 16 | single `[0]`, 50/16 | PASS |
| RI-QA-12 | 50,49,48,47,46 | group 5 | group `[0,1,2,3,4]`, 50/1 | PASS |

| ID | Дополнительный сценарий | Ожидание | Факт | Статус |
|---|---|---|---|---|
| N-01 | 4 участника | none/incomplete_team | совпало | PASS |
| N-02 | повтор/неверный слот, сторона, hero_id | none/invalid_roster | совпало | PASS |
| N-03 | -1, 101, NaN, bool вместо индекса | none/invalid_player_scores | совпало на функции; Pydantic дополнительно запрещает их в обычном JSON | PASS |
| N-04 | все игроки low | выбор возможен, confidence low | совпало | PASS |
| N-05 | unknown / estimated роли | соответственно roles_unknown / roles_unconfirmed | совпало | PASS |
| N-06 | равный максимум и один лидер без сигнала | none/leader_signals_missing | совпало | PASS |
| N-07 | участник группы с положительным индексом без отображаемого сигнала | входит, если у лидера сигнал есть | совпало | PASS |
| N-08 | trusted confirmed leaver / unknown context | none/confirmed_leaver; без контекста выбор + ограничение | совпало для **внутренней функции** | PASS |
| N-09 | рабочий OpenDota → достоверный leaver-status | специальное правило должно использовать подтверждённые данные | поле отсутствует в нормализованном pipeline | BLOCKED |
| N-10 | blocker по reason_code | none/blocking_player_context | совпало | PASS |
| N-11 | 32 параллельные чистые проекции для двух сторон | без взаимного влияния и изменения результата | совпало | PASS |
| N-12 | семантически противоречивый persisted result | отклонение или безопасная коррекция | API возвращает противоречие; 2 теста помечены xfail | FAIL |

Тестовые `reason_codes` проверены по фактическому первому коду и ограничениям. Все 14 литеральных кодов определены в DTO и локализованы в UI. `roles_unconfirmed` не появляется при всех подтверждённых позициях в штатном evaluator; `confidence=medium` при подтверждённых ролях и достаточных осях подтверждён existing test. Противоречивый сохранённый объект остаётся возможным, см. дефект 01.

### Фактический сохранённый `9051271323`

Read-only локальный GET и зафиксированная копия `backend/tests/fixtures/performance/9051271323_live_ri04_envelope.json`:

| Команда | Слоты и индексы | Итог/причины | Статус |
|---|---|---|---|
| Radiant | 0=null, 1=null, 2=12, 3=6, 4=15 | `none`, `[]`, leader/highest/margin=null, confidence low; `incomplete_player_scores`, `roles_unconfirmed`, `leaver_context_unknown` | PASS |
| Dire | 128=12, 129=15, 130=0, 131=9, 132=35 | `single`, `[132]`, leader=132, highest=35, margin=20, confidence low; `highest_relative_index`, `roles_unconfirmed`, `leaver_context_unknown` | PASS |

Все 10 позиций имеют `evidence=estimated`; строгий выбор обеих команд остаётся `no_confident_selection`. Функция на игроках из сохранённого JSON воспроизводит оба результата. В более старой регрессионной фикстуре `backend/tests/fixtures/draft/9051271323/evidence.json` **другая полнота данных и другие индексы**; она используется только для сравнения формулы с `docs/audits/9051271323-ruiner-v1.json`, а не для утверждения о текущем API.

## C. API, сохранение и совместимость

В `data.teams.radiant` и `data.teams.dire` есть отдельное `preliminary_selection`; прежний `selection` сохранён. Типы — Literal status/version/confidence, реальные player_slots, nullable лидер/индекс/отрыв, массив reason_codes. Новый отчёт сериализуется через `model_dump(mode='json')` в прежнюю строку секции. Старый JSON без поля проходит `RuinerReport.model_validate_json`: внутреннее поле сначала `None`, затем GET явно выполняет `project_preliminary`, так что отсутствие поля не выдается за `status=none`. Два последовательных authenticated GET одного legacy-отчёта возвращают одинаковую проекцию, без перезаписи JSON/computed_at и без повторного вызова provider. Проверены отдельно локальный GET существующего реального матча и authenticated API на изолированной тестовой базе. У соседних endpoints предварительное поле не появилось.

Пример реально полученного ответа Dire 9051271323:

```json
{"status":"single","player_slots":[132],"leader_slot":132,"highest_index":35,"margin":20,"confidence":"low","reason_codes":["highest_relative_index","roles_unconfirmed","leaver_context_unknown"],"projection_version":"ri_preliminary_v1","minimum_margin":15}
```

Это `data.teams.dire.preliminary_selection`; полный envelope сохранён в новой QA-фикстуре. Radiant возвращает JSON `null`, а не 0, в трёх соответствующих полях. В текущем API нет дополнительных запросов OpenDota при GET; при новом анализе вычисление происходит над уже готовыми объектами игроков. Кэширующий integration test проверяет число вызовов provider и отсутствие новой записи. Изолированный тест concurrent вызовов функции проверяет детерминизм двух команд, но не является нагрузочным тестом многоматчевого PostgreSQL pipeline.

## D. Регрессия `ruiner_v1` и приоритет

`git diff --unified=0 -- backend/app/services/performance.py` показывает только новый импорт и добавление `preliminary_selection` при сборке `TeamPerformanceReport`. Конфигурация `backend/app/services/performance_config.py`, вычисление `observed`, `compare`, осей, credit, `error_index`, confidence и `select_team` не изменены. Тест `test_9051271323_all_existing_fields_remain_identical` удаляет только новое поле и сравнивает **весь** отчёт со старым сохранённым baseline: совпадают индексы, оси, кредит, сигналы, missing_metrics, evidence_coverage, строгие selection/пороги и digest. Проверка со сменой победителя, draft и статистики противника находится в `backend/tests/test_performance.py:179` и прошла в полной регрессии; новая проверка независимости стороны — `test_winner_opponents_and_match_id_do_not_change_selection`. Реальный live-отчёт не сопоставлялся с сырым OpenDota до RI-04: подходящего baseline именно для **этой более полной локальной записи** нет.

Backend возвращает и `selection`, и `preliminary_selection`. Приоритет для пользователя задан в `frontend/src/features/matches/RuinerSection.tsx:29-57`: `selected` показывает только строгий результат; иначе single/group/none. Отдельный frontend-тест этого приоритета прошёл в `npm test -- src/features/matches/RuinerSection.test.tsx` (20/20). Это проверка компонента в jsdom; реальный Telegram Mini App/WebView в ходе backend-аудита не запускался.

Итоговые команды и результаты:

```sh
# из dota-hub/backend
../.venv/bin/python -m pytest --tb=short
# 382 passed, 2 xfailed, 1 StarletteDeprecationWarning
../.venv/bin/python -m pytest tests/test_performance_preliminary_qa.py -q --tb=short
# 14 passed, 2 xfailed
../.venv/bin/python -m mypy app tests/test_performance_preliminary.py tests/test_performance_preliminary_api.py tests/test_performance_preliminary_qa.py
# 51 source files, no issues
# из dota-hub/frontend
npm test -- src/features/matches/RuinerSection.test.tsx
# 20 passed
# из dota-hub
curl --fail --silent http://127.0.0.1:8000/api/v1/local-alpha/matches/9051271323/ruiner
git diff --unified=0 -- backend/app/services/performance.py
git diff --check
```

Два `xfail` — задокументированные **непройденные** проверки дефекта ниже; их нельзя считать PASS. Отдельная тестовая БД `dota_hub_test` изолирована от рабочей. Старый warning относится к Starlette/httpx. Полный `mypy` по репозиторию ранее имел три не связанных с RI-04 ошибки аннотации в `tests/test_draft_alpha_bugfix.py`; в этом аудите он повторно не запускался. Отсутствие повторного запуска полного frontend-suite отмечено: проверен релевантный компонент, ранее он проходил 57 тестов в рамках реализации RI-04.

## E. Обнаруженные проблемы

### RI04-QA-DEFECT-01 — P2, подтверждённый дефект целостности сохранённого результата

**Как воспроизвести:** взять валидный сохранённый RuinerReport (тестовый legacy fixture 9057722463), в `data.teams.radiant.preliminary_selection` поставить `confidence="medium"` и `reason_codes=["incomplete_player_scores"]`, оставив статус `group`, пять численных индексов и `confidence="low"` у всех пяти игроков. Выполнить DTO-десериализацию, затем `project_preliminary`; в изолированной PostgreSQL test DB — authenticated GET `/api/v1/matches/{id}/ruiner`.

**Ожидание:** противоречивое предварительное решение отклоняется или безопасно согласуется с фактическими оценками; `medium` не выдаётся при пяти `low`, а `incomplete_player_scores` не сопровождает `group` с полным набором индексов.

**Факт:** `PreliminarySelection.model_validate_json` принимает комбинацию; `project_preliminary` сохраняет её без проверки; authenticated REST возвращает HTTP 200 с `confidence="medium"`. У всех пяти игроков low. Оба доказательных теста — `xfail` (на текущем коде утверждения ожидаемого поведения не выполняются).

**Причина:** `backend/app/models/performance.py:64-83` валидирует форму DTO, но не согласованность `reason_codes` с состоянием и не видит игроков; `backend/app/services/performance_preliminary.py:78-85` доверяет любому уже присутствующему значению. `backend/app/api/v1/matches.py:99-107` после этого сериализует объект.

**Масштаб:** штатный evaluator сам вычисляет согласованные результаты; дефект воспроизводится на повреждённом/устаревшем persisted JSON. Работающий `ruiner_v1` не затронут. Риск для пользовательской достоверности достаточен, чтобы отложить независимую приёмку этого контракта до отдельного исправления.

**Рекомендация без реализации:** определить политику при противоречивом persisted `preliminary_selection` (отклонить отчёт или пересчитать проекцию из неизменных `players`, учитывая информацию о подтверждённом leaver). Добавить проверку согласованности статуса, причины, слотов, confidence и текущих игроков перед REST-выдачей. Сохранить отдельную версию проекции и не исправлять legacy JSON массовой миграцией.

### Технический долг и ограничения продукта

- Нормализованная модель не передаёт достоверный leaver-status; end-to-end правило блокировки leaver остаётся **BLOCKED**. Текущий `leaver_context_unknown` честно отражает неизвестность.
- Позиции текущего live-матча только estimated, поэтому `confidence=low` оправдана; role evidence не выводится из названия героя.
- Относительные индексы не прошли внешнюю игровую калибровку и не доказывают причинность/«вину».
- Проверка 32 потоков удостоверяет чистоту проекции, но не заменяет нагрузочный тест БД или сквозной тест одновременной обработки нескольких матчей. Последний — **NOT RUN**.
- Реальный Telegram WebView и независимая пользовательская приёмка — **NOT RUN**; local browser предыдущего этапа не равен Telegram.
- Аудируемая реализация ещё не в Git HEAD; для воспроизводимой проверки после QA нужен отдельный коммит/ревизия. Коммит в этом аудите не создавался.

## F. Оставшиеся проверки и статус

Рабочий API, полный backend-suite, DTO/legacy read, численные регрессии и unit-сценарии выполнены. Без сквозного источника leaver и real Telegram часть поведения остаётся недоступной для end-to-end подтверждения. Дефект 01 требует отдельного решения и последующего regression run.

## G. Вердикт

**IN PROGRESS.** Предварительный выбор соответствует основным условиям на штатных входах и корректно обрабатывает фактический `9051271323`; подтверждён P2-дефект согласованности уже сохранённого результата. Исправление не выполнялось согласно запрету в QA-промпте. К READY FOR QA можно вернуться после решения по этому дефекту и повторной проверки API/DTO. DONE не устанавливается.
