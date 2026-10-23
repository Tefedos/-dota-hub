# Dota Hub — Backend вкладки «Обзор»

**Статус: READY FOR QA.** Задачи OV-01, OV-02, OV-03, OV-05 реализованы в существующем API. UI, алгоритмы Draft/Timeline/Ruiner и глобальные enum не менялись. Коммита нет.

## Аудит до изменений

Маршрут `GET /api/v1/local-alpha/matches/{match_id}/overview` уже существовал в `backend/app/api/v1/local_alpha.py` как локальный алиас к общему хранилищу `stored()` из `backend/app/api/v1/matches.py`. Основной авторизованный маршрут — `GET /api/v1/matches/{match_id}/overview`. Оба используют `OverviewReport` из `backend/app/models/match_api.py`. Отчёт создаётся `public_base()` из `NormalizedMatch`; повторного запроса OpenDota при GET нет. Составы, публичные имена и ID героев уже нормализовались для «Игроков», а общий закреплённый каталог содержал имена и изображения героев.

Новой логики требовали вложенные публичные составы Overview, названия режима/патча из закреплённого справочника и явные ограничения доступности данных. В нормализованной модели нет надёжного полного счётчика разрушенных башен или убийств Roshan. Статус строений не равен количеству разрушенных башен, а неполные `objectives` нельзя считать полным счётчиком Roshan.

## Контракт и источники

| Новое поле | Источник и правило |
|---|---|
| `radiant.players`, `dire.players`, `player_slot`, `hero_id` | `NormalizedMatch.players`, сортировка по исходному слоту, сторона из нормализации; отсутствующих игроков не добавляем |
| `hero_name`, `hero_image_url` | Общий `hero_catalog.json`, закреплённый commit `5c0242df9057848fa2036ca3fafe9f2bd4508163`; неизвестный ID → `null` |
| `display_name` | Нормализованный `personaname` OpenDota только при `is_anonymous=false`; иначе `null` |
| `game_mode_name`, `patch_name` | Новый локальный `match_metadata_catalog.json`, тот же закреплённый commit OpenDota; ключ режима переведён в читаемый Title Case, версия патча взята дословно; неизвестный ID → `null` |
| `team_stats.*.kills` | Итоговый счёт соответствующей стороны, в том числе `null`, если счёт неизвестен |
| `team_stats.*.towers_destroyed`, `roshan_kills` | `null`: подтверждённого полного счётчика нет |
| `limitations` | Неполный состав, неизвестные метаданные, ограниченность источника/хронологии и недоказанные дополнительные показатели |

