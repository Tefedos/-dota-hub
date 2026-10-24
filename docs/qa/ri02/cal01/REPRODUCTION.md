# RI-02-CAL-01 — воспроизведение

Рабочий каталог — корень `dota-hub/`. Требуются существующая `.venv` проекта и текущие исходники Python. Версию исходников проверять по `model_freeze.json`: HEAD недостаточен из-за незакоммиченных RI-04/RI-02-FIX-01. Точные `git status --short` на старте и после исследования: `git_status_at_start.txt` и `git_status_after.txt`.

```sh
.venv/bin/python scripts/ri02_cal01.py analyze
shasum -a 256 docs/qa/ri02/cal01/raw/*.json
git status --short
git diff --check
```

Скрипт `analyze` не обращается к сети или БД, читает замороженные `raw/*.json`, пересчитывает все 12 отчётов дважды, отдельно проверяет формулу каждого из 120 индексов/`null` и совпадение 20 индексов пилотов с сохранёнными. Исследовательские таблицы и отчёты перезаписываются детерминированно, исходные копии не меняются. Для хранения копий `raw/` внесён в локальный `.gitignore`; **не публиковать** эти JSON автоматически. Реестр содержит SHA-256 и путь к локальной копии. Если копии потеряны, точное воспроизведение невозможно только по текущему OpenDota, который может обновить/распарсить ответ; новая загрузка считается новой версией датасета.

Первоначальный сбор: две страницы `GET https://api.opendota.com/api/publicMatches` (вторая с `less_than_match_id=9058841291`), без перемешивания/seed; первые десять кандидатов с mode 1/2/22, duration≥900 и boolean winner. Полный список 200 и порядок сохранены в `candidate_discovery.json`. Затем 10 GET `/matches/{id}`, пауза 1 с, максимум 40; HTTP 429 — ограниченный Retry-After, POST `/request` отсутствует. Команда `collect` отказывается повторять сбор при уже существующем `fetch_journal.json`. `pilots` читает локальную PostgreSQL в read-only транзакции и не перезаписывает уже скопированные raw-файлы:

```sh
.venv/bin/python scripts/ri02_cal01.py collect
.venv/bin/python scripts/ri02_cal01.py pilots
.venv/bin/python scripts/ri02_cal01.py analyze
```

Файлы: `candidate_discovery.json` — 200 кандидатов и метод; `fetch_journal.json` — 10 проверок; `pilot_sources.json` — metadata сохранённых пилотов; `match_registry.json` — все 202 записи, статусы, 12 checksum; `player_dataset.json` — 120 игроков и сырые числовые статистики без персональных ID; `ruiner_reports.json` — 12 полных RI-ответов; `coverage.json` — агрегаты; `score_breakdown.json` — 20 подробных случаев с peers, медианами, осями, весами, credit и повторным расчётом; `blind_review_cards.json` — 20 карточек без индексов; `benchmark_samples.json` — два OpenDota hero/role примера; `competitor_manual_registry.json` — 12 ссылок; `model_freeze.json` — конфигурация и SHA исходников. `COVERAGE_REPORT.md`, `SCORE_BREAKDOWN.md`, `BENCHMARK_RESEARCH.md`, `COMPETITOR_COMPARISON.md`, `RESEARCH_CONCLUSIONS.md` дают интерпретацию и пределы.

В raw-копиях `parse_match_response()` убирает основные персональные поля и чат, но они всё равно остаются локальными исходными данными; Git их игнорирует. SHA-256 в реестре относится **к этой санитизированной копии, используемой анализатором**, а не к байтам первоначального HTTP-ответа OpenDota. Она содержит все входы текущего RI, но не позволяет восстановить удалённые поля. Участники с `null` остаются в датасете. Пилот `9057722463` имеет сохранённый raw `FOUND_PARTIAL`, model `ruiner_v1`, digest совпадает с текущим и индексы `[50,0,0,0,42]` / `[0,0,0,31,6]`; это реальный snapshot, а не старая синтетическая fixture. Для разных патчей и подтверждённых ролей потребуется отдельная выборка. Независимый игровой эксперт не участвовал.
