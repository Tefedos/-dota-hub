# Передача frontend: Dota Hub после №09

## Сценарий и границы

Пользователь отправляет `/match <id>` в Telegram-группе. Бот подтверждает запрос, сохраняет raw snapshot и пять отчётов, присылает короткую сводку с URL-кнопкой «Подробный анализ». Main Mini App открывается с `startapp=match_<id>`. React передаёт **полную raw initData** в `/api/v1/auth/telegram`, получает bearer session, проверяет `/api/v1/auth/me` и запрашивает готовые разделы. Start-параметр — выбор матча, не авторизация. Матч ID всегда строка; диапазон 1…9223372036854775807, без знака, нулей в начале и экспоненты.

Текущая React-заглушка `/matches/:matchId` уже проходит этот сценарий и fetch. Высокоточный интерфейс — этап 3. Отображать только пять вкладок: **Обзор; Драфт; Игроки; Ход матча; Индекс ошибок / Вывод**. Новый анализ запускается командой группы; браузерные GET не ставят задания.

## Источник контракта

Машиночитаемый снимок шести маршрутов и связанных схем: [contracts.json](../backend/tests/fixtures/group_flow/contracts.json). Он сверяется тестом с FastAPI OpenAPI. Обновление: `.venv/bin/python scripts/export_match_contracts.py` из корня. Точные DTO: `backend/app/models/match_api.py`, `draft.py`, `performance.py`, `timeline.py`.

Для всех match routes: `Authorization: Bearer <session>`, `Accept: application/json`, `Cache-Control: no-store`. Токен хранить только в памяти приложения, не в URL, localStorage и не в логах. Предусмотреть явный повтор входа по истечении сессии. При смене ID или вкладки отменять старый запрос и не показывать результат другого матча.

## JSON-конверт v1

```json
{
  "schema_version": 1,
  "match_id": "8888765469",
  "status": "ready",
  "available_sections": ["overview", "players", "draft", "ruiner", "timeline"],
  "data": {},
  "error": null,
  "limitations": [],
  "model_version": "overview_v1",
  "config_version": "<sha256>",
  "analyzed_at": "<ISO-8601 UTC>",
  "completeness": "partial",
  "retry_after_seconds": null
}
```

Это схематический пример, не реальные данные матча. `data` имеет тип выбранного раздела ниже. `status` — queued/running/ready/failed; completeness — full/partial/missing или null. `error` — `{code,message,retryable}` либо null. Возможен ready-раздел с общей ошибкой другого анализатора: доступность именно этого раздела определяется HTTP 200 + data, ограничения остаются видимыми. `available_sections` указывает сохранённые разделы, а не гарантированную полноту их данных.

| GET `/api/v1/matches/{id}/…` | `data` |
| --- | --- |
| `overview` | match_id, duration (секунды/null), radiant/dire `{team,team_id,name,score}`, winner/null, start_time/null, game_mode/null, patch/null, data_quality по категориям, source_status |
| `players` | match_id, players: массив до 10 записей; player_slot, team, team_player_number, display_name, hero_id/name, kills/deaths/assists, last_hits/denies, gpm/xpm, damage/healing, net_worth, items, neutral_item, position; статистики nullable |
| `draft` | mode SEQUENTIAL/FINAL_ONLY, actions, pick_events с visibility, at_pick/final_context, at_pick_score/final_score/post_pick_delta, stages и counters/synergies; teams Radiant/Dire, draft_advantage, coverage, confidence внутри evaluations, model/config/evidence digests, limitations |
| `ruiner` | players с error_index/null, confidence, evidence_coverage, positive/negative_signals, reason_codes, role/position; teams и summary.selection_status; quality и limitations |
| `timeline` | events, gold_adv_points, xp_adv_points, turning_points, quality/timeline_data_status, available/supported/missing types, event_coverage, empty_state_text, limitations |
| `analysis/status` | status, available_sections, error_code/null |

Timeline поддерживает `?type=hero_kill&side=radiant`. Типы: first_blood, hero_kill, tower, building, roshan, aegis, buyback, purchase, teamfight. Side: radiant/dire; неизвестная сторона не совпадает с фильтром. Фильтр меняет events, но сохраняет полный список related_event_ids внутри turning_points: нужное событие может быть скрыто выбранным фильтром. Для jump-to-event сбросить фильтры. Время exact — time_seconds; source interval — time_start/time_end и time_seconds=null. Pregame время бывает отрицательным.

## HTTP и состояния

