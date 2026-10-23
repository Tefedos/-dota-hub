# Промпт 03 — PostgreSQL, ORM и Alembic

Дата завершения: 22 октября 2026. Среда: macOS, Python 3.13.7, PostgreSQL 17.11, Node 22.18.0.

## Результат и границы проверки

Добавлены четыре ORM-сущности, явная начальная миграция, асинхронный доступ к PostgreSQL, внутренние repositories и безопасный GET /api/v1/health/db. Основной health и React сохранены. OpenDota, scoring, timeline и Telegram-авторизация не добавлялись; пользовательских API записи нет.

В начале шага у проекта не было БД, моделей или миграций. Docker, OrbStack, Postgres.app и PostgreSQL CLI на компьютере отсутствовали. Подготовлен compose.yaml для postgres:17.11. Для реальных проверок установлен PostgreSQL 17.11 через Homebrew и создан **отдельный кластер проекта** в `.local/postgres`, доступный только на `127.0.0.1:55432`, без регистрации системной службы.

**Docker Compose не запускался.** Проверены нативный PostgreSQL, миграции, repositories и сохранность данных после перезапуска нативного сервера. Контейнерный запуск и сохранность named volume не представлены как проверенные.

## Реальная схема

| Таблица | Поля |
| --- | --- |
| telegram_users | telegram_user_id BIGINT PK, username VARCHAR(64) NULL, display_name VARCHAR(256) NULL, created_at/updated_at TIMESTAMPTZ NOT NULL DEFAULT now() |
| matches | match_id BIGINT PK, fetch_status VARCHAR(16) NOT NULL DEFAULT pending, raw_payload JSONB NULL, fetched_at TIMESTAMPTZ NULL, created_at/updated_at TIMESTAMPTZ NOT NULL DEFAULT now() |
| match_analyses | id UUID PK DEFAULT gen_random_uuid(), match_id BIGINT NOT NULL FK, algorithm_version VARCHAR(64) NOT NULL, status VARCHAR(16) NOT NULL DEFAULT pending, report_payload JSONB NULL, completeness VARCHAR(16) NULL, computed_at TIMESTAMPTZ NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now() |
| user_match_history | id UUID PK DEFAULT gen_random_uuid(), telegram_user_id BIGINT NOT NULL FK, match_id BIGINT NOT NULL FK, last_viewed_at TIMESTAMPTZ NOT NULL DEFAULT now() |

Ограничения и индексы:

- Четыре PK с соответствующими уникальными индексами.
- FK `match_analyses.match_id → matches.match_id` с ON DELETE RESTRICT.
- FK истории на пользователя и матч с ON DELETE RESTRICT.
- `uq_match_analyses_match_version`: UNIQUE(match_id, algorithm_version).
- `ix_match_analyses_match_id`: индекс match_id.
- `uq_user_match_history_user_match`: UNIQUE(telegram_user_id, match_id).
- `ix_user_match_history_user_recent`: (telegram_user_id, last_viewed_at DESC).
- `ix_user_match_history_match_id`: индекс match_id.
- CHECK положительных ID; допустимых fetch_status pending/ready/unavailable/failed; analysis status pending/ready/failed; completeness full/partial/missing или NULL; непустой algorithm_version.

Помимо четырёх сущностей существует служебная `alembic_version`, текущая версия — `0001_initial`. Dev-таблицы после миграции проверены: записей пользователей, матчей, отчётов и истории в них нет.

## Доступ к данным и авторизация

Engine и session factory создаются один раз в lifespan без начального соединения; запрос получает одну сессию, закрываемую и при ошибке. Pool освобождается при остановке. PostgreSQL timezone установлен в UTC, входные timestamps требуют timezone. В repositories транзакцией управляет вызывающая сторона, автоматического commit нет.

