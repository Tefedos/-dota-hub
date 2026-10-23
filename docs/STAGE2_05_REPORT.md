# Этап 2 v2 промпт 05 — OpenDota Match Ingestion

Дата: 22 октября 2026. Итог: локальная реализация и автоматические проверки PASS. Реальный вызов OpenDota не выполнялся: контракт проверен через отдельный HTTP mock transport без расходования внешней квоты. Telegram group smoke остаётся BLOCKED до настройки тестового бота и группы.

## A. Изменения по файлам

Созданы:

- `backend/app/integrations/__init__.py` — пакет внешних интеграций.
- `backend/app/integrations/opendota.py` — асинхронный клиент, retry/backoff, статусы, проверка ответа, presence matrix и безопасный versioned snapshot.
- `backend/app/services/match_ingestion.py` — PostgreSQL TTL-кэш, single-flight одного процесса, сохранение статусов и восстановление `pending`.
- `backend/tests/test_opendota.py` — mock-проверки ответов OpenDota и защиты секрета.
- `backend/tests/test_match_ingestion.py` — проверки TTL, конкуренции, перезапуска и сохранения в PostgreSQL.
- `docs/STAGE2_05_REPORT.md` — этот отчёт.

Изменены:

- `backend/app/bot/handlers.py`, `backend/app/bot/services.py`, `backend/app/bot/main.py` — быстрая квитанция, фоновая загрузка, итоговое сообщение и lifecycle ресурсов.
- `backend/app/core/config.py`, `backend/.env.example` — OpenDota key, timeout, retry и TTL-настройки.
- `backend/app/db/repositories.py` — чтение записи матча для кэша.
- `backend/pyproject.toml` — `httpx` перенесён в runtime-зависимости; lock уже содержал проверенную версию 0.28.1.
- `backend/tests/test_bot_config.py`, `test_bot_handlers.py`, `test_bot_services.py` — новый рабочий сценарий вместо заглушки.
- `README.md`, `docs/AI_PROJECT_CONTEXT.md` — фактическое поведение, запуск и ограничения.

Схема БД не менялась: versioned snapshot и метаданные TTL помещаются в существующий `matches.raw_payload JSONB`, статус — в существующий `fetch_status`. Новая миграция не нужна.

## B. Запуск

Из корня проекта:

```sh
.venv/bin/python scripts/local_postgres.py start
cd backend
../.venv/bin/python -m alembic upgrade head
../.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

В отдельном терминале, после локальной настройки `BOT_TOKEN` и `TELEGRAM_ALLOWED_CHAT_IDS`:

```sh
cd backend
../.venv/bin/python -m app.bot.main
```

`DATABASE_URL` обязателен для bot-процесса. `OPEN_DOTA_API_KEY` необязателен. По умолчанию timeout — 15 секунд, до двух retry для transport/5xx, success TTL — 3600 секунд, `NOT_FOUND` — 300, временная ошибка — 60. Все значения перечислены в `backend/.env.example`.

## C. Выполненные проверки

| Проверка | Результат |
| --- | --- |
| `pytest -m 'not postgres'` | PASS — 149 passed |
| полный `pytest` | PASS — 179 passed |
| `mypy` strict | PASS — 42 source files |
| `pip check` | PASS — broken requirements отсутствуют |
| `alembic current` | PASS — `0001_initial (head)` |
| `alembic check` | PASS — новых операций нет |
| `npm test` | PASS — 11 passed |
| `npm run typecheck` | PASS |
| `npm run build` | PASS |
| FastAPI `/api/v1/health` | PASS — HTTP 200 |
| FastAPI `/api/v1/health/db` | PASS — HTTP 200 |
| Vite `/matches` | PASS — HTTP 200 |
| PostgreSQL status | PASS — PostgreSQL 17.11, PID 3637 |
| Live OpenDota | NOT RUN — внешний вызов и квота не нужны для детерминированной проверки |
| Telegram group smoke | BLOCKED — локально не настроены тестовые credentials/allowlist |

Есть одно предупреждение от FastAPI/Starlette о будущем переходе тестового клиента с `httpx` на `httpx2`; оно существовало до этого изменения и не влияет на результат.

## D. Негативные и граничные случаи

Проверены полный и частичный матч, отсутствующие `picks_bans`, `objectives=null`, отсутствующие teamfights/advantage/patch, неверный JSON, неправильный Match ID, незавершённый матч, отсутствие второй команды, 404, 401, 429 с `Retry-After`, повторяемые 500, timeout и максимальный BIGINT `9223372036854775807`.

Retry выполняется только для transport-ошибок и 5xx, ограничен настройкой и экспоненциальной паузой. 404 и 429 не повторяются. `Retry-After` ограничивается диапазоном 1…3600 секунд и задаёт TTL результата rate limit.

Снимок сохраняет игровые данные, включая players, draft, objectives, teamfights и преимущества, плюс явную матрицу present/non-null/item_count. Из игроков удаляются account/profile/name/avatar/location/Steam поля, весь игровой chat не сохраняется. API key передаётся в Authorization header, отсутствует в URL, результате и логах.

## E. Кэш, конкуренция и сбои

Первый запрос создаёт/заменяет строку `pending`, затем выполняет внешний HTTP-вызов без открытой DB-транзакции и сохраняет итог. В одном bot-процессе `asyncio.Lock` на Match ID объединяет одновременные запросы: тест с двумя конкурентными вызовами выполнил provider один раз. Новый экземпляр сервиса использует сохранённый кэш, что имитирует перезапуск. После TTL выполняется новая загрузка.

Если процесс завершится во время фоновой задачи, Telegram-уведомление и сама задача теряются. Строка `pending` намеренно не считается готовым кэшем, поэтому следующий `/match` повторит загрузку. Архитектура этапа поддерживает один polling-процесс. Для нескольких реплик потребуется DB advisory lock или отдельная очередь; они не добавлялись преждевременно.

Ошибки OpenDota и Telegram разделены: первая превращается в безопасный пользовательский статус, ошибка отправки Telegram логируется отдельно только с Match ID и типом исключения. Raw response, токены и URL с секретами не логируются.

## F. Критерии приёмки

- `/match <match_id>` больше не возвращает `NOT_IMPLEMENTED` — PASS.
- Один заданный матч загружается через `GET /matches/{match_id}` — PASS на mock HTTP contract.
- Полный/частичный/не найден/недоступен/rate limited/malformed различаются — PASS.
- Большие ID не преобразуются во frontend number и сохраняются как PostgreSQL BIGINT — PASS.
- Ответ валидируется до сохранения, обе команды определяются по `player_slot` — PASS.
- PostgreSQL TTL-кэш и повторное использование после рестарта — PASS.
- Одновременный запрос одного ID не дублирует внешний вызов в одном процессе — PASS.
- Бот отвечает до начала фоновой загрузки — PASS на aiogram mock transport.
- Секрет OpenDota не попадает в URL/логи — PASS.
- Scoring, timeline, анализ, новые HTTP endpoints и микросервисы не создавались — PASS.

Официальная схема: [OpenDota API v31.1.0](https://api.opendota.com/api), [OpenDota documentation](https://docs.opendota.com/).

## G. Граница следующего шага

Промпт 05 завершён. Данные матча только загружаются, проверяются и кэшируются. Оценка игроков, объяснение результата, timeline, кнопка Mini App и пользовательский API анализа не реализованы и требуют следующего отдельного задания.
