# Этап 2 v2 промпт 06 — нормализация матча и статистики игроков

Дата: 22 октября 2026. Итог: реализация и автоматические проверки PASS. Использован snapshot-контракт промпта 05; live OpenDota и Telegram не вызывались.

## A. Изменения по файлам

Созданы:

- `backend/app/models/matches.py` — строгие неизменяемые Pydantic DTO: MatchSummary, PlayerStat, DraftRawData, MatchEventRawData, derived-метрики и data quality.
- `backend/app/services/match_normalization.py` — детерминированный сервис нормализации без I/O.
- `backend/tests/test_match_normalization.py` — полный, частичный и негативные сценарии.
- `docs/STAGE2_06_REPORT.md` — этот отчёт.

Изменены:

- `README.md` — контракт и ограничения нормализованной модели.
- `docs/AI_PROJECT_CONTEXT.md` — фактическое состояние после промпта 06.

Существующие bot, auth, ingestion и frontend-контракты не изменялись. Публичный endpoint не добавлен: он был необязательным, а новый API до шага 09 расширил бы поверхность без текущего потребителя.

Новая миграция не создана. Raw snapshot уже хранится в `matches.raw_payload`; нормализованная модель является детерминированным представлением и пока вычисляется внутренними модулями по требованию. Отдельное хранилище без политики версий/инвалидации создало бы преждевременное дублирование.

## B. Команды запуска и миграций

Обычный запуск проекта не меняется:

```sh
.venv/bin/python scripts/local_postgres.py start
cd backend
../.venv/bin/python -m alembic upgrade head
../.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Нормализатор вызывается внутренним Python-кодом:

```python
from app.services.match_normalization import normalize_match_snapshot

normalized = normalize_match_snapshot(snapshot, hero_names=hero_constants)
payload = normalized.model_dump(mode="json")
```

`hero_names` необязателен и является отдельным справочником. Без него ID сохраняется, а имя остаётся неизвестным.

## C. Выполненные проверки

| Проверка | Результат |
| --- | --- |
| Целевые тесты нормализации | PASS — 11 passed |
| `pytest -m 'not postgres'` | PASS — 160 passed |
| Полный `pytest` с PostgreSQL | PASS — 190 passed |
| `mypy` strict | PASS — 45 source files |
| `pip check` | PASS — broken requirements отсутствуют |
| `alembic current/check` | PASS — `0001_initial (head)`, новых операций нет |
| Frontend tests/typecheck/build | PASS — 11 tests, TypeScript и production build |
| Live OpenDota | NOT RUN — для нормализации используется контролируемый snapshot fixture |
| Telegram group smoke | NOT RUN — bot-контракт на этом шаге не менялся |

## D. Проверенные негативные и граничные случаи

- Ровно десять игроков и разделение 5 Radiant / 5 Dire.
- Дублированный, отрицательный, больше 255 и шестой slot одной команды отклоняются.
- Максимальный signed BIGINT Match ID сериализуется строкой; крупные team/Steam/account IDs не проходят через JavaScript number.
- Неизвестный положительный hero ID сохраняется, имя остаётся null без constants.
- Отсутствующий account ID остаётся null; fallback — `Игрок Radiant #N` / `Игрок Dire #N`.
- Числовой `0` остаётся доступным значением; missing/null/неверный тип не подменяется нулём.
- При deaths=0 KDA имеет `DENOMINATOR_ZERO`, а не придуманное число; при отсутствующих входах — `INPUTS_MISSING`.
- Null picks_bans означает unavailable. Bad order, duplicate order/action, missing order и invalid action фиксируются отдельно.
- Source order остаётся индексом исходного массива и не смешивается с player_slot или draft order.
- Unknown patch и неполный score снижают качество summary, не удаляя остальные данные.
- Отсутствующий teamfight/kills log и повреждённый advantage дают partial timeline; известные элементы advantage сохраняются.
- Без lane_role позиция unknown, не estimated. Одна известная роль не используется для вывода фарм-распределения команды.
- Повторная нормализация одного snapshot даёт идентичный JSON; входной объект не мутируется.

## E. Ограничения

- Нормализатор принимает snapshot schema version 1 и сообщает ошибку на повреждённой оболочке, Match ID или структуре players.
- Частичный список от 0 до 10 уникальных игроков допустим; data_quality.stats становится partial/unavailable. Полный статус требует 10 игроков и все основные stats.
- Имена героев разрешаются только переданным справочником. Названия items не добавляются и исходные item IDs сохраняются.
- `lane_role` считается confirmed evidence от источника. Собственная оценка позиции не выполняется.
- KDA и kill participation округляются до четырёх знаков и содержат `decimal_places=4`; нулевой знаменатель не заменяется единицей.
- Нормализованная модель не сохраняется отдельно и не опубликована HTTP endpoint. Bot пока сохраняет raw snapshot, а будущий analyzer может вызвать общий сервис.
- Формулы Draft Analyzer, Ruiner Analyzer, scoring, контрпики и реконструкция draft phases находятся вне промпта 06.

## F. Критерии приёмки

- Полный fixture создаёт MatchSummary и 10 PlayerStat — PASS.
- Известные значения partial snapshot сохраняются, неизвестные остаются null — PASS.
- Raw, normalized и derived разделены DTO — PASS.
- DraftRawData не реконструирует стадии/контрпики — PASS.
- Data quality оценивается отдельно для summary, stats, draft order, timeline и roles — PASS.
- player_slot не используется как порядок пика — PASS.
- Fallback names нейтральны и стабильны — PASS.
- Сериализация стабильна, вход не мутируется — PASS.
- Старые тесты остаются зелёными — проверяется финальным полным прогоном.

## Данные для промпта 7А

Draft Analyzer сможет получать без обращения к raw OpenDota:

- Match ID, patch, game mode, lobby type, команды, score, winner и data quality.
- Hero roster с team, stable player_slot, hero_id и отдельно разрешённым hero_name.
- Draft actions в исходном порядке: `source_order`, `is_pick`, `hero_id`, source `team_code`, normalized team и source `order`.
- Списки duplicate orders, duplicate actions, missing orders и invalid source indexes.
- Player stats и подтверждённый lane_role evidence как вспомогательный контекст, с availability каждого поля.

Нормализатор намеренно не предоставляет для 7А придуманные стадии, counterpick labels, matchup score, inferred pick ownership или estimated positions. Справочники героев/патча и правила Draft Analyzer должны иметь собственную версию и обрабатывать `draft_order != complete` явно.

## G. Следующий промпт

Промпт 06 завершён. После финального зелёного прогона можно переходить к промпту 7А, сохраняя перечисленные границы и не смешивая Draft Analyzer с Ruiner Analyzer.
