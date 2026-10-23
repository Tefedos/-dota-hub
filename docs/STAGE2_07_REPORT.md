# Этап 2 — промпт 07: Ruiner Analyzer

Дата: 22 октября 2026. Работа продолжена в существующем `dota-hub/` после 07A. Изучены техническое задание, контекст, план и QA этапа 1, действующие DTO, normalizer, bot pipeline, зависимости и миграции. `sources/` не изменялись. Git всё ещё показывает исходное дерево как untracked; список изменений ниже не выдается за diff с зафиксированным baseline.

**Результат:** реализован единый RoleAwarePerformanceEvaluator с model_version=`ruiner_v1`. Он вызывается ботом после загрузки матча и выдаёт нейтральную сводку отдельно по Radiant/Dire. Индекс отражает относительные признаки исполнения; ни результат матча, ни Draft Analyzer в него не входят. При нехватке данных возвращаются null и no_confident_selection. Живая отправка Telegram не проверялась.

## A. Изменения по файлам

Созданы:

| Файл | Назначение |
| --- | --- |
| `backend/app/models/performance.py` | Строгие JSON-контракты signals, player/team reports, selection и RuinerReport |
| `backend/app/services/performance_config.py` | Версия, веса, ограничения достаточности и пороги выбора |
| `backend/app/services/performance.py` | RoleAwarePerformanceEvaluator, общая функция analyze_performance и русские шаблоны сводки |
| `backend/tests/test_performance.py` | 33 тестовых случая формул, ролей, пропусков, границ, независимости и реального offline-снимка |
| `backend/tests/test_performance_integration.py` | 5 интеграционных тестов ingestion → нормализация → анализ → bot notification, включая dispatcher |
| `scripts/audit_performance.py` | Offline-воспроизведение сохранённого снимка без внешних действий |
| `docs/RUINER_ANALYZER_SPEC.md` | Подробное описание формул, baseline, контракта и ограничений |
| `docs/audits/9051271323-ruiner-v1.json` | Отчёт на ранее сохранённом реальном снимке |
| `docs/STAGE2_07_REPORT.md` | Настоящий отчёт |

Изменены:

- `backend/app/models/matches.py`: nullable wards/dewarding и отдельная FarmPositionEvidence с безопасными defaults. Старое поле линии сохранено.
- `backend/app/services/match_normalization.py`: валидация этих счётчиков, available_fields и `position_est` только как estimated. Обратная совместимость старых snapshots сохранена.
- `backend/app/bot/services.py`: вызов общего evaluator после успешного ingestion; нейтральная сводка обеих команд; ошибка анализа не теряет результат загрузки.
- `README.md`, `docs/AI_PROJECT_CONTEXT.md`: актуальный статус и команды.

Существующий Draft Analyzer не изменялся. Новых dependencies, ORM-таблиц, миграций, REST endpoints, UI, микросервисов или LLM нет. Постоянное хранение RuinerReport в БД не реализовывалось.

## B. Команды запуска и миграций

Из корня проекта — воспроизведение без сети:

```sh
.venv/bin/python scripts/audit_performance.py \
  backend/tests/fixtures/draft/9051271323/evidence.json \
  --output /tmp/dota-hub-performance.json
```

Внутренний вызов для bot или будущего REST-handler:

```python
from app.services.match_normalization import normalize_match_snapshot
from app.services.performance import analyze_performance

report = analyze_performance(normalize_match_snapshot(saved_snapshot))
payload = report.model_dump(mode="json")
```

Обычные команды локального запуска не меняются. При настроенном bot окружении запустить или перезапустить его, чтобы загрузить новый код:

```sh
cd backend
../.venv/bin/python -m app.bot.main
```

Бот использует существующие BOT_TOKEN, allowlist групп, cooldown, ingestion и БД. Секреты в этом задании не изменялись. Не запускайте второй polling-процесс поверх существующего.

