# RI-04 — Предварительный лидер по индексу ошибок

Статус: **READY FOR QA**. Независимая QA-приёмка и DONE не присваивались.
Дата: 23 октября 2026 года.

## A. Исходное состояние

HEAD до работы и при сдаче: `f222ee9dc322e98b8890ec642c9038244fe1e5a2`, ветка `main`. `git diff f222ee9dc322e98b8890ec642c9038244fe1e5a2 --stat` до реализации был пуст. Единственный исходный untracked-файл — `docs/RI_01_AUDIT_REPORT.md`; он сохранён без изменений. Новый коммит и push не выполнялись.

Прочитаны RI-01 и `/Users/artemfedoseev/Downloads/Dota_Hub_Master_Plan_v0_1.md`. Актуальный промпт RI-04 уточняет прежнюю задачу мастер-плана: строгий выбор сохраняется, добавляется отдельный предварительный вывод.

Архитектура соответствует аудиту: OpenDota → snapshot → нормализация → `RoleAwarePerformanceEvaluator.evaluate` → JSON-отчёт в PostgreSQL → read-only REST → React. `select_team` остаётся строгим выбором. GET читает сохранённый отчёт и не инициирует анализ. Общий evaluator также используется ботом. Достоверного leaver-контекста нормализация не предоставляет.

Необходимые изменения ограничены RI: отдельная проекция индексов, расширение DTO и OpenAPI, подключение при сборке/чтении отчёта, UI RI и передача ему имеющихся данных Players по слотам. Миграции, ingestion, другие анализаторы и конфигурация ruiner_v1 не менялись.

## B. Backend и контракт

Изменены:

- `backend/app/models/performance.py` — строгий `PreliminarySelection`, конечный `PreliminaryReason`, nullable поле `TeamPerformanceReport.preliminary_selection`.
- `backend/app/services/performance.py` — импорт и вызов предварительного выбора при сборке команды; формула и `select_team` неизменны.
- `backend/app/api/v1/matches.py` — проекция отсутствующего поля после десериализации RuinerReport. Единая функция `stored()` обслуживает authenticated и local-alpha GET.
- `backend/tests/fixtures/group_flow/contracts.json` — совместимое расширение OpenAPI snapshot только TeamPerformanceReport и нового DTO.

Созданы:

- `backend/app/services/performance_preliminary.py` — `select_preliminary`, `project_preliminary`.
- `backend/tests/test_performance_preliminary.py` — 38 unit/regression cases.
- `backend/tests/test_performance_preliminary_api.py` — 2 PostgreSQL/API cases.
- `backend/tests/fixtures/performance/9057722463_ruiner_legacy.json` — фактический сохранённый RI-отчёт, без новых полей.
- `backend/tests/fixtures/performance/README.md` — происхождение и границы применения фикстуры.

### Семантика

Функция принимает пять уже рассчитанных игроков **одной** команды. Проверяет слоты 0–4 / 128–132, сторону, наличие пяти уникальных положительных hero_id и числовых индексов 0–100. Неполные/невалидные входы не превращаются в нули. Максимальный индекс должен быть положительным; все игроки с равным максимумом должны иметь negative_signals. У остальных участников группы отсутствие отображаемого сигнала допустимо.

Отрыв ≥15 даёт `single`. При отрыве <15 в `group` входят **все** положительные индексы строго ближе 15 к максимуму. Слот используется только для устойчивого порядка равных участников, не для назначения лидера. confidence — минимальный фактический уровень среди пяти игроков; low не препятствует предварительному результату. Роли, weights, positive_credit, evidence_coverage и исходные сигналы не пересчитываются.

При `none` player_slots пуст, leader_slot/highest_index/margin равны null: сравнение не признано допустимым. При ненулевом статусе highest_index — реальный максимум, margin — разница первых двух. Строгий DTO проверяет согласованность статусов, слотов, чисел, отрыва и конечного списка причин.

