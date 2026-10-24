**RI-02-CAL-01-DATA / READY FOR QA.** Дата: 24.10.2026. HEAD `f222ee9dc322e98b8890ec642c9038244fe1e5a2`. Исследуется рабочее дерево с уже существующими незакоммиченными RI/PL/UI изменениями, а не чистый HEAD. Код, настройки, сохранённые матчи и прежние отчёты не изменены.

## Фактическая выдача

Локальный сервер `127.0.0.1:8000`: выполнены20 GET (две схемы маршрутов × два матча × пять разделов), без POST. Local-alpha10/10 HTTP200, защищённые10/10 без токена HTTP401 AUTH_REQUIRED. Авторизованный live HTTP200 **BLOCKED**: действующая пользовательская Telegram-сессия для аудита не предоставлена. Обход auth и выдача токена от имени пользователя не выполнялись. Авторизованный путь, JWT/пользователь и паритет с local-alpha подтверждены существующими тестами в отдельной `dota_hub_test` с тестовыми credential; это не Telegram WebView и не live login.

Оба маршрута вызывают один stored(), но условия доступа различаются. Authenticated требует сессию существующего TelegramUser; история запроса/членство в чате для GET конкретного матча не проверяется (публичная ссылка доступна другому аутентифицированному пользователю, это существующая политика, проверенная test_forwarded_match_link_is_public_to_other_authenticated_user). Local-alpha зарегистрирован только при local_alpha, требует loopback host/client и разрешённый Origin. Тело результата не содержит account_id/Steam ID/raw payload.

| Матч | Раздел | Local HTTP | status | completeness / quality | DB→API отличия | Read projection→API |
|---|---|---|---|---|---|---|
| 9051271323 | overview | 200 | ready | full / None | нет | нет |
| 9051271323 | players | 200 | ready | full / None | нет | нет |
| 9051271323 | draft | 200 | ready | partial / None | нет | нет |
| 9051271323 | ruiner | 200 | ready | partial / partial | нет | нет |
| 9051271323 | timeline | 200 | ready | full / complete | нет | нет |
| 9057722463 | overview | 200 | ready | full / None | нет | нет |
| 9057722463 | players | 200 | ready | full / None | нет | нет |
| 9057722463 | draft | 200 | ready | partial / None | нет | нет |
| 9057722463 | ruiner | 200 | ready | partial / partial | [".teams.dire.preliminary_selection", ".teams.radiant.preliminary_selection"] | нет |
| 9057722463 | timeline | 200 | ready | missing / unavailable | нет | нет |

Во всех десяти ответах data соответствует сохранённому DTO после разрешённой read-time проекции. Для9057722463 legacy preliminary отсутствует в JSONB, появляется только в HTTP; БД не меняется. Для9051271323 даже старые reason_codes возвращаются как сохранены. Replay меняет два поля Oracle: diagnostic counter_ratio появляется, общий код отказа заменяется точным. Индексы всех20 совпадают. `model_version=ruiner_v1`, config_digest и source_digest при этом одинаковы. Flow config digest тоже равен текущему; при неизменном snapshot `_process` может вернуть старый report из кэша даже после явного analyze. Это доказанный пробел инвалидации при смене реализации, не отказ OpenDota и не потеря JSON поля на GET.

## Envelope: ожидаемое = фактическое наличие

| Поле | JSON type | 9051271323 | 9057722463 | Проверка / смысл |
|---|---|---|---|---|
| schema_version | int | 1 | 1 | present; DTO JSON validate PASS; no null->0 |
| match_id | str | 9051271323 | 9057722463 | present; DTO JSON validate PASS; no null->0 |
| status | str | ready | ready | present; DTO JSON validate PASS; no null->0 |
| available_sections | list | ["overview", "players", "draft", "ruiner", "timeline"] | ["overview", "players", "draft", "ruiner", "timeline"] | present; DTO JSON validate PASS; no null->0 |
| data | dict | {RuinerReport} | {RuinerReport} | present; DTO JSON validate PASS; no null->0 |
| error | NoneType | null | null | present; DTO JSON validate PASS; no null->0 |
| limitations | list | ["Индекс 0–100 отражает относительные признаки проблемного исполнения, не вероятность виновности и не причинность.", "Результат матча и оценки драфта не используются. Radiant и Dire анализируются независимо.", "Веса, пороги и ролевые группы — гипотезы ruiner_v1; малые группы и различия героев ограничивают выводы."] | ["Индекс 0–100 отражает относительные признаки проблемного исполнения, не вероятность виновности и не причинность.", "Результат матча и оценки драфта не используются. Radiant и Dire анализируются независимо.", "Веса, пороги и ролевые группы — гипотезы ruiner_v1; малые группы и различия героев ограничивают выводы."] | present; DTO JSON validate PASS; no null->0 |
| model_version | str | ruiner_v1 | ruiner_v1 | present; DTO JSON validate PASS; no null->0 |
| config_version | str | 31147c647698fe40a5109d8520227d2e62f5d203aa5299a5585e3c1f5c6779a8 | 31147c647698fe40a5109d8520227d2e62f5d203aa5299a5585e3c1f5c6779a8 | present; DTO JSON validate PASS; no null->0 |
| analyzed_at | str | 2026-10-24T00:16:38.809814Z | 2026-10-23T13:37:46.742588Z | present; DTO JSON validate PASS; no null->0 |
| completeness | str | partial | partial | present; DTO JSON validate PASS; no null->0 |
| retry_after_seconds | NoneType | null | null | present; DTO JSON validate PASS; no null->0 |

