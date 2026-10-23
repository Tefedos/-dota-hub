# Smoke-приёмка этапа 1 перед промптом 04

Дата: 22 октября 2026. Проверки выполнены **до изменения auth-кода**. Отчёта STAGE1_QA_REPORT.md ранее не было; изучены исходники, README, AI_PROJECT_CONTEXT, STAGE1_PLAN, отчёты 02/03 и git status/diff.

В репозитории присутствовали FastAPI, React/TypeScript/Vite, PostgreSQL 17.11, SQLAlchemy/asyncpg, Alembic 0001_initial и четыре таблицы. Telegram auth отсутствовала. Пользователь подтвердил переход к этапу 2. Существующий Git ещё без коммитов: 52 неигнорируемых файла не отслеживались; перед работой сохранён контрольный снимок SHA-256. Пустой git diff сам по себе не использовался как доказательство отсутствия изменений.

| Команда / проверка | Результат |
| --- | --- |
| backend: `../.venv/bin/python -m pytest -m 'not postgres'` | PASS: 9 passed, 24 deselected |
| backend: `../.venv/bin/python -m mypy` | PASS: 22 файла |
| frontend: `npm run build` | PASS: TypeScript и Vite |
| backend: `../.venv/bin/python -m alembic current` | PASS: 0001_initial (head) |
| backend: `../.venv/bin/python -m alembic check` | PASS: No new upgrade operations detected |
| `curl -fsS http://127.0.0.1:8000/api/v1/health` | PASS: status ok, service dota-hub-api |
| `curl -fsS http://127.0.0.1:8000/api/v1/health/db` | PASS: status ok, database available |

Решение: **GO для ограниченного промпта 04**. Блокирующих дефектов и неработающих миграций не выявлено. Полный повтор цикла downgrade/upgrade в этой smoke-приёмке NOT RUN: миграции не меняются, разрушительные операции не требуются. Это короткая локальная проверка, не production-сертификация.

Известно: предупреждение Starlette об устаревающем использовании httpx в TestClient присутствовало до изменений и не влияло на результат. Docker отсутствует; проверялась действующая нативная PostgreSQL. Проверка внутри Telegram относится к следующей работе и здесь не заявляется.