Достоверный `leaver_context` — только внутренний аргумент `Mapping[slot, bool | None]`: True подтверждает leaver, False подтверждает отсутствие leaver, None/отсутствие означает неизвестность. Любой подтверждённый leaver в команде блокирует предварительный выбор. Значение False не придумывается. Текущий pipeline аргумент не передаёт: неизвестность явно отражается в каждом результате. Подключение реального источника отложено; правило протестировано на явно заданных входах.

### Конечный список reason_codes

| Код | Причина / условие |
|---|---|
| highest_relative_index | Единственный лидер, отрыв ≥15 |
| close_scores | Группа положительных индексов на расстоянии <15 |
| incomplete_team | Количество участников не равно пяти |
| invalid_roster | Неверные/повторные слоты, сторона, отсутствующий/повторный hero_id |
| incomplete_player_scores | Хотя бы один null |
| invalid_player_scores | Нечисловой/нецелочисленный или выходящий за 0–100 индекс |
| all_indices_zero | Все пять индексов равны нулю |
| leader_signals_missing | Хотя бы один игрок с максимальным индексом без negative_signals |
| confirmed_leaver | Есть достоверно заданный leaver |
| invalid_leaver_context | Неверный тип признака или слот вне этой команды |
| blocking_player_context | Сохранённый диагностический blocker: unsupported_game_mode, short_or_unknown_duration, incomplete_team, conflicting_positions или insufficient_data |
| roles_unknown | У части игроков позиция не определена |
| roles_unconfirmed | Все позиции заданы, но часть имеет estimated evidence |
| leaver_context_unknown | Нет полного достоверного leaver-контекста |

Первая причина описывает результат/отказ; затем в устойчивом порядке добавляются ограничения ролей и leaver. У всех кодов есть локализация и тестовое покрытие. При смешении неизвестных и оценённых ролей выдаётся общее roles_unknown.

### Совместимость, сохранение и версии

`model_version=ruiner_v1`, config_digest, envelope schema_version=1, FLOW_VERSION и SECTION_VERSIONS сохранены: это дополнение проекции, а не изменение формулы. Новое поле содержит собственную `projection_version=ri_preliminary_v1` и фиксированный `minimum_margin=15`, независимый от строгого `selection_margin`.

Новые расчёты сохраняют поле штатным JSON-сохранением. Старые отчёты без поля/с null валидируются, получают предварительный результат **в памяти при GET**. Запись, computed_at и кэш не перезаписываются. Уже сохранённое предварительное значение сохраняется, включая отказ по подтверждённому leaver. Массовой миграции нет. API-тесты подтверждают round-trip, два одинаковых чтения, отсутствие нового fetch при cache hit и неизменность старой записи. При будущих изменениях логики необходима новая версия проекции и явное решение о совместимости; это не обновление ruiner_v1.

Существующие `selection`, `summary`, `players`, все scores/confidence/signals/missing_metrics/limitations сохранены. Бот использует общий расширенный отчёт, но его текстовые уведомления остались прежними; отправка в Telegram не выполнялась.

### Фактический API-ответ 9057722463

GET существующего локального отчёта после перезапуска API, без OpenDota fetch:

```json
{
  "radiant": {
    "projection_version": "ri_preliminary_v1", "minimum_margin": 15,
    "status": "group", "player_slots": [0, 4], "leader_slot": null,
    "highest_index": 50, "margin": 8, "confidence": "low",
    "reason_codes": ["close_scores", "roles_unknown", "leaver_context_unknown"]
  },
  "dire": {
    "projection_version": "ri_preliminary_v1", "minimum_margin": 15,
    "status": "single", "player_slots": [131], "leader_slot": 131,
    "highest_index": 31, "margin": 25, "confidence": "low",
    "reason_codes": ["highest_relative_index", "roles_unknown", "leaver_context_unknown"]
  }
}
```