| Состояние | Ответ и текст UI |
| --- | --- |
| Авторизация отсутствует/истекла | 401 AUTH_REQUIRED/INVALID_SESSION/SESSION_EXPIRED: «Откройте приложение через Telegram заново» |
| Неверный ID/фильтр | 422 INVALID_MATCH_ID/INVALID_EVENT_TYPE/VALIDATION_ERROR: «Некорректная ссылка на матч» |
| Матч не запрашивали | 404 MATCH_NOT_FOUND: «Отправьте /match с этим номером в группе» |
| OpenDota не нашла матч | 404 NOT_FOUND: «Матч не найден в OpenDota» |
| Анализ queued/running | Раздел 202, data=null, Retry-After: 2; «Матч обрабатывается…»; текущий smoke обновляется кнопкой |
| Существующая запись статуса | status endpoint всегда 200, в том числе failed; смотреть data.status/error_code |
| Ограничение OpenDota | 429 RATE_LIMITED, retryable=true, Retry-After при наличии; «Повторите позже» |
| OpenDota недоступна | 503 API_UNAVAILABLE; «OpenDota временно недоступна» |
| Некорректный ответ источника | 502 MALFORMED_RESPONSE; «Не удалось разобрать данные матча» |
| Ошибка отдельного анализатора | 503 ANALYSIS_FAILED для его раздела, остальные могут отвечать 200; «Раздел временно недоступен» |
| Worker прервался | 503 WORKER_RESTARTED; «Повторите /match в группе» |
| БД/отчёт недоступны | 503 DATABASE_UNAVAILABLE/REPORT_UNAVAILABLE; «Анализ временно недоступен» |
| Partial/unavailable данные внутри готового отчёта | 200; показывать реальные данные и явное empty/partial state, не заполнять пропуски нулями |

403 зарезервирован для будущих проверок доступа. В текущем MVP нет приватности группы: любой авторизованный пользователь может прочитать анализ известного Match ID. Пересланная ссылка работает после auth. Нельзя выводить «участник группы подтверждён» на основании chat_instance. Raw snapshot route отсутствует; UI не должен его ожидать. Health и auth сохраняют свои прежние конверты, match v1 envelope применяется к шести новым маршрутам.

## Требования к пяти экранам

**Обзор:** длительность, команды Radiant/Dire, счёт, победитель только при наличии, источник и полнота. Не превращать отсутствующий winner в победу одной из команд.

**Драфт:** показывать стадии только при SEQUENTIAL. При FINAL_ONLY писать «Доступны только финальные составы; порядок и видимость пиков не подтверждены». at_pick_score и final_score — разные поля; null не становится 50/0. Раскрывать причины/контры/синергии и confidence. Не предлагать альтернативных героев: это отдельная будущая задача. Текущее покрытие ограничено: каталог 127 героев, механические профили 11 героев для patch=60, подтверждённая последовательная политика game_mode=22/patch=46. №09 не запрашивает дополнительные matchup statistics.

**Игроки:** группировка Radiant/Dire, нейтральные подписи «Игрок … #…», показатели nullable. Не выводить Steam/account/Telegram IDs. Unknown position не превращать в позицию 1–5.

**Ход матча:** фильтры событий и стороны; минуты/секунды и интервалы отображать различимо. Gold/XP положительный знак — Radiant, отрицательный — Dire. Отсутствующий график не рисовать нулевой линией. Возможные переломы — отдельные карточки, без формулировок «эта смерть проиграла матч».

**Индекс ошибок / Вывод:** относительная эвристика с причинами, положительными сигналами и ограничениями. `no_confident_selection` — полноценный результат, показывать «Недостаточно данных для уверенного вывода». Не выбирать «руинера» вручную из low-confidence результатов и не скрывать положительный вклад.

## Визуальный ориентир

Основной референс — существующие токены [styles.css](../frontend/src/shared/ui/styles.css) и текущий shell: графитовый фон, тёмно-фиолетовые акценты, светлый текст, сдержанные панели. Концепция задана словами; отдельного утверждённого пиксельного макета нет. Этап 3 должен подготовить мобильную компоновку с safe areas Telegram, доступным контрастом, видимым фокусом и состояниями loading/error/empty/partial. Красный использовать для отрицательных сигналов без обвинительных ярлыков, фиолетовый — для навигации и акцентов. Придерживаться существующей типографики до отдельного решения о дизайне.

Имена команд и любые строки источника выводить обычным React text rendering; не применять `dangerouslySetInnerHTML`, не интерпретировать Markdown/HTML из API. Длинные тексты ограничивать визуально с доступным раскрытием. Не показывать пользователю сырые JSON и технические fingerprints в основном интерфейсе.

## Приёмка этапа 3

Проверить deep link с signed raw initData, истечение/отказ auth, перемещение по пяти вкладкам, pending → ready, 404/429/502/503, повторную загрузку, long/null data, FINAL_ONLY, unknown position, отсутствие timeline curves, отмену запроса при смене матча. Live Telegram iOS/Android/Desktop требует отдельно настроенных Main Mini App и HTTPS; локальные mocks не заменяют эту проверку.