Пять внутренних операций: upsert_verified_user, upsert_match, save_analysis, record_view, recent_matches. ON CONFLICT предотвращает дубли. Одинаковая версия анализа сохраняет UUID, новая версия хранится отдельно. Запоздалый просмотр не уменьшает last_viewed_at. История фильтруется по пользователю и сортируется по убыванию времени.

VerifiedTelegramUser является только внутренним типом данных. Он не проверяет подпись и не означает готовую авторизацию. Конструирование из клиентского JSON запрещено контрактом; на следующем этапе этот объект должен появляться только после серверной проверки initData. Сейчас ни один публичный API не вызывает запись пользователя или истории.

## Файлы

Созданы:

```text
compose.yaml
scripts/init_local_env.py
scripts/local_postgres.py
backend/alembic.ini
backend/app/db/__init__.py
backend/app/db/base.py
backend/app/db/models.py
backend/app/db/session.py
backend/app/db/repositories.py
backend/migrations/env.py
backend/migrations/script.py.mako
backend/migrations/versions/0001_initial.py
backend/tests/conftest.py
backend/tests/test_database_health.py
backend/tests/test_repositories.py
backend/tests/test_migrations.py
docs/STAGE1_03_REPORT.md
```

Изменены:

```text
.gitignore
README.md
backend/.env.example
backend/pyproject.toml
backend/requirements.lock
backend/app/main.py
backend/app/core/config.py
backend/app/core/errors.py
backend/app/api/v1/health.py
backend/app/models/health.py
docs/AI_PROJECT_CONTEXT.md
docs/STAGE1_PLAN.md
```

Локально сгенерирован `backend/.env` с правами 0600; пароль не выводился. Runtime-каталог `.local/`, env, зависимости и кэши исключены Git. Файлы frontend не изменены — проверено сравнением SHA-256 с состоянием перед шагом. Все исходные файлы сохранены, технический план и read-only `sources/` не изменялись. Git остаётся без коммитов; изменения проверены по фактическому списку файлов и контрольным суммам, а не по пустому diff неотслеживаемых файлов.

## Фактические проверки

| Проверка | Результат |
| --- | --- |
| PostgreSQL version | PostgreSQL 17.11 (Homebrew) |
| Проектный сервер | scripts/local_postgres.py start: server started, loopback port 55432 |
| Отдельные БД | dota_hub, dota_hub_test, dota_hub_migration_test созданы без удаления существующих данных |
| Alembic upgrade head | Успешно |
| Alembic current | 0001_initial (head) |
| Повторный upgrade head | Успешно, без изменений схемы |
| Alembic check | No new upgrade operations detected |
| Полный pytest | **33 passed, 1 warning in 0.79s**, без пропусков |
| mypy | Success: no issues found in 22 source files |
| pip check | No broken requirements found |
| npm run build | TypeScript прошёл; Vite: 28 modules transformed, built in 197ms |
| HTTP /api/v1/health | 200, прежний точный JSON |
| HTTP /api/v1/health/db | 200, {"status":"ok","database":"available"} |
| /health/db через Vite proxy | 200, тот же JSON |
| БД остановлена | /health/db → 503 DATABASE_UNAVAILABLE, /health → 200 |
| БД снова запущена | /health/db → 200, pool восстановил соединение |
| Сохранность данных | Техническая запись в dota_hub_test пережила stop/start PostgreSQL |

Из 33 тестов 9 не требуют PostgreSQL, а 24 выполняют настоящие PostgreSQL-проверки. Проверены BIGINT без округления, JSONB и SQL NULL, UUID и UTC, upsert и отсутствие дублей, FK и RESTRICT, CHECK статусов, независимость версий отчёта, порядок и изоляция истории, поздние события, диапазон limit, откат транзакций, одна сессия на запрос и откат записи при ошибке HTTP-обработчика.