Здесь показаны `data.teams.<team>.preliminary_selection`. Полный фактический envelope: `docs/qa/ri04/9057722463_api.json`. После удаления только нового поля весь декодированный envelope совпал с ответом до RI-04, включая analyzed_at и прежние индексы.

## C. Frontend

Созданы `frontend/src/features/matches/RuinerSection.tsx`, `RuinerSection.css`, `ruiner.ts`, `RuinerSection.test.tsx`. Изменены `SectionContent.tsx`, `contract.test.tsx`, `frontend/src/pages/MatchReportPage.tsx`.

Существующая вкладка открывает RI-компонент. Переключатель показывает пять игроков выбранной стороны. Приоритет: строгий team.selection → preliminary single/group → none; общий summary не используется для подмены командного результата. На frontend нет собственного расчёта лидера, разницы или состава группы.

Используются настоящие имена и изображения из существующего Players API, связываемые через player_slot с проверкой hero_id. Данные привязаны к текущему Match ID. При недоступном каталоге/имени показывается честная заглушка героя/участника, без угадывания роли. Общий HeroPortrait переиспользован без изменений.

Single показывает индекс, отрыв, фактическую уверенность и оговорку о причинности; group одинаково выделяет всех участников; none не выделяет случайного игрока. Строгий выбор не дублируется предварительным. В каждой карточке есть confidence, количество сигналов, раскрытие value/reference/text/типа/нормализованной силы. Missing metrics, причины и достоверность роли локализованы. Coverage подписан как покрытие взвешенных отрицательных осей, не полнота всех данных. Ограничения отчёта и envelope объединены без дублей в свёрнутое раскрытие. Новых библиотек и глобальной темы нет.

Скриншоты фактического UI:

- `docs/qa/ri04/9057722463_radiant_1280.png` — desktop group.
- `docs/qa/ri04/9057722463_dire_1280.png` — desktop single.
- `docs/qa/ri04/9057722463_radiant_390.png` — mobile group.
- `docs/qa/ri04/9057722463_dire_390.png` — mobile single.
- `docs/qa/ri04/9057722463_dire_details_390.png` — раскрытые сигналы и ограничения.

## D. Реально выполненные проверки

| Проверка | Статус | Результат |
|---|---|---|
| Новые backend unit/regression | PASS | 38 cases: RI-QA-01…10, границы 14/15/16, ties, 2–5 участников группы, null, нули, invalid roster/scores, лидер без сигналов, известный/неизвестный leaver, роли/confidence, детерминизм, строгий выбор |
| Новые PostgreSQL/API | PASS | 2 cases: новый и legacy отчёт, сохранение/чтение, cache hit без fetch, сохранение старых полей и timestamps, соседние endpoints |
| Полный backend suite | PASS | 368 passed, 1 существующее StarletteDeprecationWarning; из них 40 новых, 328 регрессионных |
| Новые frontend | PASS | 20 RI component cases + 1 page loading/empty/error case |
| Полный frontend suite | PASS | 57 passed: 21 новых, 36 регрессионных |
| TypeScript / production build | PASS | `tsc --noEmit`, Vite build |
| mypy app + новые тесты | PASS | 50 файлов без ошибок |
| Полный mypy | FAIL, ранее существовавшее | 3 ошибки аннотации `real_report` в `tests/test_draft_alpha_bugfix.py:18,26,49`; Draft не изменён. Ограничение отмечалось ещё в ALPHA_PLAYERS_BACKEND_REPORT |
| Старые численные результаты 9051271323 | PASS | Replay существующего snapshot сравнивается с прежним полным ruiner JSON за исключением нового поля; индексы, оси, credit, confidence, selection, digest идентичны |
| Старый реальный API 9057722463 | PASS | Все прежние поля envelope идентичны; group [0,4] / single [131] соответствуют промпту |
| Смена победителя / независимость команд | PASS | Новые и существующие тесты сохраняют результат своей команды при изменении исхода и статистики соперников |
| Browser desktop / mobile | PASS | Chrome, 1280/320/360/375/390 CSS px, обе стороны; по пять игроков, портреты загружены, scrollWidth=innerWidth, кнопки ≥44px |
| Browser smoke на других сохранённых матчах | PASS | 9051271323: Radiant none, Dire single slot132; 8888765469: Radiant group [0,3], Dire single slot128. Это фактические локальные отчёты, не синтетическая group_flow-фикстура |
| Browser детали / ограничения / длинное имя | PASS | Раскрытия работают; проверка длинного имени выполнена временной заменой DOM-текста только в QA; production/API не подменялись |
| Реальный Telegram Mini App | BLOCKED | Нет настроенного тестового Telegram-окружения; локальный Chrome не эквивалентен Telegram WebView. Жесты внутри Telegram требуют независимой проверки |
| Публикация / отправка сообщений боту | NOT RUN | Не входят в эту реализацию |

