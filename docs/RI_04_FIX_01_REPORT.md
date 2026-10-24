# RI-04-FIX-01 — целостность сохранённого предварительного выбора

**Статус: READY FOR QA.** `DONE` не присваивался. Коммит не создавался.

## Исходное состояние и причина

Git HEAD до и после: `f222ee9dc322e98b8890ec642c9038244fe1e5a2`. До работы в дереве уже были незакоммиченные RI-04 изменения: `backend/app/api/v1/matches.py`, `backend/app/models/performance.py`, `backend/app/services/performance.py`, `backend/tests/fixtures/group_flow/contracts.json`, несколько frontend-файлов и новые `performance_preliminary.py`, тесты и отчёты RI-04. Также существовал отчёт RI-02. Эти изменения сохранены. Текущий `git status --short` приведён в выводе проверок; из-за ранее незакоммиченного RI-04 обычный `git diff --stat` показывает совокупность работ, а не чистый diff этого багфикса.

Подтверждённая причина: `PreliminarySelection` проверял форму собственного объекта, но не сверял сохранённый результат с `players` и `TeamPerformanceReport`. `project_preliminary()` оставлял любой ненулевой объект без семантической проверки; оба GET-маршрута возвращали его после DTO-десериализации. Следовательно, `group` мог содержать `confidence=medium` при пяти игроках `low`, неверные слоты и противоречивые причины.

## Политика и изменения

- `backend/app/services/performance_preliminary.py`: сохранённая проекция сопоставляется с повторно вычисленным **только из достоверных полей игроков** результатом `select_preliminary()` и с `team`, `player_slots`, `scored_players`. Совпадающий объект остаётся тем же. Legacy `preliminary_selection=null` получает прежнюю совместимую проекцию. Если сохранённый объект противоречив, возвращается `none` с пустыми слотами, `leader_slot/highest_index/margin=null`, фактической уверенностью и `stored_projection_inconsistent`. При утраченном leaver-контексте лидер не восстанавливается по индексам. Согласованный сохранённый отказ `confirmed_leaver` остаётся отказом как при частично, так и при полностью известном контексте. Сохранённый JSON не изменяется.
- `backend/app/models/performance.py`: новый диагностический код добавлен в конечный набор `PreliminaryReason`; версия `ri_preliminary_v1` и поля/контракты индекса сохранены.
- `frontend/src/features/matches/ruiner.ts`: добавлена пользовательская русская фраза для нового кода, чтобы UI не показывал сырой enum. Верстка и логика вкладки не менялись.
- `backend/tests/fixtures/group_flow/contracts.json`: обновлён снимок OpenAPI только для нового значения enum.
- `backend/tests/test_performance_preliminary_qa.py`: два доказательных `xfail` переведены в PASS; добавлены семантические, legacy, leaver, authenticated REST и local-alpha REST проверки.

Формула `ruiner_v1`, веса, пороги строгого `selection`, `error_index`, `positive_credit`, сигналы, оси, coverage, envelope и сохранённые отчёты не менялись. `backend/app/api/v1/matches.py` и `backend/app/api/v1/local_alpha.py` этим багфиксом не редактировались: оба вызывают общий `stored()`, в котором уже применялся `project_preliminary()`. GET не запускает анализ и не вызывает OpenDota; тест проверяет неизменность сохранённого payload и детерминированность повторной выдачи.

## FIX-QA

| ID | Результат | Доказательство |
|---|---|---|
| 01 | PASS | Прежний `xfail`: сохранённая `medium` при пяти `low` заменяется на `none/low`, проверено также через authenticated и local-alpha REST. |
| 02 | PASS | `group` с `incomplete_player_scores` при пяти рассчитанных индексах становится диагностическим `none`. |
| 03 | PASS | Структурно допустимый `single` с заявленным margin 15, когда фактический отрыв 8, не выдаётся. |
| 04 | PASS | Сохранённая `group` не выдаётся, если фактический отрыв после изменения игрока ≥15. |
| 05 | PASS | Слот другой команды в сохранённом `single` отвергается; противоположная команда не меняется. |
| 06 | PASS | Несовпадение `leader_slot` и `player_slots` отклоняется DTO; REST возвращает 503 `REPORT_UNAVAILABLE`, а не противоречивый HTTP 200. |
| 07 | PASS | При `error_index=null` у одного игрока сохранённый `single` заменяется безопасным `none`, без подстановки нуля. |
| 08 | PASS | Согласованный сохранённый результат возвращается без изменения. |
| 09 | PASS | Legacy-отчёт без поля проецируется как прежде; отдельный REST-тест проходит. |
| 10 | PASS | Повторный GET даёт тот же JSON; `project_preliminary()` идемпотентен. |
| 11 | PASS | Радиант и Dire сверяются отдельно; противоположная команда не меняется. |
| 12 | PASS | Сохранённый согласованный отказ `confirmed_leaver` не превращается в лидера, проверены частичный и полный leaver-контекст. |
| 13 | PASS | Результат, зависевший от полного `leaver_context={False...}`, после утраты этого контекста не восстанавливается как `single/group`; возвращается `none` и `leaver_context_unknown`. |

Дополнительно PASS: неподдерживаемая `projection_version` отвергается DTO и REST ответом 503; другие структурно неверные объекты тоже не выдаются как валидные. При повреждении самого DTO возврат `none` невозможен до десериализации, поэтому весь раздел безопасно получает `REPORT_UNAVAILABLE`. Это оставшееся ограничение политики read-time repair.

## Фактические проверки

- `../.venv/bin/python -m pytest -q --tb=short` из `backend/`: **PASS, 394 теста**, включая отдельную PostgreSQL тестовую БД, authenticated и local-alpha REST. Единственное предупреждение: существующая `StarletteDeprecationWarning` о `httpx`/`starlette.testclient`.
- `../.venv/bin/python -m mypy app/models/performance.py app/services/performance_preliminary.py tests/test_performance_preliminary_qa.py`: **PASS**, ошибок нет.
- `npm test -- --run src/features/matches/RuinerSection.test.tsx` из `frontend/`: **PASS, 21 тест** (локализация нового кода включена в проверку всех reason codes).
- `git diff --check`: **PASS**. Финальный diff проверен на изменения вне перечисленных файлов; непредусмотренных правок от FIX-01 нет.

Оставшийся долг: достоверный leaver-контекст пока не сохраняется отдельно, поэтому противоречивый старый выбор нельзя безопасно восстановить как лидера даже при полных индексах. Новая причина в локализации frontend добавлена; отдельный редизайн не нужен. Не выполнялись миграции и массовый пересчёт сохранённых отчётов.
