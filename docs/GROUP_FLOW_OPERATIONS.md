# Эксплуатация группового сценария Dota Hub

## Локальный запуск

Из корня проекта установите зависимости по README и запустите локальную PostgreSQL. В `backend/.env` задайте DATABASE_URL, BOT_TOKEN, SESSION_SECRET (отдельный от токена бота, минимум 32 байта), BOT_USERNAME и точный список TELEGRAM_ALLOWED_CHAT_IDS. Не печатайте .env в логи. OPEN_DOTA_API_KEY необязателен. Все примеры переменных находятся в `backend/.env.example`.

В отдельных терминалах:

```sh
cd backend
../.venv/bin/python -m alembic upgrade head
../.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

```sh
cd backend
../.venv/bin/python -m app.bot.main
```

```sh
cd frontend
npm run dev
```

Web-процесс не активирует polling. CI запускает только тесты с искусственным Telegram transport. Не направляйте ручную проверку в production-группу.

## BotFather и HTTPS

Создайте отдельного тестового бота в BotFather, настройте Main Mini App на HTTPS URL frontend, добавьте команду `match` с пояснением `Анализ по номеру матча`. Включите нужную тестовую группу в allowlist. Для команд `/match` отключать privacy mode не требуется; тестируйте `/match@BotUsername`, особенно при нескольких ботах. Разрешения бота должны позволять отправлять сообщения в группе.

В ответе используется `InlineKeyboardButton(url=...)` с `https://t.me/<username>?startapp=match_<id>`. Main Mini App и HTTPS должны быть настроены, иначе успешный unit-тест URL не гарантирует открытие клиента Telegram. Настоящий SDK передаёт `start_param` внутри initData; frontend также поддерживает startParam/tgWebAppStartParam только как подсказку маршрута. Подпись проверяет backend по полному initData. Переданная ссылка и `chat_instance` не дают групповых прав.

Основание: [официальные Telegram Mini Apps](https://core.telegram.org/bots/webapps#launching-mini-apps), [Bot API InlineKeyboardButton](https://core.telegram.org/bots/api#inlinekeyboardbutton). Данные Telegram нельзя считать проверенными только потому, что они получены от frontend.

## Deploy и запуск

Текущий `compose.yaml` поднимает только PostgreSQL для локальной разработки; это не production-конфигурация. Docker-окружение в этой сессии не проверялось. При контейнеризации backend запускайте web и bot отдельными сервисами из одного образа, применяйте миграцию отдельной одноразовой командой перед стартом и передавайте секреты через secret store/окружение. Не встраивайте `.env` в образ. Web может иметь несколько процессов, polling worker — один. Статику `frontend/dist` публикуйте за HTTPS reverse proxy с fallback `/matches/*` на index.html; `/api` направляйте в backend. Vite dev server не является production-хостингом.

Для production установите точный HTTPS origin в DOTA_CORS_ORIGINS и отключите публичный OpenAPI через DOTA_DOCS_ENABLED=false. Внешний порт PostgreSQL не публикуйте; сделайте резервные копии. Reverse proxy должен ограничивать размер запросов/частоту auth и закрывать служебные endpoints от ненужного внешнего доступа. При TLS termination сверяйте конфигурацию forwarded headers со своим proxy.

Startup бота проверяет BOT_TOKEN, DATABASE_URL, соединение с PostgreSQL, единственность worker через advisory lock, реальный username через getMe и соответствие BOT_USERNAME. Затем отмечает прерванные задания и запускает polling только для типов updates, зарегистрированных dispatcher (сейчас message). Код удаляет старый webhook перед polling; используйте только выделенный polling-токен.

Liveness: `/api/v1/health`. Readiness БД: `/api/v1/health/db`. Они не доказывают доступность Telegram или OpenDota. Статус отдельного анализа: `/api/v1/matches/{id}/analysis/status` после auth. Метаданные моделей и время вычисления доступны в каждом разделе.

## Перезапуск и ошибки

Внутри worker одновременные команды одного ID разделяют сохранённый результат. Второй worker на той же БД не должен стартовать: advisory lock защищает recovery и polling. При штатном завершении задачи отменяются с отметкой WORKER_RESTARTED; при аварийном завершении эта отметка ставится на следующем старте. Автоматическая повторная отправка в чаты не реализована: пользователь повторяет `/match`. Запись raw snapshot сохраняется; ingestion переиспользует TTL-кэш либо делает новый запрос. Повторные GET не восстанавливают worker и не инициируют анализ.

Ограничение группы — 10 принятых команд в минуту, дополнительно cooldown `(chat_id,user_id)` и ограничение активных задач. Эти счётчики живут в памяти и сбрасываются при перезапуске. Для нескольких независимых бот-реплик потребуется отдельное проектирование распределённой обработки; текущая конфигурация запрещает второй worker.

OpenDota 429 хранится с bounded retry interval; недоступность и некорректный ответ имеют короткий отрицательный TTL. Ошибка одного анализатора оставляет доступными другие разделы; status перечисляет их и сообщает ANALYSIS_FAILED. Сохранение отчётов и итогового состояния происходит одной транзакцией. GET проверяет совпадение fingerprint источника и не смешивает версии. Повреждённый сохранённый DTO приводит к безопасному 503.

Логируются match_id, имя раздела и класс ошибки. Не логировать BOT_TOKEN, Authorization, initData, сырые тела Telegram/OpenDota или exception text с секретами. Telegram delivery failure не удаляет уже сохранённые отчёты; повторная команда отдаст кэш.

## Live E2E — отдельный чек-лист

Состояние в №09: **BLOCKED — не предоставлены настроенный тестовый бот/группа, Main Mini App и HTTPS deployment для реальной приёмки**. Локальные тесты используют фиктивный Telegram transport и OpenDota provider.

1. Проверить разрешённую тестовую группу и отдельный токен; стартовать один worker.
2. Отправить `/match <реальный Match ID>` и `/match@BotUsername <id>`; проверить быстрое подтверждение и краткий результат в той же группе.
3. Повторить команду после cooldown; убедиться в кэше. Проверить запрет другой группы и ответ на 0.
4. Нажать «Подробный анализ» на iOS/Android/Desktop; подтвердить Main Mini App, HTTPS, auth, нужный ID и чтение API.
5. Переслать ссылку другому авторизованному пользователю: MVP намеренно позволяет чтение известного матча. Проверить отказ без сессии.
6. Проверить partial/failure без выдуманных оценок, восстановление после worker restart и отсутствие дублей polling.
7. Зафиксировать реальные время/версию/клиенты и результат каждого пункта, не публикуя токены или initData.