Первый прогон выявил ожидаемо устаревший OpenAPI snapshot; обновлены только добавленные схемы. Также исправлены аннотации нового кода и двусмысленный frontend test query для двух одинаковых численных строк. В итоговых функциональных прогонах ошибок нет. JSON измерений браузера: `docs/qa/ri04/browser_checks.json`. Скриншоты просмотрены после генерации.

Команды (если не оговорено иначе — из `dota-hub/`):

```sh
git status --short
git rev-parse HEAD
git diff f222ee9dc322e98b8890ec642c9038244fe1e5a2 --stat
git diff --check
# из backend/
../.venv/bin/python -m pytest --tb=short
../.venv/bin/python -m mypy app tests/test_performance_preliminary.py tests/test_performance_preliminary_api.py
../.venv/bin/python -m mypy
# из frontend/
npm test
npm run build
# read-only API
curl --fail --silent http://127.0.0.1:8000/api/v1/local-alpha/matches/9057722463/ruiner
# локальный Chrome/CDP QA harness этой сессии
node /tmp/dota_hub_ri04_qa.mjs
```

Запуск остаётся прежним: из backend `DOTA_LOCAL_ALPHA=true ../.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`; из frontend `VITE_LOCAL_ALPHA=true npm run dev -- --host 127.0.0.1 --port 5173`. Локальный backend перезапущен с новыми изменениями; данные матчей не пересчитывались. PostgreSQL integration tests используют отдельную проверяемую `dota_hub_test`, внешние сервисы подменены.

## E. Ограничения

- Low confidence остаётся low: предварительный результат не является подтверждённым кандидатом, вероятностью вины или доказательством причины поражения.
- Роли текущего pipeline не подтверждаются из имени героя/линии; качество ролевых данных не улучшалось.
- Достоверный leaver-контекст отсутствует в ingestion; действует явное ограничение. Подключение источника и политика обработки leaver требуют отдельного решения.
- Любой null индекс/неполный состав запрещает предварительный вывод. У максимума должен быть отображаемый negative_signal; низкие положительные индексы без такого сигнала закономерно могут дать none.
- Модель остаётся относительной эвристикой с малыми группами, без проверенных популяционных норм. Новые тесты не доказывают игровую достоверность.
- Live local API и сохранённые fixtures могут содержать разные версии полноты исходного матча. Фикстура 9051271323 не заменялась живой расширенной записью.
- Реальный Telegram/WebView и независимая продуктовая приёмка не выполнены. Существующие ошибки полного mypy в тестах Draft оставлены для отдельной задачи.

## F. Итог и следующий шаг

RI-04 реализован и передан в **READY FOR QA**. Формула ruiner_v1 и строгий выбор сохранены; новые результаты читаются в API и отображаются в существующей вкладке. Рабочее дерево содержит изменения без нового коммита; публикация не выполнялась.

Далее: независимая QA-приёмка интерфейса и wording в Telegram, решение по достоверному источнику ролей/leaver, отдельная проверка полезности предварительных выводов на выборке матчей. DONE этим отчётом не устанавливается. Статусы RI-01 и соседних аналитических задач не изменялись.