`analyzed_at` — время сохранения, не GET/replay; `status=ready` — отчёт доступен, не обещание десяти оценок. `completeness=partial` и `data.quality=partial` согласованы. `retry_after_seconds=null` и Retry-After отсутствует при200. Cache-Control no-store присутствует на всех20 запросах.

## RuinerReport / team / player

### data

| Ожидаемое поле DTO | Фактический type | Значение / краткое представление | Сохранённый report |
|---|---|---|---|
| match_id | str | 9051271323 | совпадает; legacy projection см. выше |
| model_version | str | ruiner_v1 | совпадает; legacy projection см. выше |
| config_digest | str | 31147c647698fe40a5109d8520227d2e62f5d203aa5299a5585e3c1f5c6779a8 | совпадает; legacy projection см. выше |
| quality | str | partial | совпадает; legacy projection см. выше |
| teams | dict | 2 records; полный JSON в live_ruiner_responses.json | совпадает; legacy projection см. выше |
| players | list | 10 records; полный JSON в live_ruiner_responses.json | совпадает; legacy projection см. выше |
| summary | dict | {"selected_player_slot": null, "selected_team": null, "selection_status": "no_confident_selection", "evidence": ["team_context_not_provided"]} | совпадает; legacy projection см. выше |
| limitations | list | ["Индекс 0–100 отражает относительные признаки проблемного исполнения, не вероятность виновности и не причинность.", "Результат матча и оценки драфта не используются. Radiant и Dire анализируются независимо.", "Веса, пороги и ролевые группы — гипотезы ruiner_v1; малые группы и различия героев ограничивают выводы."] | совпадает; legacy projection см. выше |
### data.teams.radiant

| Ожидаемое поле DTO | Фактический type | Значение / краткое представление | Сохранённый report |
|---|---|---|---|
| team | str | radiant | совпадает; legacy projection см. выше |
| player_slots | list | [0, 1, 2, 3, 4] | совпадает; legacy projection см. выше |
| scored_players | int | 3 | совпадает; legacy projection см. выше |
| selection | dict | {"selected_player_slot": null, "selected_team": null, "selection_status": "no_confident_selection", "evidence": ["incomplete_or_low_confidence_team"]} | совпадает; legacy projection см. выше |
| threshold | int | 70 | совпадает; legacy projection см. выше |
| minimum_margin | int | 15 | совпадает; legacy projection см. выше |
| preliminary_selection | dict | {"projection_version": "ri_preliminary_v1", "minimum_margin": 15, "status": "none", "player_slots": [], "leader_slot": null, "highest_index": null, "margin": null, "confidence": "low", "reason_codes": ["incomplete_player_scores", "roles_unconfirmed", "leaver_context_unknown"]} | совпадает; legacy projection см. выше |
### data.players[slot=0]

| Ожидаемое поле DTO | Фактический type | Значение / краткое представление | Сохранённый report |
|---|---|---|---|
| player_slot | int | 0 | совпадает; legacy projection см. выше |
| team_player_number | int | 1 | совпадает; legacy projection см. выше |
| hero_id | int | 123 | совпадает; legacy projection см. выше |
| team | str | radiant | совпадает; legacy projection см. выше |
| position | dict | {"position": 4, "evidence": "estimated", "source_field": "position_est"} | совпадает; legacy projection см. выше |
| role_group | str | support | совпадает; legacy projection см. выше |
| error_index | NoneType | null | совпадает; legacy projection см. выше |
| confidence | str | low | совпадает; legacy projection см. выше |
| evidence_coverage | float | 0.5 | совпадает; legacy projection см. выше |
| axes | dict | {"survival": 0.4999999999999999, "participation": null} | совпадает; legacy projection см. выше |
| observed_metrics | dict | {"gpm": 211.0, "kda": 0.6666666666666666, "xpm": 329.0, "obs_placed": 3.0, "sen_placed": 5.0, "sentry_kills": 0.0, "deaths_per_min": 0.3724780134505949, "observer_kills": 1.0, "healing_per_min": 3.8799793067770305, "kill_participation": 0.8, "hero_damage_per_min": 244.4386963269529, "tower_damage_per_min": 7.108122090015519} | совпадает; legacy projection см. выше |
| positive_credit | float | 3.9942 | совпадает; legacy projection см. выше |
| positive_signals | list | [{"code": "positive:hero_damage_per_min", "text": "Урон героям в минуту: положительный вклад относительно сравниваемых союзников.", "metric": "hero_damage_per_min", "value": 244.4387, "reference": 193.0367, "comparison_slots": [1], "magnitude": 0.266281, "source_ref": "normalized_match"}, {"code": "observed_contribution:tower_damage_per_min", "text": "Урон строениям в минуту: вклад наблюдается, но ненулевого ориентира для численного сравнения нет.", "metric": "tower_damage_per_min", "value": 7.1081, "reference": 0.0, "comparison_slots": [1], "magnitude": 0.0, "source_ref": "normalized_match"}] | совпадает; legacy projection см. выше |
| negative_signals | list | [{"code": "relative_high:deaths_per_min", "text": "Смертность в минуту: отклонение от медианы сравниваемых союзников; это сигнал, а не доказательство ошибки.", "metric": "deaths_per_min", "value": 0.3725, "reference": 0.2483, "comparison_slots": [1], "magnitude": 0.5, "source_ref": "normalized_match"}] | совпадает; legacy projection см. выше |
| missing_metrics | list | [] | совпадает; legacy projection см. выше |
| reason_codes | list | ["position_estimated", "economy_not_penalized", "kda_descriptive_only", "comparison_unavailable:kill_participation", "zero_comparison_reference:tower_damage_per_min", "insufficient_data", "positive:hero_damage_per_min", "observed_contribution:tower_damage_per_min", "relative_high:deaths_per_min"] | совпадает; legacy projection см. выше |
| limitations | list | ["Позиция 1–5 не подтверждена; уверенность низкая. Линия и имя героя не доказывают роль.", "Сравнение внутри команды и ролевой группы; проверенной популяционной нормы нет. KDA не дублирует штрафы за смерти и участие."] | совпадает; legacy projection см. выше |

