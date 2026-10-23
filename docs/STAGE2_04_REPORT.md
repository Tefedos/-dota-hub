# Этап 2 v2 промпт 04 Telegram group bot и Mini App auth

Дата: 22 октября 2026. Итог: локальная реализация и автоматические проверки PASS. Ручная проверка в Telegram BLOCKED до настройки отдельного тестового бота, тестовой группы и HTTPS Mini App. OpenDota не подключался.

## A Изменения по файлам

Созданы:

- `backend/app/bot/__init__.py` — пакет отдельного bot-процесса.
- `backend/app/bot/main.py` — polling entrypoint, не связанный с FastAPI lifecycle.
- `backend/app/bot/handlers.py` — `/start`, `/help`, `/match`, private/group поведение и ответы без parse mode.
- `backend/app/bot/services.py` — строгий Match ID, deep link, cooldown и интерфейс `JobService.request_match`.
- `backend/tests/test_bot_config.py` — fail-closed настройки и отсутствие токена.
- `backend/tests/test_bot_handlers.py` — aiogram dispatcher с mock transport, без Telegram API.
- `backend/tests/test_bot_services.py` — Match ID, deep link, cooldown и reuse.

Изменены:

- `backend/app/core/config.py`, `backend/.env.example` — bot username, allowlist и cooldown.
- `backend/pyproject.toml`, `backend/requirements.lock` — aiogram 3.31.0 и его закреплённые зависимости. Для совместимости aiogram Pydantic закреплён на 2.13.5 вместо 2.14.1; FastAPI и все старые тесты проверены после изменения.
- `README.md`, `docs/AI_PROJECT_CONTEXT.md`, этот отчёт — запуск, BotFather, доверительные границы и результаты.

Frontend, API-контракты `/api/v1/auth/telegram` и `/api/v1/auth/me`, ORM-модели и миграция `0001_initial` не изменялись. Новых БД и таблиц нет.

## B Команды запуска и миграций

Локальная установка из корня:

```sh
.venv/bin/python -m pip install -r backend/requirements.lock
cd frontend && npm ci
```

Четыре процесса разработки:

```sh
# PostgreSQL, из корня
.venv/bin/python scripts/local_postgres.py start

# FastAPI, из backend
../.venv/bin/python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# Telegram polling, из backend; требует локальный BOT_TOKEN
../.venv/bin/python -m app.bot.main

# React, из frontend
npm run dev
```

Перед polling задаются `BOT_TOKEN`, `BOT_USERNAME`, `TELEGRAM_ALLOWED_CHAT_IDS` и при необходимости `DOTA_TELEGRAM_MATCH_COOLDOWN_SECONDS`. Пустой allowlist запрещает `/match` во всех группах. Polling удаляет webhook без удаления pending updates. Нельзя запускать polling и webhook одновременно с одним токеном.

Миграции не создавались. Проверка: `../.venv/bin/python -m alembic current` и `../.venv/bin/python -m alembic check`.

## C Выполненные проверки

| Проверка | Статус и результат |
| --- | --- |
| `pytest -m 'not postgres'` | PASS — 132 passed, 25 deselected |
| `pytest --ignore=tests/test_migrations.py` | PASS — 156 passed, включая отдельную PostgreSQL |
| `python -m mypy` | PASS — 37 файлов |
| `python -m pip check` | PASS — broken requirements отсутствуют |
| `alembic current` | PASS — `0001_initial (head)` |
| `alembic check` | PASS — новых операций нет |
| `npm test` | PASS — 11 frontend-тестов |
| `npm run build` | PASS — TypeScript и production build |
| FastAPI `/api/v1/health` | PASS — HTTP 200 |
| FastAPI `/api/v1/health/db` | PASS — HTTP 200, database available |
| Запуск bot без BOT_TOKEN | PASS — процесс закрывается до сетевого вызова с понятной ошибкой |
| Реальный Telegram group smoke | BLOCKED — credentials и тестовая группа не настроены |
| Реальный Telegram Mini App auth | BLOCKED — BOT_TOKEN Dota Hub и HTTPS origin не настроены |
| OpenDota HTTP | NOT RUN — вне границ промпта, вызовов нет |
| Docker Compose | NOT RUN — Docker отсутствует, использован нативный PostgreSQL |