Backend и frontend в отдельных терминалах из соответствующих каталогов:

```sh
# backend/
../.venv/bin/python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

```sh
# frontend/
npm run dev
```

Миграций нет. Проверки из `backend/`:

```sh
../.venv/bin/python -m pytest --tb=no
../.venv/bin/python -m mypy
../.venv/bin/python -m pip check
../.venv/bin/python -m alembic current
../.venv/bin/python -m alembic check
```

## C. Реально выполненные проверки

| Проверка | Результат |
| --- | --- |
| Новые unit + integration тесты | **PASS — 38** |
| Финальный полный pytest, включая локальные PostgreSQL test databases | **PASS — 275**, 4.18 секунды; все прежние 237 включены |
| mypy | **PASS — 60 файлов** |
| pip check | **PASS — No broken requirements found** |
| alembic current | **PASS — 0001_initial (head)** |
| alembic check | **PASS — No new upgrade operations detected** |
| frontend npm test | **PASS — 11 тестов** |
| frontend npm run build / TypeScript | **PASS** |
| Dispatcher + /match + fake Telegram transport | **PASS**, сообщение отправлено только в тестовый transport |
| Offline-анализ сохранённого реального матча 9051271323 | **PASS**, 10 player reports, partial quality, нет выбора игрока |
| Новый live-запрос матча OpenDota для этого этапа | **NOT RUN** — использован снимок, полученный в 07A |
| Настоящая Telegram-группа / WebView | **NOT RUN** — живые сообщения и UI не проверялись |

Остаётся прежнее StarletteDeprecationWarning о httpx/TestClient, не влияющее на прохождение тестов. Ошибок финальных проверок нет; проверки, заблокированные окружением, отсутствуют. NOT RUN не выдаётся за PASS.

### Проверка сохранённого реального матча

Вход: `backend/tests/fixtures/draft/9051271323/evidence.json` из 07A. Это минимальная проекция реального OpenDota snapshot с kills/deaths/assists и team scores; GPM, damage, healing, wards и подтверждённых позиций в этой проекции нет. Это не доказательство отсутствия этих полей в полном ответе OpenDota.

Получено 10 player reports. Индексы рассчитаны для 4/5 Radiant и 5/5 Dire, все с confidence=low. Для обеих команд selection=no_confident_selection; общий summary также без выбора команды или игрока. Подробный артефакт: [9051271323-ruiner-v1.json](audits/9051271323-ruiner-v1.json).

У Radiant slot=1: kills=1, assists=11 при team_score=10. Участие `(1+11)/10` недостоверно как доля; оно не обрезано до 100%, а исключено. Остаётся одна доступная отрицательная ось — этого мало, error_index=null. Остальные индексы — ограниченный fallback по смертности и участию, не заключение о качестве конкретного игрока.

## D. Негативные сценарии

Проверены:

- 10 игроков, пустой/неполный roster, отдельные Radiant/Dire; отсутствие придуманной «нашей команды».
- Нулевые убийства, смерти и командные totals; маленький team_score; kills+assists больше team_score; KDA без деления на ноль.
- Support с низким GPM, но высокими healing/assists: экономика не штрафуется, положительный вклад виден.
- Core с низкой экономикой: сравнение только с core своей команды, с фактической reference и peer slots.
- Unknown/estimated позиция, наличие только lane_role, конфликт позиций: низкая уверенность и отсутствие выбора игрока.
- Непарсенный/неполный матч, недоступные wards/damage и полностью отсутствующие stats: пропуски не становятся нулями или индексом 100.
- Неизвестные modes и Turbo: nullable-оценки с причиной. Короткие матчи: ниже 900 секунд индексов нет; граница проверена.
- Outlier 50 deaths: ограниченная ось, один сигнал не объявляет игрока выбранным.
- Положительные extreme-счётчики: credit ≤15 и не суммируется по коррелированным метрикам. Единица лечения на фоне нулевого baseline не даёт максимальный credit.
- Границы score 69/70 и отрыва 14/15, ничья, необходимость двух независимых отрицательных осей.
- Изменение победителя/драфта не меняет отчёт; изменение статистики противника не меняет собственную командную оценку.
- Детерминизм, JSON roundtrip, неизменность входа.
- Ошибка evaluator не теряет сообщение о сохранении; исключение не раскрывается. Недоступный матч не анализируется; несовпадающий Match ID не публикуется как анализ запрошенного матча.

## E. Ограничения и основания формулы

Формула полностью описана в [RUINER_ANALYZER_SPEC.md](RUINER_ANALYZER_SPEC.md). Проверенных статистических норм по герою/роли/патчу/рангу нет. Baseline — медиана наблюдаемых значений других сравниваемых союзников в этом матче; веса и пороги явно обозначены как гипотезы ruiner_v1.

Core: survival 30%, participation 25%, economy 25%, impact 20%. Support/unknown: survival 50%, participation 50%, без штрафа за фарм и обязательного damage. Положительный вклад healing/wards/objectives и support damage даёт объяснения и ограниченный credit максимум 15. Для общего индекса нужны минимум две оси и coverage ≥0.70. Пропущенные оси исключаются, веса доступных перенормируются.

Режимы 1/2/22 поддержаны в заявленной области. Матчи короче 15 минут не оцениваются. Threshold выбора — 70, margin — 15, минимум две отрицательные оси и все пять игроков команды с medium/full coverage. Даже выбранный игрок не объявляется причиной поражения.

Модель относительная: сильнейшая игра всей команды и одинаково слабая игра могут дать одинаковые индексы. Малые ролевые группы, особенно один peer для support, и различия возможностей героев ограничивают интерпретацию. Места/время смертей, последствия вардов, доступность фарма и цели не восстанавливаются из totals. KDA показывается отдельно, чтобы не удвоить одни и те же штрафы. Герой с healing=0 не обязан уметь лечить.

Полноценного источника **confirmed позиций 1–5** в текущем bot pipeline нет. OpenDota position_est — estimated, lane_role — линия. Поэтому обычный вызов бота сохраняет low confidence и no_confident_selection, даже когда fallback-индекс посчитать можно. Выбор игрока с подтверждёнными ролями проверен на fixtures, а не выдан за результат live-инференса.

REST endpoint, постоянное сохранение отчёта, отображение десяти подробных карточек и дальнейшие аналитические этапы не реализованы. Архитектура позволяет REST-handler вызвать тот же сервис. Живая доставка в Telegram остаётся непроверенной.

## F. Критерии приёмки

| Критерий | Итог |
| --- | --- |
| Отчёт каждому доступному игроку, причины, positive/negative, confidence | PASS |
| Объяснимые baseline, веса, границы и версии | PASS, документированные гипотезы |
| Unknown role / missing metrics не создают ложные штрафы или выбор | PASS |
| Разделение Radiant/Dire и независимость от победы/драфта | PASS |
| Threshold и no_confident_selection | PASS |
| Общий сервис реально вызывается bot pipeline | PASS, интеграционные тесты |
| Unit + integration + регрессии + JSON | PASS |
| Живой Telegram end-to-end | NOT RUN; отдельно от программной готовности |

## G. Следующий шаг

**Программный модуль №07 готов к дальнейшей интеграции в заявленных границах.** Можно выполнять следующий отдельно переданный промпт. Его интегратор должен сохранять nullable-оценки, confidence, отдельные команды и нейтральные формулировки.

Для следующих заданий: согласовать хранение версионированного отчёта и HTTP-доступ, источники подтверждённых ролей, калибровку на независимой размеченной выборке, а затем UI и настоящую Telegram smoke-проверку. Ограничения Draft Analyzer 07A сохраняются отдельно и не скрываются индексом исполнения. Функциональность рекомендаций альтернативных героев не добавлялась.