Все scalar/axes/observed/signals/null каждого из20 участников можно сопоставить с `live_ruiner_responses.json` и MATCH_TRACE. Player DTO содержит slot/team/team_number/hero_id/position/role_group/index/confidence/coverage/axes/observed/credit/signals/missing/reasons/limitations. duration, team_score, leaver_status, source_fetched_at, raw-vs-usable отдельный статус не являются обязательными полями текущего /ruiner. Их отсутствие классифицируется как API_DIAGNOSTIC_GAP, а не потеря обязательного API поля. Runtime response model authenticated типизирован MatchEnvelope[RuinerReport], local generic route в OpenAPI не описывает все section DTO — документационный долг, фактическая сериализация общая.

## Повреждённые и устаревшие данные: изолированные эксперименты

Это копии сохранённого report и fake read-only session, не запросы к изменённой рабочей БД. Baseline200 проверен перед мутациями. Эмуляция возвращает datetime, как SQLAlchemy, и проходит тот же stored()/DTO serializer.

| Вариант | HTTP | Факт | Вердикт |
|---|---|---|---|
| stored_baseline | 200 | ["highest_relative_index", "roles_unconfirmed", "leaver_context_unknown"] | PASS |
| stored_stale_raw | 200 | ["highest_relative_index", "roles_unconfirmed", "leaver_context_unknown"] | исторический report принят; свежесть отдельно не проверена |
| stored_model_mismatch | 200 | envelope=different_model, data=ruiner_v1 | FAIL: противоречивый metadata принят |
| stored_config_mismatch | 200 | ["highest_relative_index", "roles_unconfirmed", "leaver_context_unknown"] | FAIL: противоречивый metadata принят |
| stored_schema_mismatch | 200 | ["highest_relative_index", "roles_unconfirmed", "leaver_context_unknown"] | FAIL: противоречивый metadata принят |
| stored_source_digest_mismatch | 503 | REPORT_UNAVAILABLE | PASS: source mismatch отвергнут |
| stored_corrupt_preliminary | 200 | ["stored_projection_inconsistent", "roles_unconfirmed", "leaver_context_unknown"] | PASS: conservative repair/legacy |
| stored_legacy_preliminary | 200 | ["highest_relative_index", "roles_unconfirmed", "leaver_context_unknown"] | PASS: conservative repair/legacy |

GET валидирует структуру DTO и совпадение section.source_digest с flow.source_digest; не валидирует wrapper schema/model/config против data и raw Match. При противоречивой, но структурно допустимой preliminary выдаётся none/stored_projection_inconsistent. При структурной порче DTO возвращается503 REPORT_UNAVAILABLE (проверено существующими тестами). Оси/индексы не пересчитываются, сохранённые строки не меняются.

## Прочие разделы

Overview и Players обоих пилотов full по своей области core stats; это не означает availability ward/parsed/roles для каждого поля. Timeline первого complete, второго missing/unavailable; ограничения второго отражают отсутствие событий. Draft обоих partial. Basic fields не скрываются из-за слабого Draft/Timeline. Все пять data DTO совпадают с JSONB, кроме описанного legacy preliminary. Найдена отдельная семантическая проблема Timeline team attribution для уничтоженной своей башни — см. F10; она не участвует в RI.

[Воспроизводимые свидетельства](qa/ri02/data01/) · [Матрица](RI_02_DATA_01_FIELD_MATRIX.csv) · [QA](RI_02_DATA_01_QA_REPORT.md)
