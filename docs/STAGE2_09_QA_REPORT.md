# Этап 2 v2 — промпт №09: Group Flow, REST API и QA

Дата завершения: 23 октября 2026. Работа продолжена в существующем `dota-hub/` после №08. Требования извлечены из предоставленного документа; проверены текущий код, контекст, план/QA этапа 1, зависимости и миграции. Файлы `sources/` не менялись. Реальные polling и сообщения в Telegram не запускались.

**Решение: GO для перехода к локальной разработке интерфейса этапа 3.** Обязательные локальные функциональные и контрактные проверки прошли. **Live Telegram/HTTPS — BLOCKED**, поэтому это не утверждение о полной проверке в Telegram и не production GO. Известные ограничения драфта, confidence и partial data сохраняются.

## A. Изменения по файлам

Созданы:

| Файлы | Назначение |
| --- | --- |
| `backend/app/models/match_api.py` | Публичные Overview/Players DTO, envelope v1, состояние и безопасная ошибка |
| `backend/app/services/match_analysis.py` | Общий процесс ingestion → normalization → draft/ruiner/timeline, версии/сохранение/кэш/recovery, короткая сводка |
| `backend/app/api/v1/matches.py` | Шесть авторизованных read-only маршрутов, HTTP-состояния, проверка сохранённых DTO, timeline filters |
| `backend/tests/test_group_flow.py` | 17 новых проверок, включая реальную тестовую PostgreSQL и fake Telegram transport |
| `backend/tests/fixtures/group_flow/8888765469.json` | Синтетическая входная фикстура; не результат внешнего запроса этого ID |
| `backend/tests/fixtures/group_flow/contracts.json` | Версионированный JSON snapshot OpenAPI match routes и связанных схем |
| `scripts/export_match_contracts.py` | Воспроизводимый экспорт JSON-контракта |
| `frontend/src/features/matches/api.ts` | Авторизованный fetch, отмена/timeout и безопасные состояния |
| `frontend/src/features/matches/contract.test.tsx` | 9 frontend-проверок start-param/auth/fetch/pending/errors/ID |
| `frontend/src/pages/MatchReportPage.tsx` | Минимальная заглушка пяти разделов и чтения API |
| `ruff.toml`, `backend/requirements-qa.txt` | Воспроизводимая политика lint E9/F и отдельные QA-инструменты; runtime-зависимости не меняются |
| `docs/GROUP_FLOW_OPERATIONS.md` | Запуск, BotFather/Main Mini App, HTTPS/deploy, restart, security и live-чек-лист |
| `docs/STAGE3_FRONTEND_HANDOFF.md` | DTO, состояния, русские тексты, вкладки, ограничения и визуальный ориентир этапа 3 |
| `docs/history/AI_PROJECT_CONTEXT_BEFORE_09.md` | Сохранённая история контекста до актуализации |
| `docs/STAGE2_09_QA_REPORT.md` | Настоящий отчёт |
| `docs/audits/stage2_09_backend_tests.txt`, `stage2_09_frontend_tests.txt`, `stage2_09_mypy.txt` | Выводы финальных проверок |
| `docs/audits/stage2_09_python_audit.json`, `stage2_09_npm_audit.json` | Фактические отчёты аудита зависимостей |

Изменены:

- `backend/app/main.py`, `backend/app/core/errors.py`: подключены маршруты и match envelope ошибок, старые health/auth/unknown-route контракты сохранены.
- `backend/app/bot/services.py`: подключение общего процесса, лимит группы 10/минуту, ограничение активных задач; прежний путь сохранён для совместимости существующих callers/tests.
- `backend/app/bot/handlers.py`: обычная URL-кнопка «Подробный анализ», ограничение сообщения, `parse_mode=None`.
- `backend/app/bot/main.py`: создание общего сервиса, singleton PostgreSQL lock, проверка username, recovery на старте, безопасный вывод ошибок.
- `backend/app/services/draft/scoring.py`: только удалён неиспользуемый импорт `Tag`, вычисления не изменены.
- `frontend/src/app/App.tsx`, `features/auth/AuthStatus.tsx`, `features/auth/telegram.ts`: сессия в памяти передаётся экрану матча, читается start-параметр и выполняется переход после auth.
- `frontend/src/pages/HomePage.tsx`, `pages/MatchesPage.tsx`, `features/matches/MatchIdForm.tsx`: текущий групповой сценарий и тексты вместо устаревших обещаний профилей/заданий.
- `.gitignore`, `README.md`, `docs/AI_PROJECT_CONTEXT.md`: исключён cache lint, описан текущий продукт/запуск/контракт.