Первый PostgreSQL-прогон дал FAIL/ERROR, потому что локальный сервер БД был остановлен. После обычного запуска существующего проектного кластера тот же набор завершился 154 PASS. Это инфраструктурный промежуточный результат, не дефект кода. Vite также был остановлен на первой smoke-проверке; после запуска сборка и frontend-тесты прошли.

## D Негативные кейсы

Проверены пустой Match ID, ноль, отрицательное и signed значение, leading zero, дробь, экспонента, пробелы/второй аргумент, URL, HTML, Unicode-цифры, больше BIGINT и чрезмерная длина. Ответ не использует HTML/Markdown parser.

Проверены пустой и чужой allowlist, private chat, `/match@FixtureBot`, команда для другого бота, повторный update, cooldown одного пользователя и независимый запрос другого пользователя. Mock transport перехватывает `GetMe`/`SendMessage`; сообщения в Telegram не отправлялись.

Старые auth-тесты остались зелёными: реальный HMAC тестового initData, user/hash/auth_date tampering, URL encoding/unicode, недействительные и истёкшие сессии, транзакционный upsert/rollback и отсутствие секретов в ответах/логах.

## E Ограничения и причины BLOCKED

- `JobService` возвращает `NOT_IMPLEMENTED`; статистика и анализ не выдумываются.
- Cooldown и cache interface находятся в памяти одного процесса. После перезапуска cooldown сбрасывается; готовых отчётов пока нет.
- Deep link подготовлен и протестирован, но кнопка в группу не публикуется до этапа реального результата. Для группы в будущем используется `InlineKeyboardButton(url=...)`, поскольку `web_app` inline-кнопки доступен только в private chat.
- Direct-link Mini App не читает историю группы и не отправляет сообщения в неё. `start_param`, `tgWebAppStartParam` и `chat_instance` не доказывают членство. Доверенная личность по-прежнему появляется только после серверного HMAC initData.
- Production webhook, deployment, OpenDota, persistent jobs/cache и наблюдаемость относятся к следующим заданиям.
- Ручной smoke BLOCKED, потому что в локальном `.env` нет токена именно Dota Hub, настроенной тестовой группы и HTTPS Main Mini App. Реальные секреты не добавлялись и не запрашивались в чате.

## F Критерии приёмки

- Существующий FastAPI и публичный health работают — PASS.
- Bot запускается отдельным entrypoint и не встроен в web worker — PASS локально без credentials до fail-closed проверки; реальный polling BLOCKED.
- `/match` валидирует ID, allowlist и cooldown, возвращает честную заглушку — PASS на mock transport.
- Команда с mention учитывает username бота; команда другому боту игнорируется — PASS.
- Privacy mode можно оставить включённым; бот обрабатывает адресованные команды — подтверждено контрактом и фильтром aiogram, реальный smoke BLOCKED.
- Auth HMAC и сессии переиспользованы без новой архитектуры — PASS.
- Секреты не зашиты, `.env` игнорируется Git — PASS.
- Миграции и frontend не сломаны — PASS.

Официальные основания: [Telegram Mini Apps](https://core.telegram.org/bots/webapps), [Telegram Bot API](https://core.telegram.org/bots/api), [Telegram bot privacy mode](https://core.telegram.org/bots/features#privacy-mode), [aiogram long polling](https://docs.aiogram.dev/en/latest/dispatcher/long_polling.html).

## G Следующий промпт

Автоматическая часть v2 промпта 04 готова к QA. Следующий промпт допустим после ручной проверки с отдельным тестовым ботом либо с явным принятием перечисленных BLOCKED. OpenDota, настоящий отчёт, групповая кнопка результата и следующие этапы не начинались.
