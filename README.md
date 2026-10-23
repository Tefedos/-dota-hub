# Dota Hub

Telegram Mini App для ручного группового сценария `/match <id>`. Бот загружает матч из PostgreSQL/OpenDota, сохраняет независимые отчёты обзора, игроков, драфта, исполнения и хронологии, публикует короткую сводку с URL-кнопкой. Авторизованный Mini App читает готовые разделы через REST API. `/matches/:matchId` — функциональная заглушка чтения; подробные экраны относятся к этапу 3.

```text
Браузер → React + Vite → /api (Vite proxy) → FastAPI → PostgreSQL
Telegram group → aiogram bot → OpenDota → PostgreSQL cache
```

Добавлены PostgreSQL, SQLAlchemy/asyncpg, миграции Alembic и repositories. Telegram-авторизация, короткая серверная сессия и групповой бот работают в отдельных web/polling процессах. Промпты 05–08 добавили ingestion, нормализацию и анализаторы; №09 связал их с хранением, групповым ответом и read-only REST API. Актуальный контекст — [AI_PROJECT_CONTEXT](docs/AI_PROJECT_CONTEXT.md).

## Требования и зависимости

- macOS/Linux; Python 3.12+. Для локальной проверки выбран установленный Python 3.13.7.
- Node.js 22.12+ в ветке 22 либо 24+; локальная среда — Node 22.18.0, npm 10.9.3. Совместимость Vite: [официальное руководство](https://vite.dev/guide/).
- Интернет для первой установки пакетов. Для БД: PostgreSQL 17.11 через Docker Compose либо локальные бинарные файлы PostgreSQL 17. Docker в текущем окружении отсутствует; используется отдельный локальный кластер внутри проекта.
- Backend: FastAPI 0.159.0, Uvicorn 0.54.0, Pydantic 2.13.5, Pydantic Settings 2.16.1, aiogram 3.31.0 и httpx 0.28.1. Добавлены SQLAlchemy 2.0.55, asyncpg 0.32.0, Alembic 1.20.0 и pytest-asyncio 1.4.0. Прямые зависимости объявлены в `backend/pyproject.toml`; полный проверенный набор закреплён в `backend/requirements.lock`.
- Frontend: React 19.3.1, Vite 8.3.5. Точные версии остальных прямых зависимостей — в `frontend/package.json`, дерево зависимостей — в `frontend/package-lock.json`.

## Установка на macOS

Из корня проекта выполните один раз:

```sh
cd /Users/artemfedoseev/.codex/.chatgpt-projects/g-p-6ad91adda7e08191a8921416b367c275/dota-hub
python3.13 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.lock
cd frontend
npm ci
```

При другом установленном Python 3.12+ замените `python3.13` его именем. Команды venv/pip не требуют активации окружения. Если окружение уже создано при выполнении задания, повторное создание не требуется.

## Запуск

### Локальная Alpha 0.1 без Telegram

Один раз создайте `frontend/.env.local` из `frontend/.env.example` (`VITE_LOCAL_ALPHA=true`). Файл уже создан в этой локальной рабочей копии и исключён из Git. `backend/.env` должен содержать рабочий локальный `DATABASE_URL`; токен бота для браузерной проверки не требуется. Запустите локальную PostgreSQL через `.venv/bin/python scripts/local_postgres.py start`, затем из `backend/` выполните `../.venv/bin/python -m alembic upgrade head`.

В первом терминале из `backend/`:

```sh
DOTA_LOCAL_ALPHA=true ../.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Во втором терминале из `frontend/`:

```sh
npm run dev -- --host 127.0.0.1 --port 5173
```

Откройте [http://127.0.0.1:5173](http://127.0.0.1:5173), в разделе «Анализ матча» введите любой корректный Match ID и нажмите «Запросить анализ из OpenDota». Запрос использует настоящий backend, локальную БД и OpenDota; повторный запрос может обслуживаться локальным кэшем. Локальные маршруты регистрируются только при явном `DOTA_LOCAL_ALPHA=true`, требуют loopback-БД и loopback-клиента. Сборка Vite для production локальный режим не включает. Для обычного Telegram-сценария запускайте backend без флага и используйте бот-команду `/match`.

Фактическая приёмка и известные ограничения: [LOCAL_ALPHA_01_REPORT](docs/LOCAL_ALPHA_01_REPORT.md).

Терминал 1, backend:

```sh
cd /Users/artemfedoseev/.codex/.chatgpt-projects/g-p-6ad91adda7e08191a8921416b367c275/dota-hub/backend
../.venv/bin/python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Терминал 2, frontend:

```sh
cd /Users/artemfedoseev/.codex/.chatgpt-projects/g-p-6ad91adda7e08191a8921416b367c275/dota-hub/frontend
npm run dev
```

Терминал 3, групповой бот после настройки `BOT_TOKEN`, `TELEGRAM_ALLOWED_CHAT_IDS` и БД:

```sh
cd /Users/artemfedoseev/.codex/.chatgpt-projects/g-p-6ad91adda7e08191a8921416b367c275/dota-hub/backend
../.venv/bin/python -m app.bot.main
```

- Приложение: [http://127.0.0.1:5173](http://127.0.0.1:5173).
- Раздел матчей: [http://127.0.0.1:5173/matches](http://127.0.0.1:5173/matches).
- API: [http://127.0.0.1:8000/api/v1/health](http://127.0.0.1:8000/api/v1/health).
- OpenAPI UI: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

Остановка каждого сервера — Ctrl+C в его терминале. Если порт занят, сначала выясните, каким процессом; не завершайте неизвестный процесс. При смене backend-порта также измените target в `frontend/vite.config.ts`. `strictPort` не позволяет frontend незаметно перейти на другой порт.

## Контракты и поведение

`GET /api/v1/health` возвращает HTTP 200, `Content-Type: application/json`, `Cache-Control: no-store` и ровно:

```json
{"status":"ok","service":"dota-hub-api"}
```

Health проверяет доступность API, а не БД или будущих интеграций. Вызовы `/matches/.../analysis` на backend отсутствуют и возвращают 404. Ошибки собственного API имеют форму:

```json
{"error":{"code":"NOT_FOUND","message":"Ресурс не найден","details":[]}}
```

UI запрашивает health при загрузке и по кнопке «Проверить», показывает loading / доступно / недоступно. Состояние отражает последнюю проверку, а не непрерывный мониторинг. Общий тайм-аут — 5 секунд, при размонтировании запрос отменяется. Проверяются HTTP-статус и форма JSON; HTML или неожиданный JSON не считаются успехом.

Match ID остаётся строкой, а сравнение границы использует BigInt: допустим диапазон 1…9223372036854775807. Пробелы по краям удаляются; дроби, ноль, отрицательные числа, экспонента, буквы и ведущие нули отклоняются. Форма проверяет формат и показывает готовую команду `/match <id>` для группы. Открытие готового анализа по ссылке использует отдельный маршрут `/matches/:matchId` и авторизованный REST API.

## Настройки и будущие секреты

Для liveness и frontend `.env` не обязателен. Для БД создайте его через `scripts/init_local_env.py` по инструкции ниже. Скрипт генерирует локальный пароль, не выводит его и не перезаписывает существующий файл. Поддерживается `DOTA_DOCS_ENABLED=false` для отключения `/docs` и `/openapi.json`. Переменные окружения имеют приоритет; файл находится по пути backend независимо от текущего каталога. Подход основан на [Pydantic Settings в документации FastAPI](https://fastapi.tiangolo.com/advanced/settings/).

Строка DATABASE_URL и локальный пароль PostgreSQL хранятся только в `backend/.env` или окружении. Для входа через Telegram нужны BOT_TOKEN и отдельный SESSION_SECRET; без них auth возвращает 503, а публичный health продолжает работать. OpenDota работает без ключа; необязательный `OPEN_DOTA_API_KEY` повышает доступные лимиты и передаётся в Authorization header. Не добавлять секреты в `VITE_*`, браузерный код или Git.

Локальный frontend использует относительный `/api` и Vite proxy. Backend разрешает CORS только для точных адресов из DOTA_CORS_ORIGINS: по умолчанию http://127.0.0.1:5173 и http://localhost:5173, без cookies и wildcard. В будущем при развёртывании нужен HTTPS reverse proxy с `/api` к backend и возвратом `index.html` для frontend-маршрутов. При разделении доменов добавьте точный HTTPS origin в DOTA_CORS_ORIGINS. Dev-серверы привязаны к loopback; публикация и доступ с телефона не настроены.

## Проверки

Backend, из папки `backend/`:

```sh
../.venv/bin/python -m pytest
../.venv/bin/python -m mypy
../.venv/bin/python -m pip check
```

Frontend, из папки `frontend/`:

```sh
npm test
npm run typecheck
npm run build
```

При запущенных серверах:

```sh
curl -i http://127.0.0.1:8000/api/v1/health
curl -i http://127.0.0.1:5173/api/v1/health
```

Ручная проверка: открыть главную → «Анализ матча» → отправить пустой/неверный/корректный ID; обновить `/matches` напрямую; остановить backend → нажать «Проверить» → увидеть контролируемую ошибку; снова запустить backend → повторить проверку. При остановленном backend сообщение proxy `ECONNREFUSED` в терминале Vite ожидаемо.

`npm run build` создаёт `frontend/dist/`. `npm run preview` предназначен только для просмотра сборки; dev-proxy не является production-инфраструктурой, для публикации нужен описанный выше reverse proxy.

## Структура и ограничения

- `backend/app/api/v1/` — публичные health и маршруты Telegram auth.
- `backend/app/bot/` — отдельный aiogram polling-процесс, команды группы и сервис запросов матчей.
- `backend/app/core/` — настройки и единая обработка ошибок.
- `backend/app/models/` — Pydantic-схемы HTTP и внутренние DTO нормализованного матча.
- `backend/app/db/` — ORM-модели, единый async pool/session factory и внутренние repositories.
- `backend/migrations/` — версия 0001_initial и окружение Alembic.
- `compose.yaml` — dev-only PostgreSQL с постоянным volume и healthcheck.
- `scripts/` — генерация локального env и необязательный запуск PostgreSQL на macOS без Docker.
- `backend/app/integrations/` — HTTP-клиент OpenDota, проверка ответа и безопасный снимок.
- `backend/app/services/` — Telegram auth/session, загрузка матча с PostgreSQL TTL-кэшем и чистая нормализация snapshot.
- `backend/tests/` — проверки контракта, ошибок и настроек.
- `frontend/src/app/` — оболочка и маршруты Dota Hub.
- `frontend/src/pages/` — главная и раздел матчей.
- `frontend/src/features/matches/` — проверка ввода без анализа.
- `frontend/src/features/auth/` — Telegram bridge, auth API и статус входа; bearer хранится только в React.
- `frontend/src/shared/` — HTTP-клиент, статус подключения, стили.
- `docs/` — контекст, план этапа и фактический отчёт проверки.

Главная описывает только групповой анализ матчей. Добавлены Telegram SDK, проверка initData, сессия, обработка startapp и чтение готовых отчётов. Настоящий прогон в Telegram WebView пока не выполнен. CSS учитывает системные safe-area-inset; поведение внутри Telegram на iOS/Android/Desktop требует отдельной проверки с HTTPS и Main Mini App. Это локальная основа приложения, не готовый production-релиз.

Git инициализирован локально; коммиты, remote и публикация не выполнялись. Отчёты: `docs/STAGE1_02_REPORT.md`, `docs/STAGE1_03_REPORT.md`, `docs/STAGE1_QA_REPORT.md` и `docs/STAGE2_04_REPORT.md`.

## PostgreSQL: локальная настройка

Все команды этого раздела начинаются в корне `dota-hub/`. Не запускайте одновременно Compose и локальный кластер: оба используют `127.0.0.1:55432`. База разработки — `dota_hub`; тесты используют только `dota_hub_test` и пустую `dota_hub_migration_test`.

```sh
.venv/bin/python -m pip install -r backend/requirements.lock
.venv/bin/python scripts/init_local_env.py
```

Вторую команду выполняйте только при отсутствии `backend/.env`. Существующий файл скрипт оставляет без изменений. Файл создаётся с правами 0600; реальные значения не нужно пересылать или добавлять в Git.

Переменные:

| Переменная | Назначение |
| --- | --- |
| `POSTGRES_USER`, `POSTGRES_DB`, `POSTGRES_PASSWORD` | Инициализация локального PostgreSQL; пользователь `dota_hub` имеет административные права только в этом dev-кластере |
| `DATABASE_URL` | Asyncpg URL БД разработки; хранится в Settings как SecretStr |
| `TEST_DATABASE_URL` | Отдельная `dota_hub_test` для тестов repositories |
| `MIGRATION_TEST_DATABASE_URL` | Отдельная пустая `dota_hub_migration_test` для цикла downgrade/upgrade |
| `DOTA_DB_HEALTH_TIMEOUT_SECONDS` | Тайм-аут публичной проверки БД, по умолчанию 3 секунды |

POSTGRES-переменные задают начальные настройки кластера. Изменение пароля в env не меняет пароль существующей БД. При изменении конфигурации обновляйте её согласованно, не удаляя данные и volume.

### Вариант A: Docker Compose

Требуется установленный и запущенный Docker с Compose. Compose использует `backend/.env`, образ `postgres:17.11`, привязку только к loopback и named volume `postgres_data`. Путь volume соответствует [официальному образу PostgreSQL 17](https://hub.docker.com/_/postgres).

```sh
docker compose up -d db
docker compose ps
docker compose exec db pg_isready -U dota_hub -d dota_hub
docker compose exec db createdb -U dota_hub dota_hub_test
docker compose exec db createdb -U dota_hub dota_hub_migration_test
```

`createdb` выполняется один раз. Если тестовая БД уже существует, сохраните её: не пересоздавайте и не удаляйте. Основную БД создаёт образ при первой инициализации volume. После готовности сервиса примените миграции, как описано ниже. Docker-вариант в текущей среде не запускался: Docker отсутствует.

Обычная остановка и запуск с сохранением данных:

```sh
docker compose stop db
docker compose start db
```

Не используйте `docker compose down -v`, сброс volume или `dropdb` для обновления схемы.

### Вариант B: macOS без Docker

В текущей среде используется PostgreSQL 17 из Homebrew. Если его нет, установите `brew install postgresql@17`. Не требуется `brew services start`: проектный скрипт запускает отдельный кластер в `.local/postgres/` и сохраняет данные между остановками. Обычный Homebrew-кластер не используется.

```sh
.venv/bin/python scripts/local_postgres.py start
.venv/bin/python scripts/local_postgres.py create-databases
.venv/bin/python scripts/local_postgres.py status
```

Для Intel Mac можно передать `--bin /usr/local/opt/postgresql@17/bin`; на Apple Silicon используется `/opt/homebrew/opt/postgresql@17/bin`. Скрипт не перезаписывает существующий кластер, не печатает пароль и создаёт только три именованные локальные БД, если их ещё нет. `create-databases` можно повторять.

```sh
.venv/bin/python scripts/local_postgres.py stop
.venv/bin/python scripts/local_postgres.py start
```

### Миграции

Из папки `backend/`:

```sh
../.venv/bin/python -m alembic upgrade head
../.venv/bin/python -m alembic current
../.venv/bin/python -m alembic upgrade head
../.venv/bin/python -m alembic check
```

`DATABASE_URL` загружается из `backend/.env`, переменная процесса имеет приоритет. URL не хранится в `alembic.ini`. При запуске FastAPI таблицы и миграции автоматически не создаются. Будущие изменения — только новыми миграциями, с проверкой сгенерированного SQL. Уже применённую миграцию не переписывать.

Первоначальный upgrade создаёт только новые таблицы; он не удаляет и не заменяет существующие. При неожиданной существующей схеме остановитесь и изучите её, не используйте `stamp` для скрытия расхождений. Прямое изменение production требует отдельного плана, резервной копии и согласования.

Первоначальный downgrade защищён: допускается только с явным флагом, только на loopback-БД `dota_hub_migration_test` и только если четыре таблицы пусты. Тест ниже проверяет отказ без флага/при наличии записей и разрешённый цикл. Не направляйте downgrade в dev/prod.

### Схема

| Таблица | Ключевые поля и ограничения |
| --- | --- |
| `telegram_users` | PK `telegram_user_id BIGINT > 0`, nullable username/display_name, created_at/updated_at TIMESTAMPTZ |
| `matches` | PK `match_id BIGINT > 0`, fetch_status pending/ready/unavailable/failed, nullable raw_payload JSONB и fetched_at, created_at/updated_at TIMESTAMPTZ |
| `match_analyses` | PK UUID, FK match_id → matches RESTRICT, algorithm_version VARCHAR(64), status pending/ready/failed, nullable report_payload JSONB/completeness/computed_at, created_at; UNIQUE(match_id, algorithm_version), индекс match_id |
| `user_match_history` | PK UUID, FK пользователя и матча RESTRICT, last_viewed_at TIMESTAMPTZ; UNIQUE(telegram_user_id, match_id); индексы (telegram_user_id, last_viewed_at DESC), match_id |

UUID генерирует PostgreSQL (`gen_random_uuid()`), время — `now()` с timezone. Сессии устанавливают UTC; updated_at обновляется ORM/repositories, отдельного DB-триггера для произвольного внешнего SQL нет. Nullable JSONB сохраняет Python None как SQL NULL. Completeness — full/partial/missing или NULL. Служебная таблица `alembic_version` не является бизнес-сущностью.

### Сессии, repositories и граница авторизации

Один лениво подключаемый engine/pool на lifespan приложения, `expire_on_commit=False`, отдельная сессия на запрос. `get_db_session` закрывает сессию и откатывает незакоммиченную работу; engine освобождается при остановке. Записи вызываются внутри `async with session.begin()`; repository-функции сами commit не делают.

`upsert_verified_user`, `upsert_match`, `save_analysis`, `record_view`, `recent_matches` — внутренние функции, публичных API записи нет. Upsert использует PostgreSQL ON CONFLICT; повторная версия анализа сохраняет UUID, новая версия получает отдельную запись. Повторный просмотр обновляет запись; запоздалое событие не уменьшает last_viewed_at. История ограничена конкретным пользователем, сортируется по времени DESC с дополнительной сортировкой match_id DESC, limit 1–100.

`VerifiedTelegramUser` — внутренний тип, **не валидатор подписи**. В будущем его разрешено создавать только после серверной проверки initData. Нельзя десериализовать его из клиентского JSON или вызывать запись пользователя/истории до успешной авторизации. Сейчас производственных вызовов этих методов нет. upsert матча заменяет текущие поля кэша целиком: опущенные payload/time очищаются в NULL; будущий сервис загрузки должен передавать состояние осознанно.

### Проверка БД и тесты

`GET /api/v1/health/db`: HTTP 200 и `{"status":"ok","database":"available"}`, если `SELECT 1` успешен; HTTP 503 с `error.code=DATABASE_UNAVAILABLE` при отсутствии настройки, ошибке соединения или тайм-ауте. Пароль, URL и SQL-ошибки не возвращаются. Это проверка доступности БД, не актуальности схемы; миграции проверяются отдельно через Alembic. Основной `/api/v1/health` работает и при отключённой БД.

```sh
curl -i http://127.0.0.1:8000/api/v1/health/db
```

Все backend-проверки из `backend/`:

```sh
../.venv/bin/python -m pytest
../.venv/bin/python -m mypy
../.venv/bin/python -m pip check
```

Выборочно:

```sh
../.venv/bin/python -m pytest -m 'not postgres'
../.venv/bin/python -m pytest -m postgres
../.venv/bin/python -m pytest tests/test_migrations.py -v
```

Tests не используют SQLite. URL тестов проверяется до соединения: PostgreSQL/asyncpg, loopback, точное имя отдельной test-БД, несовпадение с БД разработки. Если test URL не задан, PostgreSQL-тесты пропускаются; это не означает их успешного прохождения. Если URL задан, но БД недоступна, тесты завершаются ошибкой. Тестовые таблицы создаются через Alembic, каждая repository-проверка откатывает собственную транзакцию. Цикл миграций проходит на второй пустой БД, отказывается работать с посторонними таблицами/записями и оставляет схему в head.

Архитектура async сессий соответствует [SQLAlchemy](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html), интеграция Alembic с async engine — [официальному cookbook](https://alembic.sqlalchemy.org/en/latest/cookbook.html#using-asyncio-with-alembic). Фактические результаты и ограничения текущего запуска: [отчёт промпта 03](docs/STAGE1_03_REPORT.md).


## Telegram auth — этап 2, промпт 04

Локальная реализация и автоматические проверки завершены. Реальный вход из Telegram **BLOCKED**: токен Dota Hub и HTTPS-развёртывание не настроены. Не используйте токен другого бота. Обычный браузер показывает «Откройте Dota Hub через Telegram для входа»; dev-входа по userId нет.

### Настройки

Добавьте значения только в локальный `backend/.env` с правами 0600 либо в окружение backend. Не передавайте секреты в чат, URL, `VITE_*`, тестовые файлы или Git. `.env.example` содержит закомментированные плейсхолдеры; реальный `.env` этим шагом не изменён.

| Переменная | Значение / смысл |
| --- | --- |
| `BOT_TOKEN` | Токен именно бота, который запускает Dota Hub |
| `SESSION_SECRET` | Независимый криптографически случайный секрет, минимум 32 байта; используйте генератор секретов/менеджер паролей. Не совпадает с BOT_TOKEN |
| `DOTA_TELEGRAM_INIT_DATA_MAX_AGE_SECONDS` | 86400 по умолчанию; можно уменьшить до 1 секунды |
| `DOTA_TELEGRAM_CLOCK_SKEW_SECONDS` | 30 по умолчанию, допустимо 0–60 |
| `DOTA_SESSION_TTL_SECONDS` | 900 по умолчанию, допустимо 60–3600 |
| `DOTA_CORS_ORIGINS` | JSON-массив точных origins, например `["http://127.0.0.1:5173","http://localhost:5173","https://mini.example.org"]`; добавляйте только свой доверенный домен |

Изменение env требует перезапуска backend. Без обоих корректно настроенных секретов вход закрыт: `503 AUTH_UNAVAILABLE`. Секрет сессии не проверяет HMAC Telegram, а BOT_TOKEN не подписывает сессию.

### Контракт и границы доверия

- `POST /api/v1/auth/telegram`, JSON `{"init_data":"<RAW_TELEGRAM_INIT_DATA>"}`. Успех: `{"access_token":"<SERVER_SESSION>","token_type":"bearer","expires_in":900,"user":{"telegram_user_id":"<ID_AS_STRING>","username":null,"display_name":"<NAME>","created_at":"<ISO_8601>","updated_at":"<ISO_8601>"}}`.
- `GET /api/v1/auth/me`, заголовок `Authorization: Bearer <SERVER_SESSION>`; ответ — тот же объект `user`, без access_token. Профиль читается из БД, переданный `userId` не влияет на идентичность.
- Ошибки сохраняют единый формат `{"error":{"code":"INVALID_INIT_DATA","message":"Не удалось подтвердить вход через Telegram","details":[]}}`. `401`: неверный initData, отсутствующая/неверная/истёкшая сессия или отсутствующий пользователь; `422`: неверное тело запроса; `503`: недоступна конфигурация auth либо БД. Ответы auth имеют `Cache-Control: no-store`; ошибки 401 — `WWW-Authenticate: Bearer`.
- Сохраняются публичные `/api/v1/health` и `/api/v1/health/db`.

Проверка соответствует [официальной схеме Telegram](https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app): строгий разбор query string, отсутствие дубликатов, сортировка всех полей кроме `hash`, строки `key=value` через LF, два HMAC-SHA256, `compare_digest`, проверка auth_date. `signature` и неизвестные поля входят в HMAC; исключение `signature` относится к другому алгоритму Ed25519. Затем валидируются JSON user и положительный BIGINT ID. Ограничения: 16384 символа, 32 query-поля, строковые поля в пределах существующей схемы. Только после этого выполняется транзакционный upsert в `telegram_users`.

Сессия: [PyJWT](https://pyjwt.readthedocs.io/en/stable/api.html), фиксированный HS256, обязательные sub/iss/aud/iat/nbf/exp/jti, проверка issuer/audience/времени. В JWT нет имени, username или raw initData. Токен выпускается после commit; новый login обновляет одного пользователя по PK. Изменение схемы не требуется.

React получает только raw `Telegram.WebApp.initData`, вызывает login, затем `/me`. Состояния: загрузка / вне Telegram / ошибка / вход выполнен / сессия истекла. Токен хранится только в состоянии React и удаляется при истечении, 401 или размонтировании. Повторный вход — по кнопке, без скрытого продления; время повторно проверяется после возврата во вкладку. SDK загружается асинхронно (тайм-аут 8 с), API имеет тайм-аут 5 с. SDK недоступен — контролируемая ошибка, основной интерфейс остаётся работоспособным.

### Тесты без реальных секретов

Из `backend/`:

```sh
../.venv/bin/python -m pytest -m 'not postgres'
../.venv/bin/python -m pytest --ignore=tests/test_migrations.py
../.venv/bin/python -m mypy
../.venv/bin/python -m pip check
../.venv/bin/python -m alembic current
../.venv/bin/python -m alembic check
```

Первый прогон не требует PostgreSQL или Telegram. Второй использует существующую отдельную `dota_hub_test` и rollback; тест цикла downgrade/upgrade намеренно исключён из обычной приёмки auth. Нет внешних HTTP-запросов и расхода API-квоты. BOT_TOKEN, SESSION_SECRET и подписанные initData создаются в памяти тестов. Если test-БД не настроена, PostgreSQL-тесты SKIPPED, а не PASS; нужен отдельный доступный PostgreSQL-прогон для приёмки.

Из `frontend/`: `npm test` (mock SDK/fetch), затем `npm run build`. Установка новых зависимостей: из корня `.venv/bin/python -m pip install -r backend/requirements.lock`, из frontend `npm ci`.

Безопасные примеры контрактов (плейсхолдеры намеренно не дают успешный вход; не заменяйте их реальными секретами в сохраняемой истории команд):

```sh
curl -i http://127.0.0.1:8000/api/v1/auth/telegram \
  -H 'Content-Type: application/json' \
  --data '{"init_data":"<RAW_TELEGRAM_INIT_DATA>"}'
curl -i http://127.0.0.1:8000/api/v1/auth/me \
  -H 'Authorization: Bearer <SERVER_SESSION>'
curl -i http://127.0.0.1:8000/api/v1/health
```

### Ручная проверка внутри Telegram

1. Настройте локально BOT_TOKEN Dota Hub и независимый SESSION_SECRET. Перезапустите backend. Не присылайте значения в отчёты.
2. Подготовьте доверенный HTTPS origin для frontend с проксированием `/api` на backend. Текущие loopback dev-серверы сами по себе не доступны Telegram на телефоне. Публикация/туннель в этом задании не выполнялись.
3. Настройте Mini App этого бота через BotFather на свой HTTPS URL. При разных origins настройте точный DOTA_CORS_ORIGINS.
4. Откройте приложение именно через Mini App кнопку/меню бота. Должны пройти POST login и GET me, появиться «Вход через Telegram выполнен» и имя. Не копируйте тела запросов/ответов или Authorization в логи, скриншоты, HAR и Git.
5. Повторно откройте приложение: для того же telegram_user_id остаётся одна запись, профиль обновляется. В обычном браузере личность не появляется.
6. Для проверки истечения временно задайте TTL 60 с, перезапустите backend и откройте Mini App заново. После минуты — «Сессия истекла», профиль очищается. Проверьте также после сворачивания/возврата. Верните TTL 900.
7. Проверьте iOS/Android/Desktop отдельно. В отчёте фиксируйте только PASS/FAIL, платформу и безопасное описание, без персональных данных и токенов.

Ограничения MVP: initData можно повторно использовать в пределах разрешённого возраста; одноразовый nonce-store не добавлен. Сессии без отдельной таблицы, refresh-токенов и индивидуального отзыва; ротация SESSION_SECRET завершает все текущие сессии. Текущий шаг не реализует анализ матчей, профиль как отдельный экран или функциональность следующих промптов.

## Групповой Telegram-бот — этап 2 v2, промпт 04

Бот запускается отдельным процессом из той же кодовой базы. Он обрабатывает `/start`, `/help`, `/match <match_id>` и `/match@BotUsername <match_id>`. В private chat объясняет, как добавить его в группу. В group/supergroup проверяет allowlist и Match ID, сразу подтверждает запрос, затем в фоновой задаче загружает данные OpenDota и присылает статус `FOUND_FULL`, `FOUND_PARTIAL`, `NOT_FOUND`, `API_UNAVAILABLE`, `RATE_LIMITED` или `MALFORMED_RESPONSE` понятным текстом.

### Настройки

Добавьте значения только в локальный `backend/.env` или окружение процесса:

| Переменная | Назначение |
| --- | --- |
| `BOT_TOKEN` | Секретный токен бота от BotFather; используется также серверной проверкой initData |
| `BOT_USERNAME` | Username без `@`; нужен для формирования ссылок Main Mini App |
| `TELEGRAM_ALLOWED_CHAT_IDS` | JSON-массив точных отрицательных ID групп, например `[-1001234567890]` |
| `DOTA_TELEGRAM_MATCH_COOLDOWN_SECONDS` | Cooldown `/match` для пары chat_id + user_id; по умолчанию 10 секунд |

Пустой `TELEGRAM_ALLOWED_CHAT_IDS=[]` — безопасное значение: `/match` запрещён во всех группах. ID группы получают из Bot API update после добавления тестового бота; не используют `chat_instance`, `startapp` или данные браузера как доказательство членства. Не публикуйте chat ID вместе с персональными данными и не добавляйте токен в Git, frontend или URL.

Запуск polling из `backend/`:

```sh
../.venv/bin/python -m app.bot.main
```

Процесс удаляет настроенный webhook без сброса ожидающих updates и запускает long polling. Не запускайте polling и webhook одновременно с одним токеном. Для production предусмотрите один управляемый процесс бота; переход на webhook выполняется отдельным заданием с HTTPS reverse proxy и отключённым polling.

### BotFather и Main Mini App

1. Создайте или выберите отдельного бота Dota Hub и сохраните выданный токен только в секретах backend.
2. В BotFather разрешите добавление в группы (`/setjoingroups`). Оставьте privacy mode включённым: адресованные команды `/match@BotUsername` работают без чтения всей переписки.
3. Задайте команды `/start`, `/help`, `/match` через `/setcommands`.
4. Настройте Main Mini App на доверенный HTTPS URL. Production Mini App требует HTTPS.
5. Укажите точный username в `BOT_USERNAME`. Ссылка формируется как `https://t.me/<bot_username>?startapp=match_<id>`; payload предварительно проверяется.
6. Для будущего группового результата используйте `InlineKeyboardButton(url=...)`. Поле `web_app` inline-кнопки доступно только в private chat, поэтому для группы оно не применяется.

Mini App, открытая direct link, не получает права читать историю группы или отправлять групповые сообщения. `start_param`, `tgWebAppStartParam`, `chat_instance` применяются только для навигации/контекста и не заменяют проверенный `initData` или chat_id, полученный ботом.

### Поведение и тестирование

Допустимый Match ID — каноническое положительное десятичное число `1…9223372036854775807`. Отклоняются ноль, знак, ведущие нули, пробелы, ссылки, HTML, экспонента, Unicode-цифры, второй аргумент и чрезмерная длина. Ответы отправляются с `parse_mode=None`.

Cooldown хранится в памяти процесса и изолирован по `(chat_id, user_id)`. Перезапуск его сбрасывает. Снимок OpenDota хранится в существующей таблице `matches`: успешные ответы — 1 час, `NOT_FOUND` — 5 минут, временные ошибки — 1 минуту, `429` — на безопасно ограниченный `Retry-After`. Одновременные запросы одного Match ID в одном bot-процессе выполняют один внешний вызов. После аварийного завершения фоновая задача теряется, но оставшийся `pending` не считается кэшем и следующий запрос запускает загрузку заново. Несколько параллельных polling-реплик на этом этапе не поддерживаются.

Unit-тесты не обращаются к Telegram: `Dispatcher.feed_update` работает с контролируемой `BaseSession`, которая перехватывает Bot API методы. Реальный smoke в группе выполняется только с отдельным тестовым ботом и разрешённой тестовой группой.

## Нормализованная модель матча — промпт 06

`normalize_match_snapshot` из `backend/app/services/match_normalization.py` принимает versioned snapshot промпта 05 и возвращает неизменяемый `NormalizedMatch`. В модели отдельно находятся:

- `summary` — строковый Match ID, команды, счёт, победитель, длительность, режим, patch и roster;
- `players` — отсортированные по `player_slot` статистики с нейтральными fallback-именами;
- `raw.draft` и `raw.events` — исходный draft/timeline без реконструкции стадий;
- `derived` — KDA и kill participation с явным статусом отсутствующих входов или нулевого знаменателя;
- `data_quality` — качество summary, stats, draft order, timeline и roles по отдельности.

Числовой ноль считается известным значением. Отсутствующее, `null` или неверно типизированное поле становится `null` и не входит в `available_fields`. Положительный hero ID сохраняется даже без записи в справочнике; имя героя появляется только через явно переданный mapping constants. `player_slot` задаёт команду и стабильную позицию записи, но никогда не трактуется как порядок пика. Дублированный или выходящий за диапазон slot отклоняет snapshot, а проблемы draft order записываются в `DraftRawData` без исправления источника.

Нормализация выполняется детерминированно и не изменяет входной snapshot. Публичный endpoint на этом шаге не добавлен: DTO и сервис доступны напрямую FastAPI и bot-модулям. Нормализованный результат пока не хранится отдельно, поэтому миграция не нужна.


## Draft Analyzer — промпт 07A

Внутренний `analyze_draft(NormalizedMatch)` формирует оценки обеих команд с причинами и источниками. Описательный каталог содержит 127 героев; механические профили — 11 героев для patch=60. Production-видимость 2+2+1 подтверждена только для game_mode=22/patch=46, поэтому численный последовательный анализ современных матчей пока не готов. Непокрытые случаи возвращают null или FINAL_ONLY.

После [Alpha-исправления №7A.1](docs/STAGE2_07A1_ALPHA_BUGFIX_REPORT.md) групповой сценарий запрашивает агрегатные матчапы, разделяет личные и командные причины и допускает численные механические правила только при доказанной применимости к патчу. Для матча 9051271323 итоговые баллы всех героев и команд теперь `null`; сохранённый ниже отчёт №07A описывает предыдущую версию модели.

Проверка без сети из корня проекта:

```sh
mkdir -p /tmp/dota-hub-draft-replay
cp backend/tests/fixtures/draft/9051271323/evidence.json /tmp/dota-hub-draft-replay/evidence.json
.venv/bin/python scripts/audit_draft.py 9051271323 --output-dir /tmp/dota-hub-draft-replay --offline
```

[Спецификация](docs/DRAFT_ANALYZER_SPEC.md) описывает контракт и формулы. [Отчёт 07A](docs/STAGE2_07A_REPORT.md) содержит список файлов, команды, реальные проверки, аудит универсальности и GAP-list. Реальный матч 9051271323 проверен через OpenDota; его история не соответствует финальному roster и корректно даёт FINAL_ONLY. Финальные проверки: 237 backend-тестов, 11 frontend-тестов, mypy, сборка frontend и проверка миграций прошли.


## Ruiner Analyzer — промпт 07

`RoleAwarePerformanceEvaluator` сравнивает исполнение внутри каждой команды с учётом подтверждённой или оценочной позиции. Отсутствие позиции включает fallback с low confidence; lane_role не превращается в позицию 1–5. Baseline — наблюдения союзников, а не выдуманные нормы GPM. Индекс не использует победителя или результат Draft Analyzer.

После загрузки snapshot бот вызывает тот же Python-сервис и добавляет нейтральную сводку Radiant/Dire. Реальная Telegram-доставка на этом этапе не проверялась; transport и dispatcher проверены тестами. После обновления кода существующий polling-процесс нужно перезапустить.

Offline-проверка из корня:

```sh
.venv/bin/python scripts/audit_performance.py backend/tests/fixtures/draft/9051271323/evidence.json --output /tmp/dota-hub-performance.json
```

[Подробная формула](docs/RUINER_ANALYZER_SPEC.md) и [отчёт 07](docs/STAGE2_07_REPORT.md) фиксируют nullable-случаи, пороги, список файлов и результаты проверок. Итог: 275 backend-тестов, 11 frontend-тестов, mypy, сборка frontend и миграции прошли. Новых миграций, HTTP endpoints и UI нет.

## Timeline Match Events — промпт 08

`analyze_timeline(NormalizedMatch)` собирает подтверждённые события из objectives, командных драк и журналов игроков, строит минутные точки преимуществ и отдельно отмечает возможные изменения преимущества. Отсутствующие данные не заменяются событиями или нулями. Отчёт `TimelineReport` содержит статус качества, покрытие источников, исходные ссылки и ограничения; `filter_timeline_events` фильтрует по типу и стороне. Подробности и воспроизводимый вызов: [спецификация](docs/TIMELINE_SPEC.md), [отчёт 08](docs/STAGE2_08_REPORT.md). В №09 добавлены вызов из общего процесса и HTTP endpoint.

## Единый групповой сценарий — промпт 09

После `/match` общий сервис сохраняет пять отдельных отчётов и состояние в `match_analyses`. Повторная команда использует TTL-кэш источника и версии отчётов; одновременные чаты не дублируют анализ одного ID. На старте единственный polling worker отмечает прерванные задания; пользователь может повторить команду. GET читает данные без вычислений и внешних вызовов.

Маршруты `/api/v1/matches/{id}/overview`, `/players`, `/draft`, `/ruiner`, `/timeline`, `/analysis/status` требуют существующую bearer-сессию Telegram auth. Обёртка schema_version=1 содержит status, data, available_sections, error/retryable, limitations и метаданные версии. Разделы queued/running возвращают 202; status endpoint — 200 с явным состоянием. MVP-анализ известного матча доступен всем авторизованным пользователям, независимо от группы. Сырые данные и Steam/account IDs не публикуются.

Проверки из `backend/`: `../.venv/bin/python -m pytest --tb=short`, `../.venv/bin/python -m mypy`, `../.venv/bin/python -m pip check`. Из `frontend/`: `npm test`, `npm run build`. Запуск web/bot/frontend указан выше, миграций №09 нет. Не запускайте polling при тестах или поверх уже работающего бота.

[QA-отчёт №09](docs/STAGE2_09_QA_REPORT.md) содержит матрицу, фактические команды и ограничения. [Эксплуатация](docs/GROUP_FLOW_OPERATIONS.md) описывает BotFather, Main Mini App, HTTPS, worker restart и live-чек-лист. [Передача этапу 3](docs/STAGE3_FRONTEND_HANDOFF.md) фиксирует DTO, русские состояния и пять вкладок. Синтетический Match ID 8888765469 используется только в контрактных тестах; live-данные для него не запрашивались.