Используется существующая таблица `match_analyses`: пять записей разделов и одна состояния, уникальные по `(match_id,algorithm_version)`. Сохраняются source fingerprint, model/config versions, computed_at и completeness. Raw snapshot остаётся в `matches`. Новых таблиц, миграций, микросервисов и UI следующего этапа нет.

## B. Фактические команды и запуск

Из `backend/`:

```sh
../.venv/bin/python -m pytest --tb=short
../.venv/bin/python -m mypy
../.venv/bin/python -m pip check
../.venv/bin/python -m alembic current
../.venv/bin/python -m alembic check
```

Из `frontend/`:

```sh
npm test -- --run
npm run build
npm audit --json --registry=https://registry.npmjs.org
```

QA-инструменты установлены отдельно во временный venv `/tmp/dota-hub-qa09`; первоначальный настроенный pip index не предоставил Ruff, установка из официального PyPI прошла. Версии закреплены в `backend/requirements-qa.txt`. Из корня выполнены:

```sh
/tmp/dota-hub-qa09/bin/ruff check backend/app backend/tests scripts
/tmp/dota-hub-qa09/bin/pip-audit -r backend/requirements.lock --no-deps --disable-pip --progress-spinner off --format json --output /tmp/dota-hub-backend-audit09.json
.venv/bin/python scripts/export_match_contracts.py
git status --short
git diff --check
git diff --stat
git check-ignore backend/.env .ruff_cache
```

Запуск приложения не изменён: backend — `../.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000` из `backend/`; bot — `../.venv/bin/python -m app.bot.main`; frontend — `npm run dev` из `frontend/`. Не запускать второй polling worker. Полные prerequisites и production-чек-лист — [GROUP_FLOW_OPERATIONS.md](GROUP_FLOW_OPERATIONS.md). Миграция №09 не нужна, текущая — `0001_initial`.

Тесты БД выполнялись с разрешённым доступом к локальной PostgreSQL. Migration test сам проверяет отдельное имя `dota_hub_migration_test` и отсутствие пользовательских данных перед downgrade; dev-БД не откатывалась.

## C. Матрица реально выполненных проверок