Каталог режимов содержит 26 ID, каталог патчей — 61 ID. Источники: [game_mode.json](https://raw.githubusercontent.com/odota/dotaconstants/5c0242df9057848fa2036ca3fafe9f2bd4508163/build/game_mode.json), [patch.json](https://raw.githubusercontent.com/odota/dotaconstants/5c0242df9057848fa2036ca3fafe9f2bd4508163/build/patch.json). Для режима 22 исходный ключ `game_mode_all_draft` отображается как `All Draft`; для патча 60 имя `7.41`. Совпадение ID в каталоге подтверждает подпись, но не механическую применимость данных героев к историческому патчу.

Существующие `duration` (секунды) и `start_time` (Unix UTC seconds) не преобразованы. Для реального матча `8888765469` остались `2608` и `1783622517`, счёт `30:49`, победитель Dire. `schema_version=1`; новые DTO-поля имеют значения по умолчанию, поэтому старые сохранённые отчёты читаются. `model_version` Overview повышена через существующий механизм сохранения до `overview_v2`; глобальный `config_version` обновляется digest конфигурации, что запускает пересчёт сохранённых секций при следующем анализе.

`status=ready` означает, что отчёт раздела сохранён и доступен. `source_status=FOUND_PARTIAL` означает неполный ответ OpenDota целиком. `completeness=full` относится только к базовым полям Overview, включая обе пятёрки, а не к хронологии и дополнительным метрикам. Поэтому сочетание `ready`/`FOUND_PARTIAL`/`full` у `8888765469` корректно: базовый обзор полный, `data_quality.timeline=unavailable`. `available_sections` означает наличие сохранённого отчёта раздела; отчёт Timeline может существовать с `quality=unavailable`. Это явно отражено в `limitations`, `error=null` остаётся корректным для доступного отчёта. Парсинг и расширенная статистика не блокируют базовый обзор.

## Проверенные ответы

Полные JSON-ответы локального API после пересчёта:

- [8888765469](qa/overview_8888765469_response.json): HTTP 200, 5+5 игроков, `All Draft`, `7.41`, `source_status=FOUND_PARTIAL`, `completeness=full`, хронология недоступна.
- [9051271323](qa/overview_9051271323_response.json): HTTP 200, 5+5 игроков, `All Draft`, `7.41`, `source_status=FOUND_FULL`, `completeness=full`.
- [9057722463](qa/overview_9057722463_response.json): независимый реальный матч, HTTP 200, 5+5 игроков, `All Draft`, `7.41`.

Пример неполного ответа из интеграционного сценария с тремя участниками (искусственная неполнота существующей фикстуры, не живой матч `8888765469`):

```json
{
  "status": "ready",
  "completeness": "partial",
  "data": {
    "data_quality": {"summary": "partial"},
    "radiant": {"players": [
      {"player_slot": 0, "hero_id": 999999, "hero_name": null, "hero_image_url": null, "display_name": null},
      {"player_slot": 1, "hero_id": 2, "hero_name": "Axe", "hero_image_url": "<URL из общего каталога>", "display_name": null}
    ]},
    "dire": {"players": [{"player_slot": 128, "hero_id": 100, "hero_name": "Tusk", "hero_image_url": "<URL из общего каталога>", "display_name": null}]},
    "patch": 999,
    "patch_name": null
  }
}
```

Этот фрагмент показывает только проверенные поля сценария, не является полным телом ответа. Интеграционный тест проверяет полный API-ответ, `limitations`, сохранение счёта и статус.

## Проверки

| Проверка | Результат |
|---|---|
| Все backend unit/integration/regression tests, включая PostgreSQL | **PASS** — 328 тестов, `pytest -q --tb=short` |
| Статический анализ типов приложения и новых тестов | **PASS** — mypy, 48 файлов |
| Линтер backend | **PASS** — Ruff |
| Контракт OpenAPI | **PASS** — snapshot обновлён; прежние пути сохранены |
| Два целевых и один независимый реальный матч через локальный API | **PASS** — HTTP 200, 5+5, корректные счета/победители и ID героев |
| Независимые сохранённые фикстуры `9051271323` и `1000000001` | **PASS** — составы и справочники |
| Частичный ответ, неизвестный герой/патч/режим, отсутствующий никнейм | **PASS** — `null`, без вымышленных игроков, `completeness=partial` |
| Отсутствие массива игроков, несуществующий ID, 429, timeout | **PASS** — действующие тесты ingestion/flow возвращают 502/404/429/503 без фиктивного отчёта |
| Players, Draft, Timeline, Ruiner | **PASS** — полная backend-регрессия и контракты |
| Frontend/UI | **NOT RUN** — UI не менялся; визуальная QA остаётся отдельной задачей |

Первый запуск полного набора в файловом sandbox дал `PermissionError` на соединении с локальной PostgreSQL; повторный запуск с разрешённым локальным подключением прошёл полностью. Единственное предупреждение — устаревающий способ `TestClient` в зависимости Starlette; на результат тестов не влияет.

## Ограничения и следующие шаги мастер-плана

`team_stats` не содержит числа башен и убийств Roshan до появления полного, проверенного по источнику журнала событий или отдельной достоверной метрики. Неизвестные ID не получают подпись. Закреплённый каталог нужно обновлять после проверки новой ревизии OpenDota; текущие названия режимов английские. `completeness=full` не означает полноту всех метрик, и клиенту следует смотреть на `data_quality` и `limitations`.

В мастер-плане OV-01/02/03/05 можно пометить **READY FOR QA**, а OV-06 оставить для ручной проверки desktop/mobile и неполных состояний. В ARCH-03/ARCH-08 стоит закрепить описанную семантику трёх уровней готовности (`status`, `source_status`, `completeness`) и правило `available_sections` как наличие отчёта. Задачи не переводились в DONE.

Изменены `backend/app/models/match_api.py`, `backend/app/services/match_analysis.py`, `backend/app/services/player_catalog.py`, `backend/tests/test_group_flow.py`, `backend/tests/fixtures/group_flow/contracts.json`; добавлены `backend/app/data/match_metadata_catalog.json`, `backend/tests/test_overview.py`, этот отчёт и три JSON-примера в `docs/qa/`. Существующий `scripts/export_match_contracts.py` использовался без изменения. Коммит не создавался.