Цикл миграций выполнялся на `dota_hub_migration_test`: upgrade → повторный upgrade → metadata check → проверка отказа downgrade без флага → проверка отказа при наличии технической записи внутри savepoint → откат savepoint → разрешённый downgrade на пустой БД → upgrade → metadata check. Таблицы оставлены в head. Никакие dev/prod-таблицы не удалялись.

В `dota_hub_test` оставлена одна явно техническая строка matches для подтверждения сохранности (`test_fixture=restart-check`), без пользовательских данных и игровой статистики. Dev-БД остаётся пустой. Repository-тесты откатывают свои записи; тестовая БД миграций не содержит бизнес-записей.

## Команды для macOS

Полная инструкция — [README](../README.md). В корне проекта при первом запуске:

```sh
.venv/bin/python -m pip install -r backend/requirements.lock
.venv/bin/python scripts/init_local_env.py
```

При уже существующем backend/.env второй шаг не нужен. Текущий проверенный вариант:

```sh
.venv/bin/python scripts/local_postgres.py start
.venv/bin/python scripts/local_postgres.py create-databases
```

Альтернатива при установленном Docker, не одновременно с нативным сервером:

```sh
docker compose up -d db
docker compose exec db createdb -U dota_hub dota_hub_test
docker compose exec db createdb -U dota_hub dota_hub_migration_test
```

Создание test-БД требуется только один раз. Из backend:

```sh
../.venv/bin/python -m alembic upgrade head
../.venv/bin/python -m alembic check
../.venv/bin/python -m pytest
../.venv/bin/python -m mypy
../.venv/bin/python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Из frontend во втором терминале: `npm run dev`. В текущей сессии frontend, API и нативная БД работают локально. Автозапуск при входе в систему не настраивался.

## Ограничения и изменения окружения

- Docker отсутствует; container startup/restart и named-volume persistence требуют отдельной проверки при его установке. Нативная проверка не подменяет эту непроведённую проверку.
- В ограниченной среде первая загрузка Python-пакетов была недоступна, а initdb вернул `could not create shared memory segment: Operation not permitted`. После разрешённых сетевых/локальных запусков установка и сервер заработали. Действующих блокеров для нативного варианта нет.
- Homebrew при установке PostgreSQL обновил свои метаданные и необходимые системные зависимости, включая OpenSSL, readline, gettext, xz, zstd и сертификаты. Он также создал стандартный кластер `/opt/homebrew/var/postgresql@17`; этот кластер не запускался и проектом не используется. Глобальная системная служба не регистрировалась. После установки Python-проверки, HTTP и сборка приложения прошли.
- Сохранилось предупреждение Starlette TestClient о будущем переходе с httpx на httpx2; оно не подавлено и не мешает 33 тестам.
- Health/db проверяет соединение, а не актуальность миграций. Актуальность контролируется Alembic.
- Начальный downgrade намеренно ограничен пустой локальной migration-test БД. Это не сценарий отката production.
- Проверена одна локальная среда Python 3.13.7 / PostgreSQL 17.11. Другие ОС, production, резервное копирование и реальные Telegram WebView не проверялись.

## Передача на следующий этап

- [ ] Реализовать серверную проверку Telegram initData по официальной схеме и негативные тесты подписи/времени.
- [ ] Создавать VerifiedTelegramUser и вызывать пользовательские repositories только после этой проверки; исключить доверие client user ID.
- [ ] Добавить OpenDota adapter с тайм-аутами, Retry-After, ограничением запросов и обработкой неполных данных.
- [ ] Согласовать переходы fetch_status / analysis status, сроки хранения raw_payload и версии алгоритма.
- [ ] Подключить защищённую историю и сценарий анализа к существующей оболочке Dota Hub без фиктивной статистики.
- [ ] При появлении Docker проверить Compose и сохранность volume; перед публикацией отдельно настроить HTTPS, роли БД и резервное копирование.

Первый этап завершён в проверенной нативной локальной среде. Перехода к авторизации, внешним API или scoring без отдельного задания не было.
