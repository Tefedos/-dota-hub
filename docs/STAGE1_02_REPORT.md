# Промпт 02 — отчёт выполнения

Дата: 21 октября 2026. Среда: macOS, Python 3.13.7, Node.js 22.18.0, npm 10.9.3.

## Результат

Создан локальный каркас единого Dota Hub с главной страницей `/` и разделом `/matches`. React получает настоящий `GET /api/v1/health` через Vite proxy. FastAPI использует Pydantic Settings, модульный router, типизированные ответы и единый формат ошибок. ID проверяется без потери точности; отчёты матчей не генерируются. Интерфейс использует графитово-синий фон, фиолетовые акценты, красные ошибки и зелёный статус доступности сервера.

Существующих функций Mini App до начала работы не было, что пользователь явно подтвердил. Роуты, пользовательские данные, авторизация и миграции не удалялись. Исходный технический план и read-only материалы рабочей области сохранены. Git инициализирован в `dota-hub/`; staging, коммиты и remote не создавались.

## Созданные файлы

```text
dota-hub/
  .gitignore
  README.md
  backend/
    .env.example
    pyproject.toml
    requirements.lock
    app/
      __init__.py
      main.py
      api/
        __init__.py
        v1/
          __init__.py
          health.py
      core/
        __init__.py
        config.py
        errors.py
      models/
        __init__.py
        health.py
        error.py
      services/
        __init__.py
    tests/
      test_api.py
  frontend/
    index.html
    package.json
    package-lock.json
    tsconfig.json
    vite.config.ts
    src/
      main.tsx
      app/App.tsx
      pages/HomePage.tsx
      pages/MatchesPage.tsx
      features/matches/MatchIdForm.tsx
      shared/
        api/client.ts
        ui/ServerStatus.tsx
        ui/styles.css
  docs/
    STAGE1_02_REPORT.md
```

Обновлены ранее существовавшие `docs/AI_PROJECT_CONTEXT.md` и `docs/STAGE1_PLAN.md`: подтверждён старт с нуля, зафиксировано выполнение инкремента 02, сохранена история аудита 01.

Локальные технические каталоги: `.git/`, `.venv/`, `frontend/node_modules/`, `frontend/dist/`, кэши Python/pytest/mypy. Это не исходники; зависимости, сборка, кэши и `.env` исключены из Git. Настоящий `.env` не создавался.

## Выполненные проверки

| Проверка | Команда / способ | Результат |
| --- | --- | --- |
| Backend smoke и ошибки | В backend: `../.venv/bin/python -m pytest` | 7 passed, 1 warning, 1.14 s |
| Строгие типы Python | В backend: `../.venv/bin/python -m mypy` | Success: no issues found in 13 source files |
| Совместимость Python-зависимостей | `../.venv/bin/python -m pip check` | No broken requirements found |
| TypeScript | `npm run typecheck`, выполнено внутри `npm run build` | `tsc --noEmit`, exit 0 |
| Production build | В frontend: `npm run build` | Vite 8.3.5: 28 modules transformed, built in 534 ms |
| Установка frontend | `npm install` с фиксацией прямых версий | 75 пакетов проверены установщиком; 0 vulnerabilities на момент установки |
| Реальный старт backend | `../.venv/bin/python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000` | Application startup complete |
| Реальный старт frontend | `npm run dev` | Vite ready, http://127.0.0.1:5173/ |
| Прямой HTTP | `curl --max-time 5 -si http://127.0.0.1:8000/api/v1/health` | 200 OK; точный JSON; application/json; no-store |
| HTTP через proxy | `curl --max-time 5 -si http://127.0.0.1:5173/api/v1/health` | 200 OK; тот же JSON и заголовки |
| Главная и навигация | Локальный браузер: `/` → «Анализ матча» → `/matches` → главная | Переходы работают, состояние сервера доступно |
| Прямая загрузка маршрута | Reload на `/matches` | Страница успешно открывается, health доступен |
| Пустой ввод | Отправка пустой формы в браузере | «Введите Match ID», фокус на поле |
| Неверный ввод | `0`, `-2`, `1.5`, `1e3`, `abc` | Контролируемая ошибка формата |
| Верхняя граница | `9223372036854775808` | Отклонён как превышающий bigint |
| Большие допустимые ID | `9007199254740993`, `9223372036854775807` | Приняты без округления; только сообщение «Функция в разработке» |
| Отсутствие backend | Остановить именно запущенный для проверки процесс, нажать «Проверить» | «Сервер недоступен», повторная проверка доступна |
| Восстановление backend | Перезапуск API, повторная проверка в UI | «Сервер доступен» |
| Мобильная адаптация | Главная и `/matches` при 320/390/430 px в браузере | scrollWidth равен innerWidth, горизонтального переполнения нет |
| Исключения Git | `git check-ignore` для venv, .env, node_modules, dist и кэшей | Все исключены |

Backend-тесты проверяют точный health-контракт, 404 для ещё не существующего анализа, 405 и Allow, безопасный 500, безопасный 422, отключение документации через env и отсутствие CORS-разрешения чужому origin. Служебные endpoint для негативных тестов добавляются только в тестовые экземпляры приложения.

Ручная проверка в браузере не является добавленным E2E-набором. Тайм-аут 5 секунд и отмена запроса реализованы в клиенте; отдельная симуляция зависшего ответа не проводилась. Реальные Telegram iOS/Android/Desktop не проверялись.

## Ограничения и возникшие проблемы

1. Ограниченная среда не разрешила загрузку пакетов: pip сообщил `Failed to establish a new connection: [Errno 8] nodename nor servname provided, or not known`, npm — `getaddrinfo ENOTFOUND registry.npmjs.org`. После разрешённого запуска с сетевым доступом зависимости установлены. Настройки глобального Python и npm не менялись.
2. Первоначальный старт серверов из ограниченной среды вернул `[Errno 1] Operation not permitted` и `listen EPERM ... 127.0.0.1:5173`. Запуск вне этого ограничения, с разрешением и привязкой только к loopback, прошёл успешно. Аналогично разрешённый curl подтвердил HTTP-ответы.
3. Starlette 1.9.0 выдаёт предупреждение о будущем переходе TestClient с httpx на httpx2. Это не ошибка тестов: все 7 проходят. Стек httpx сохранён; при следующем плановом обновлении тестовых зависимостей проверить переход по документации. Предупреждение не подавлялось.
4. pip в ограниченной среде предупреждает о недоступном каталоге кэша; это не препятствовало проверкам.
5. Git-репозиторий новый и без коммитов: обычный `git diff` не показывает неотслеживаемые файлы. Состав исходников проверяется через `git ls-files --others --exclude-standard`, а не по пустому diff. `.env`, зависимости и кэши в перечень не входят.

## Запуск и следующий шаг

Пошаговая установка и команды для двух терминалов приведены в [README](../README.md). На завершение проверки backend и frontend запущены локально; доступность после закрытия текущей сессии не гарантируется, для повторного запуска используйте README.

Не реализованы PostgreSQL, Alembic, OpenDota, scoring, timeline, Telegram SDK/initData/startapp, профиль, задания и история матчей. Следующий разрешаемый отдельным заданием инкремент — промпт 03, модели и миграции PostgreSQL. Самостоятельного перехода к нему не было.
