# Этап 2 v2 — промпт 08: Timeline Match Events

Дата: 22 октября 2026. Работа продолжена в существующем `dota-hub/`. Изучены заданный документ, фактический код, контекст/план/QA этапа 1 и миграция. `sources/` не менялись. Репозиторий по-прежнему не имеет исходного коммита: его файлы отображаются как untracked, поэтому список ниже не выдаётся за `git diff` к baseline.

**Результат:** серверный Timeline Analyzer строит упорядоченные подтверждённые события, минутные графики и отдельные возможные переломы. Данные отсутствующего источника не реконструируются. На частичном снимке клиент получает `PARTIAL`, покрытие, отсутствующие типы и текст состояния. Публикация в Telegram/Mini App не входит в №08 и не проверялась.

## A. Изменения по файлам

Созданы:

| Файл | Назначение |
| --- | --- |
| `backend/app/models/timeline.py` | Строгие DTO события, актёра, точки преимущества, возможного перелома и отчёта |
| `backend/app/services/timeline.py` | Сбор фактов, валидация, дедупликация, графики, эвристика изменения преимущества и фильтры |
| `backend/tests/test_timeline.py` | 14 сценариев хронологии, источников, ошибок и реальной фикстуры |
| `backend/tests/fixtures/timeline/9051271323.json` | Обезличенная проекция ранее полученного ответа OpenDota; разрешены только поля матча, событий и hero/slot, без account/chat |
| `docs/TIMELINE_SPEC.md` | Контракт, доказательность, формула и ограничения |
| `docs/STAGE2_08_REPORT.md` | Настоящий отчёт |

Изменены `backend/app/models/matches.py` и `backend/app/services/match_normalization.py`: сохранены per-player `kills_log`, `buyback_log`, `purchase_log`, необязательные top-level журналы и статус исходного snapshot. Старые DTO и контракты нормализации сохранены. Обновлены `README.md` и `docs/AI_PROJECT_CONTEXT.md`. Новых зависимостей, таблиц, миграций, HTTP endpoints и UI нет.

## B. Команды запуска и миграций

Внутренний вызов из каталога `backend/`:

```python
import json
from pathlib import Path
from app.services.match_normalization import normalize_match_snapshot
from app.services.timeline import analyze_timeline, filter_timeline_events

snapshot = json.loads(Path("tests/fixtures/timeline/9051271323.json").read_text())
report = analyze_timeline(normalize_match_snapshot(snapshot))
payload = report.model_dump(mode="json")
events = filter_timeline_events(report, event_type="tower")
```

Обычный локальный запуск не изменился: `cd backend && ../.venv/bin/python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000`; `cd frontend && npm run dev`. Для существующего бота: `cd backend && ../.venv/bin/python -m app.bot.main`. Вызов нового Timeline Analyzer в bot pipeline и endpoint в №08 не добавлены. Миграция не нужна; существующая схема остаётся `0001_initial`.

## C. Реально выполненные проверки

| Проверка | Результат |
| --- | --- |
| Новые тесты Timeline | **PASS — 14** |
| Полный backend pytest с локальной PostgreSQL | **PASS — 289** (275 прежних + 14 новых) |
| mypy | **PASS — 63 файла** |
| pip check | **PASS — No broken requirements found** |
| Alembic current / check | **PASS — 0001_initial (head); No new upgrade operations detected** |
| Frontend vitest / сборка TypeScript+Vite | **PASS — 11 тестов; build PASS** |
| Offline replay обезличенной проекции матча 9051271323 | **PASS — 371 событие, 33 точки золота, 33 точки опыта, 5 возможных переломов, PARTIAL** |
| Новый live OpenDota-запрос, реальная Telegram-группа и WebView | **NOT RUN** |

Первый запуск полного pytest и Alembic в ограниченной среде не получил доступ к локальному PostgreSQL (`PermissionError`); повтор с разрешённым локальным доступом прошёл. Старое предупреждение `StarletteDeprecationWarning` от TestClient остаётся. Снимок для replay — проекция старого live-ответа, не новый live-запрос.

## D. Негативные случаи

Проверены отсутствующие teamfights/кривые, пустые objectives и графики, дубли kill/teamfight, неизвестный владелец Roshan, некорректное/строковое/запредельное время, pregame `-0:29`, чужой и неизвестный actor slot, null-записи, обратный интервал драки, знаки Radiant/Dire/ноль, buyback, отсутствие ложных драк/поворотных моментов, отсутствие Roshan из MINIBOSS, стабильные ID и неизменность входа. Семантический first blood остаётся отдельным подтверждённым маркером рядом с kill-log; событие драки не создаёт дополнительных убийств.

## E. Ограничения и BLOCKED

Реальный матч возвращает `PARTIAL`, поскольку фикстура намеренно урезана и отмечена `FOUND_PARTIAL`. Командный состав `teamfights.players` не содержит надёжных slot в этом ответе, поэтому участники не выводятся по индексам. Неизвестный side остаётся null. Пороговые переломы основаны на фиксированных окнах и не доказывают причину. Если OpenDota не прислал событие или график, аналитик не может восстановить их из результата матча. Фильтры готовы как Python-функция; HTTP/Mini App интеграция — отдельная следующая работа. Постоянного хранения `TimelineReport` нет. Внешних блокировок после повторных локальных проверок нет.

## F. Критерии приёмки

- **PASS:** подтверждённые события отсортированы и содержат время/источник/доказательство; повторы журналов и интервалов удаляются.
- **PASS:** частичный ответ не создаёт отсутствующие события; выдаёт `PARTIAL`, missing types, coverage и ограничения.
- **PASS:** отдельные возможные переломы содержат дельты, направление, confidence и nearby IDs без причинного утверждения.
- **PASS:** DTO/фильтры, реалистичная фикстура, отрицательные сценарии и полный регресс.

## G. Следующий промпт

№08 готов как внутренний серверный модуль для интеграции в будущие API/бот/UI. Перед показом пользователям потребуется отдельная задача на формат ответа и интерфейс; текущий бот не вызывает Timeline Analyzer. Новые функции следующих этапов в этом промпте не начинались.