| Проверка | Результат и доказательство |
| --- | --- |
| Полный backend pytest | **PASS — 306**, 6.33 с; [вывод](audits/stage2_09_backend_tests.txt); включает все 289 прежних и 17 новых |
| Frontend vitest | **PASS — 20**, два файла; [вывод](audits/stage2_09_frontend_tests.txt) |
| mypy | **PASS — 67 файлов**, [вывод](audits/stage2_09_mypy.txt) |
| TypeScript / Vite build | **PASS**, 33 модуля, сборка создана |
| Ruff, принятую политику E9/F | **PASS** на backend/app, backend/tests, scripts |
| Дополнительный lint изменённых Python-файлов | **PASS**, E9,F,I,BLE,C408,SIM114,RUF059; намеренные защитные exception boundaries пояснены |
| pip check | **PASS — No broken requirements found** |
| Alembic current / check | **PASS — 0001_initial (head); No new upgrade operations detected** |
| Upgrade → повторный upgrade → downgrade → upgrade на пустой отдельной test-БД | **PASS**, включён test_migrations в полный pytest; защита от непустой БД проверена |
| /match и /match@username, 0, чужой username, другая группа, duplicate/cooldown | **PASS**, текущие test_bot_handlers/test_bot_services + test_group_flow |
| Лимит группы между разными отправителями | **PASS**, 11-я команда группы ограничена; другая разрешённая группа независима |
| Два concurrent chats, повторная команда, новый service после restart | **PASS**, один fetch/evaluation на один неизменный snapshot, результат доставлен обоим fake chat |
| Worker recovery | **PASS**, pending → failed/WORKER_RESTARTED, повторная команда → ready |
| OpenDota full/partial/нет данных/429/неверные массивы | **PASS**, текущие ingestion/provider тесты и новые 404/429/502/503 через storage/API |
| Draft FINAL_ONLY, unknown patch, missing picks_bans, SEQUENTIAL контракт | **PASS**, at_pick и final остаются раздельными полями; отсутствие оценки не маскируется |
| Ruiner low confidence, timeline partial, anti-fabrication | **PASS**, прежние тесты анализаторов + публичные DTO/сводка |
| GET 200/202/404/401/503, также 422/429/502 | **PASS**, реальные FastAPI/SQLAlchemy запросы с синтетически подписанным initData |
| Schema snapshot, неверные/отсутствующие поля сохранённого DTO | **PASS**, контракт совпадает с OpenAPI; повреждённая запись даёт безопасный 503 |
| Auth hash/date/expiry/подмена/дубликаты полей | **PASS**, существующие auth/session тесты включены в полный прогон |
| Запрет raw endpoint, отсутствие account/steam/player names в публичных DTO | **PASS**, raw — 404, allowlist PublicPlayer подтверждён |
| Replay/пересылка match link | **PASS**, другой авторизованный пользователь читает анализ; без сессии — 401 |
| Длинные provider names и HTML в групповой сводке | **PASS**, в текст не включаются, parse_mode=None, длина <4096, кнопка url без web_app |
| E2E dispatcher → fake OpenDota → PostgreSQL → auth → API | **PASS**, fake Telegram transport; не живая группа |
| React startParam/raw initData, переход, bearer fetch, no-auth, 202, 401/404/429/503, неверный ID/ответ | **PASS**, 9 новых contract smoke сценариев |
| Backend package vulnerability review | **PASS — 47 закреплённых пакетов, 0 известных уязвимостей, 0 skipped**; [JSON](audits/stage2_09_python_audit.json) |
| Frontend package vulnerability review | **PASS — npm сообщает 147 dependencies, 0 известных уязвимостей всех уровней**; [JSON](audits/stage2_09_npm_audit.json) |
| Git diff/check/status, игнорирование секретов/cache | **PASS с ограничением:** исходное дерево untracked, baseline-коммита нет; diff пустой и не заменяет проверку файлов/тестов |
| Live Telegram / HTTPS Main Mini App | **BLOCKED**, отдельный доступ и развёртывание не подтверждены; [чек-лист](GROUP_FLOW_OPERATIONS.md#live-e2e--отдельный-чек-лист) |
| Новый live OpenDota запрос для 8888765469 | **NOT RUN**, ID используется только в синтетической фикстуре |
| Docker deploy, Telegram iOS/Android/Desktop | **NOT RUN**, локальные mocks и сборка не доказывают поведение этих сред |

Аудиты пакетов — снимок известных записей базы на время проверки, не гарантия отсутствия будущих/неизвестных уязвимостей. `--no-deps --disable-pip` использован с полным существующим lockfile; пропущенных пакетов в отчёте нет. Приложение не обновлялось ради аудита.

## D. Негативные случаи и исправления по ходу QA

Первый запуск тестов обнаружил несовместимость нового envelope с прежним тестом неизвестного route. Исправлено: match envelope применяется к зарегистрированным match routes, неизвестные маршруты сохраняют старую ошибку. Дополнительные проверки подтвердили отсутствие регрессии health/auth.

Обработаны ошибочные ID, неподписанная авторизация, просроченная сессия, query user_id/chat_instance как попытка обхода, отсутствующая БД, пропавшие arrays, неизвестный patch, null score, неизвестные позиции, источник 429/недоступен/некорректен, повреждённый stored DTO и несогласованный source digest. Ошибка отдельного анализатора не теряет остальные отчёты. Последующая запись нового snapshot инвалидирует кэш. GET не вызывает анализатор или OpenDota, даже после повторного чтения.

Отдельно сохранена осторожность вывода: нет произвольного «руинера» при low confidence; нет принудительного score=50; timeline неизвестные события не восстанавливает; group summary не использует свободные пользовательские строки и не превышает лимит сообщения.

## E. Дефекты, ограничения и остаточные риски

| Severity | Состояние | Описание |
| --- | --- | --- |
| P1 | Закрыто | В предыдущем этапе не было единого сохранённого анализа/API; №09 добавляет весь локальный путь и E2E-test |
| P2 | Закрыто | Запрос по ссылке не должен выдавать raw идентификаторы: публичный allowlist и авторизация проверены |
| P2 | BLOCKED live acceptance | Реальная доставка и открытие Main Mini App/HTTPS не проверены; без этого production GO не выдан |
| P3 | Известно, не блокирует локальный GO | Старое StarletteDeprecationWarning об httpx/TestClient; все тесты проходят |
| P3 | Технический долг, вне gate | Первичный запуск расширенного набора правил Ruff 0.17.1 выявил также старые import/style/exception/closure замечания. После очистки изменённых файлов вне принятой политики осталось 58 замечаний. Для первого внедрения закреплена проверка E9/F всего проекта; работающие анализаторы не переформатированы. Замыкание compare в performance вызывается синхронно внутри текущей итерации, отложенных вызовов нет |
| Ограничение модели | Ожидаемо | Современный Draft Analyzer часто FINAL_ONLY/null; механическое/патчевое покрытие ограничено. №09 не добавляет новые правила, matchup fetch или рекомендации альтернативных героев |
| Ограничение MVP | Документировано | Любой авторизованный пользователь может читать известный Match ID; приватность по группе не обеспечивается и не имитируется chat_instance |
| Ограничение эксплуатации | Документировано | Один polling worker на БД; in-memory rate limits сбрасываются после рестарта; автоматической повторной доставки в чат нет, пользователь повторяет команду |
| Ограничение UI | По объёму этапа | Есть только auth/routing/fetch заглушка, подробный дизайн и отображение — этап 3 |

Незакрытых воспроизводимых P0/P1 дефектов в локальной приёмке не найдено. Тестирование не заявляется исчерпывающим. Нет изменений секретов и действий в реальных чатах.

## F. Критерии приёмки

- **PASS:** единый ручной групповой сценарий с быстрым ack, сохранением snapshot и независимых versioned reports, безопасной короткой сводкой и обычной URL-кнопкой.
- **PASS:** шесть read-only маршрутов с envelope/schema version, статусами/ошибками, auth и публичными DTO; health сохранён.
- **PASS:** повторные команды используют сохранённый анализ, concurrent chats не дублируют работу, повторные GET не вычисляют отчёты.
- **PASS:** partial/unavailable, ограничения источников, nullable scores и low confidence видны без выдуманных результатов.
- **PASS:** минимальный React contract smoke, актуальный контекст, production runbook и передача этапу 3.
- **PASS:** обязательный локальный регресс, типы, принятая lint-политика, миграции, сборка, vulnerability review.
- **BLOCKED:** живой Telegram + Main Mini App + HTTPS — отдельная приёмка, локальные проверки её не заменяют.

## G. Готовность к следующему промпту

**GO к этапу 3 в локальной среде.** Серверные контракты и сценарий готовы для подробного React-интерфейса. Актуальная передача: [STAGE3_FRONTEND_HANDOFF.md](STAGE3_FRONTEND_HANDOFF.md). Production и реальная Telegram-доставка требуют выполнения live-чек-листа; эти проверки не объявлены пройденными.
