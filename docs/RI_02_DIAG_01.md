# RI-02-DIAG-01 — отсутствующие оценки Hoodwink и Oracle

Дата: 2026-10-23. Вердикт: **MIXED CAUSES**. Диагностика завершена; исправление не выполнялось.

## A. Репозиторий и источник

- HEAD: `f222ee9dc322e98b8890ec642c9038244fe1e5a2` (`Initial Dota Hub alpha implementation`). Модель `ruiner_v1`; просмотрен фактический рабочий код, включая уже имевшиеся незакоммиченные RI-04 изменения. `git blame` для `observed()` указывает на HEAD; мотив проверки `K+A <= score` в коде или комментарии не документирован.
- До аудита `git status --short` показывал modified: `backend/app/api/v1/matches.py`, `backend/app/models/performance.py`, `backend/app/services/performance.py`, `backend/tests/fixtures/group_flow/contracts.json`, `frontend/src/features/matches/SectionContent.tsx`, `frontend/src/features/matches/contract.test.tsx`, `frontend/src/pages/MatchReportPage.tsx`; untracked: `backend/app/services/performance_preliminary.py`, `backend/tests/fixtures/performance/`, три `backend/tests/test_performance_preliminary*.py`, `docs/RI_01_AUDIT_REPORT.md`, два `docs/RI_04*.md`, `docs/qa/ri04/`, четыре файла `frontend/src/features/matches/RuinerSection*` и `frontend/src/features/matches/ruiner.ts`. В рамках RI-02 добавлен только этот отчёт; прежние изменения не трогали.
- Основной источник: **сохранённый** `matches.raw_payload` локальной PostgreSQL, `fetch_status=ready`, `fetched_at=2026-10-23 19:19:54.411929+00:00`, `source=opendota`, `source_fetched_at=2026-10-23T19:19:54.394003+00:00`, `status=FOUND_FULL`, `schema_version=1`. Матч 9051271323: duration 1933 с, Radiant 10, Dire 45, game_mode 22. Сумма `kills` пяти игроков Radiant равна 10. `FOUND_FULL` подтверждает наличие основных полей ответа, а не согласованность всех счётчиков каждого игрока.
- Сохранённый REST-ответ `GET /api/v1/local-alpha/matches/9051271323/ruiner`: `status=ready`, `model_version=ruiner_v1`, `completeness=partial`; он сверён с вычислением из сохранённого снимка. Старую частичную фикстуру `backend/tests/fixtures/draft/9051271323/evidence.json` за live-источник не принимали. Нового запроса в OpenDota не было.

## B. Фактическая статистика и преобразования

В таблице `—` означает, что поле не передаётся на данном этапе, а `null` — фактическое отсутствие значения. `Normalized` для KP — `PlayerDerivedStats`, `Observed` — вход оценщика. У обоих `performance_position.evidence=estimated` из `position_est`; подтверждённый `lane_role` описывает линию, а не позицию 1–5.

| Поле | Raw | Normalized | Observed | Комментарий |
|---|---|---|---|---|
| Hoodwink: slot, hero | `0`, `123` | `0`, `123` | `0`, `123` | Идентичность сохранена. |
| Oracle: slot, hero | `1`, `111` | `1`, `111` | `1`, `111` | Идентичность сохранена. |
| Hoodwink: K/D/A | `1/12/7` | `1/12/7` | Используются без потерь | Неотрицательные целые. |
| Oracle: K/D/A | `1/8/11` | `1/8/11` | Используются без потерь | Неотрицательные целые. |
| Оба: duration, Radiant score | `1933`, `10` | `1933`, `10` | `1933`, `10` | Пороги 900 с и 10 убийств соблюдены. |
| Hoodwink: position_est, lane_role | `4`, `3` | 4 estimated, off lane confirmed | support, low role evidence | Линия не подтверждает farm position. |
| Oracle: position_est, lane_role | `5`, `1` | 5 estimated, safe lane confirmed | support, low role evidence | Линия не подтверждает farm position. |
| Hoodwink: deaths/min | `12`, duration `1933` | `12` | `12×60/1933 = 0.372478` | Survival доступна. |
| Oracle: deaths/min | `8`, duration `1933` | `8` | `8×60/1933 = 0.248319` | Survival доступна. |
| Hoodwink: `(K+A)/score` | `8/10` | `0.8 available` | `0.8` | Значение не потеряно. |
| Oracle: `(K+A)/score` | `12/10` | **`1.2 available`** | **`null`** | Первое расхождение — в `observed()`. |
| Hoodwink / Oracle: `teamfight_participation` | `0.8 / 1.2` | Не моделируется | Не используется | Отдельное raw-поле; совпадение с арифметикой в этом матче не доказывает общую семантику. |
| Hoodwink: GPM/XPM, hero/tower damage, healing | `211/329`, `7875/229/125` | Сохранены | `211/329`, `244.439/7.108/3.880` в минуту | Экономика support не штрафуется; damage/healing могут дать положительный кредит. |
| Oracle: GPM/XPM, hero/tower damage, healing | `221/265`, `6219/0/9501` | Сохранены | `221/265`, `193.037/0/294.909` в минуту | То же правило. |
| Hoodwink: wards placed/kills (observer/sentry) | `3/5`, `1/0` | Сохранены | То же | Положительные признаки, не самостоятельная ось. |
| Oracle: wards placed/kills (observer/sentry) | `9/22`, `2/5` | Сохранены | То же | Положительные признаки, не самостоятельная ось. |

Путь данных и проверки:

| Этап | Вход → выход | Проверка и причина `null` |
|---|---|---|
| OpenDota fetch: `backend/app/integrations/opendota.py:166-174` | HTTP `/matches/9051271323` → JSON | При сохранённом снимке сетевой fetch повторно не запускался. |
| `parse_match_response()`: `backend/app/integrations/opendota.py:78-115` | JSON → snapshot `FOUND_FULL` | Проверяет ID, длительность, типы основных полей, roster и наличие полей. Не проверяет `K+A <= team_score`. |
| `MatchIngestion._save_result/_read_cache`: `backend/app/services/match_ingestion.py:33-53,90-104` | snapshot → `matches.raw_payload` → тот же snapshot | Присутствует raw, статус ready. Нового fetch или записи при диагностике не было. |
| `normalize_match_snapshot`, `_player`, `_derived`: `backend/app/services/match_normalization.py:110-145,314-338,348-...` | K/D/A, score → `PlayerStat`, derived KP `0.8/1.2` | `_int` сохраняет неотрицательные счётчики; `_metric` отказывает только при отсутствии числителя/знаменателя либо знаменателе 0. Oracle **не** становится `null` здесь. |
| `observed()`: `backend/app/services/performance.py:31-48` | `PlayerStat` → observed KP `0.8/null` | Условие `involvement <= total` отвергает `12 > 10` только для Oracle. KDA остаётся 1.5. |
| `RoleAwarePerformanceEvaluator.evaluate/compare`: `backend/app/services/performance.py:72-204` | observed → survival `0.5/0`, participation `null/null`, coverage `0.5/0.5`, индекс `null/null` | Нет Oracle KP; peer-group состоит лишь из двух саппортов. Нет достаточного peer для Hoodwink; у Oracle нет собственного значения. Требуются 2 оси и coverage ≥0.7. |
| `analyze_performance` и сохранение: `backend/app/services/performance.py:223-226`, `backend/app/services/match_analysis.py:201-216,240-259` | report → `match_analyses` | Данные и `null` сохраняются без подстановок. |
| REST: `backend/app/api/v1/matches.py:95-109` | persisted report → `RuinerReport` → JSON | Endpoint валидирует и возвращает отчёт; не пересчитывает KP. RI-04 `project_preliminary` добавляет/проецирует предварительный выбор, не меняя индекс. |

## C. Трассировка четырёх `null`

1. Oracle observed KP: `1+11=12 > 10`; `observed()` в `backend/app/services/performance.py:36-41` возвращает `None`. Отчёт добавляет `team_kills_missing_small_or_inconsistent` и `missing_metrics=['kill_participation']` (`:121-122,201-202`). При этом normalized derived KP=`1.2 available`; проверка в двух слоях различается.
2. Hoodwink participation: собственный KP=`0.8`, но peer-группа Radiant/support состоит из слотов `0,1`, у Oracle KP=`null`. `compare()` (`backend/app/services/performance.py:97-99,130-136`) требует `self + >=1` сравнимого игрока (`minimum_cohort=2`); результат `null` с `comparison_unavailable:kill_participation`.
3. Oracle participation: собственного KP нет, поэтому `compare()` возвращает `null` независимо от Hoodwink.
4. У обоих остаётся survival: `deaths_per_min` 0.372478 против 0.248319; команда имеет 45 смертей, что больше порога 5. Hoodwink: `(0.372478-0.248319)/0.248319=0.5`; Oracle: 0. Доступна ровно одна из двух весовых осей. `coverage=0.5`, `minimum_axes=2`, `minimum_coverage=0.7`; оба индекса `null`, `insufficient_data` (`backend/app/services/performance.py:170-194`). Положительный кредит Hoodwink `3.9942`, Oracle `15.0` не заменяет ось. Уверенность `low`; estimated position дополнительно не позволяет `medium`, но **не** является причиной отсутствия участия или индекса.

## D. Проверка гипотезы и семантики

| Вопрос | Ответ | Доказательство / уверенность |
|---|---|---|
| `K+A > team_score` — дефект? | **Подтверждён дефект согласованности контрактов и чрезмерно категоричное правило для произвольных raw-счётчиков.** Но не доказано, что 1.2 означает «участие в 120% уникальных командных убийств»; автоматическое принятие 1.2 за процент было бы другим дефектом. | Нормализатор считает 1.2 доступным, evaluator отбрасывает, OpenDota snapshot содержит 1.2 и в отдельном поле. Высокая уверенность в техническом несоответствии, средняя в игровой интерпретации. |
| Почему Oracle без participation? | Собственный KP отброшен из-за единственного условия `12>10`. | Код и replay, высокая. |
| Почему Hoodwink без participation? | Единственный сравнимый support peer не имеет KP. | Код и replay, высокая. |
| Estimated position — дополнительная причина `null`? | Нет: позиции 4 и 5 формируют support cohort. Это отдельная причина `confidence=low` и блокировки строгого выбора. | Код и replay, высокая. |
| Какие матчи затрагиваются? | Режимы 1/2/22 с достаточными duration и team score, где у участника `K+A>team_score`, особенно ролевые группы с двумя игроками. Из-за peer-зависимости могут потерять ось и другие члены группы. Если team score <10, участие и так выключено. | Следует из условий кода, высокая для классов входов; частота в популяции не измерялась. |

**Игровая граница.** Несколько игроков, помогающих при одном убийстве, объясняют, почему **сумма ассистов команды** может превосходить число командных убийств. Сама по себе эта посылка не доказывает, что **один игрок** получает более одного `(kill или assist)` за одно зачтённое команде убийство. Факт снимка Oracle (`assists=11`, `team_score=10`) и отдельное `teamfight_participation=1.2` показывают, что такое сочетание raw-полей встречается. [Парсер OpenDota](https://github.com/odota/parser/blob/master/src/main/java/opendota/Parse.java#L3410-L3425) читает `m_flTeamFightParticipation`, `m_iKills`, `m_iAssists` как отдельные игровые поля; [схема OpenDota](https://github.com/odota/core/blob/master/sql/create_tables.sql) хранит их отдельно от командного счёта. Есть и [сообщение пользователя в трекере Valve о 41 assists при 37 командных убийствах](https://github.com/ValveSoftware/Dota2-Gameplay/issues/7060), но оно не является официальным объяснением правила. Ни сохранённый снимок, ни доступный `kills_log` не содержат полного event-level журнала ассистов Oracle. Поэтому нельзя подтвердить причину превышения: особые правила начисления, расхождение счётчиков или ошибка источника. Семантика «доля уникальных командных убийств» требует событийной проверки; простое `(K+A)/score` здесь лишь **отношение счётчиков**, способное превышать 1.

Порог `K+A <= team_score` в `observed()` не имеет комментария или документированного игрового обоснования. Он отсекает и малое превышение `11/10`, и явный выброс `10000/10`, не разделяя их причины. Тест на `10000 assists` подтверждает защиту от крайних аномалий, но не валидность границы 100% для реальных данных. Расчёт `kill_participation` при отсутствии `kills` или `assists` возвращает `null`; при score=0 или score<10 evaluator тоже возвращает `null` без деления. При равенстве и меньшем значении вычисляется отношение. Нормализатор при score=0 возвращает статус `denominator_zero`; при score 1–9 он может показать derived число, которое оценщик не применит.

## E. Настройки, эксперименты и существующие тесты

`PerformanceConfig` (`backend/app/services/performance_config.py:5-38`): `minimum_cohort=2` **включая самого игрока**, `minimum_axes=2`, `minimum_coverage=0.7`, `fallback_weights={'survival':0.5,'participation':0.5}` для support **и unknown**, `minimum_team_kills=10`, `minimum_team_deaths=5`, `minimum_duration_seconds=900`, supported modes `(1,2,22)`, `maximum_positive_credit=15`. У поддержки много описательных и положительных признаков, но ровно две штрафные оси. При одной оси `null` математически и по действующему контракту корректен. Достаточность такого контракта — отдельное продуктовое решение; снижать пороги лишь ради числа нельзя.

Ниже replay из сохранённого снимка; во всех вариантах, кроме «реальный», **менялись только значения в памяти**. Числа вариантов не являются оценками настоящего матча.

| ID | Сценарий / ожидание | Факт: Hoodwink; Oracle | Статус |
|---|---|---|---|
| R1 | Реальный снимок: два `null` | KP `0.8/null`, participation `null/null`, coverage `0.5/0.5`, index `null/null` | PASS |
| R2 | Oracle K+A=score (assists 9): сравнение появляется | KP `0.8/1.0`, participation `0.2/0`, coverage `1/1`, index `31/0`, confidence оба low | PASS |
| R3 | Oracle K+A<score (assists 7): сравнение появляется | KP `0.8/0.8`, participation `0/0`, coverage `1/1`, index `21/0` | PASS |
| R4 | Oracle K+A>score (assists 10): старый отказ | KP `0.8/null`, participation `null/null`, index `null/null` | PASS |
| R5 | Один support с KP: второй теряет peer | Случай R1; Hoodwink при собственном 0.8 всё равно без оси | PASS |
| R6 | Одна/две оси | R1: 1 ось и coverage 0.5 → null; R2: 2 оси и coverage 1 → число | PASS |
| R7 | Team score=0: безопасное деление | KP `null/null`, participation `null/null`, index `null/null`; исключения нет | PASS |
| R8 | Team score=9: минимум 10 | KP `null/null`, participation `null/null`, index `null/null` | PASS |
| R9 | Estimated positions | Обе отнесены к support; confidence low. Смена положения на confirmed не проверялась отдельно, потому что путь роли ясен из кода и R1. | PASS |
| R10 | Оба support имеют participation | R2/R3; требуется лишь второй доступный игрок, не проверенная статистическая норма | PASS |
| R11 | K/A отсутствует | Код проверен; отдельный replay с удалением поля не запускался | NOT RUN |
| R12 | Событийное подтверждение Oracle 11 assists | Полного журнала ассистов нет | BLOCKED |

Запущены существующие `tests/test_performance.py`, `tests/test_performance_preliminary.py`, `tests/test_performance_preliminary_qa.py`: **85 passed, 2 xfailed**, одна deprecation warning зависимости Starlette/httpx. В них есть сценарии малого/нулевого team score, экстремальных `10000 assists`, estimated roles, ролевого сравнения и предварительного выбора. Реалистичного пограничного `11/10`, симметричной потери оси второго саппорта и контрактной согласованности normalized/observed тесты не содержат. Новые тесты в репозиторий не добавлялись.

## F. Первопричина и последствия возможного исправления

- **Технический дефект:** normalized KP=`1.2 available`, а `observed()` без документированной семантической политики превращает его в `null`; reason code смешивает отсутствие, малый счёт и «несогласованность». Малое превышение Oracle лишает также Hoodwink второго значения для peer-сравнения.
- **Корректное ограничение текущей модели:** 1 доступная штрафная ось <2, coverage 0.5<0.7; следовательно index=`null`. `positive_credit` не считается независимой отрицательной осью.
- **Неясность источника/игровой модели:** значение 1.2 действительно сохранено, но нет достаточного event-level evidence для трактовки как доли уникальных убийств или утверждения, что начисление ассистов корректно. Дополнительная слабость — ролевое сравнение всего двух саппортов и estimated positions, даже если оба KP доступны.
- **Непройденное:** реальное происхождение Oracle 11 assists и распространённость такого сочетания по матчам. Новый OpenDota запрос не выполнялся.

Если изменить только правило KP, последствия нельзя вычислить как факт без выбранной семантики. Диагностический R2 показывает, что при **искусственно изменённом** Oracle на `K+A=10` оба саппорта получают вторую ось и числа; при R1 оба `null`. При сохранении raw `12/10` и допуске отношения >1 значения comparison и index будут иными, нежели R2; обещать конкретный индекс нельзя. `positive_credit` и положительные сигналы по damage/healing/wards останутся исходными при неизменных raw-полях, но сигнал по самому KP может появиться. `negative_signals` по participation могут измениться. `evidence_coverage` у саппортов потенциально возрастёт до 1; `confidence` всё равно low из-за estimated positions. Другие Radiant core не используют саппортов как peers и при локальной правке KP Oracle сохранят прежние оси/индексы; Dire обрабатывается независимо и не изменится. Radiant `preliminary_selection` сейчас `none/incomplete_player_scores` и **может** стать group/single с другим лидером; R2 даёт single Hoodwink 31, но это только синтетический ввод. Строгий `selection` останется `no_confident_selection` при estimated позициях и low confidence. Нужно перепроверить весь отчёт при любом фактическом исправлении, потому что иной выбор метрики может затронуть больше игроков и команд.

## G. Варианты решения без реализации

| Вариант | Файлы / версия | Польза | Риск и необходимые проверки |
|---|---|---|---|
| **Рекомендуемый минимальный следующий шаг:** явно определить семантику KP как отношение игровых счётчиков, а не процент уникальных убийств; затем согласовать normalized и observed обработку умеренного `K+A>score`, сохранив отдельные проверки отсутствия, малого team score и аномальных/несогласованных данных. | `backend/app/services/performance.py`, `backend/app/services/match_normalization.py` (контракт derived), соответствующие DTO/документация и тесты. Изменение вычисления требует новой версии модели и повторного анализа сохранённых отчётов по принятой процедуре. | Устраняет немотивированную потерю значения, сохраняет возможность сравнения. | Нужно доказать по источнику, какие превышения валидны; нельзя бесконтрольно принимать выбросы. Проверить 10/10, 11/10, 12/10, 10000/10, missing/0/<10, peers, обе команды, selection и отсутствие регрессий. |
| Считать только долю **уникальных** командных убийств по event-level подтверждению | Инжест/нормализация событий, `performance.py`, DTO, тесты; новая версия модели обязательна. | Соответствует понятию процента 0–100%. | В сохранённом снимке нет журнала ассистов; многие матчи останутся без оси. Понадобятся достоверные события и связь kill→участники, тесты полноты парсинга. |
| Оставить `null`, но различать причину и показывать согласованный контракт | `performance.py`, нормализация/DTO, тесты; при неизменной формуле версия может остаться, но изменение публичной диагностики следует версионировать по правилам API. | Не выдаёт спорные данные за достоверные. | Не восстанавливает покрытие; Hoodwink остаётся зависим от Oracle. Тестировать reason codes и паритет слоёв. |
| Обрезать 1.2 до 1 | `performance.py`, нормализация, тесты; новая версия модели. | Число будет в диапазоне процентов. | Скрывает расхождение и меняет порядок сравнений; **не рекомендуется** без доказанной семантики. |

Рекомендация **не** состоит в снятии guard прямо сейчас. Сначала зафиксировать продуктовое определение: «отношение счётчиков, допускающее >100%» или «доля уникальных убийств», затем подтвердить происхождение Oracle 11 assists и на отдельном багфиксе согласовать слои и версии. Если подтверждения нет, сохранить `null` с точной причиной, не ослабляя пороги. Никаких специальных коэффициентов для match 9051271323.

## H. Команды и итог

Использованы `git rev-parse HEAD`, `git status --short`, `git blame -L 31,42 -- backend/app/services/performance.py`, поиски `rg`, чтение исходников, read-only SQLAlchemy `session.get(Match,9051271323)`, локальный REST GET, диагностический replay во временном `/tmp/ri02_replay.py`, `../.venv/bin/python -m pytest tests/test_performance.py tests/test_performance_preliminary.py tests/test_performance_preliminary_qa.py -q`. Replay менял только глубокую копию snapshot в памяти. Данных БД, старых фикстур, production-кода и существующих отчётов не меняли; платные сервисы не вызывали.

**Итог MIXED CAUSES:** каждый `null` технически объяснён, зависимость Hoodwink от Oracle подтверждена фактическим replay. Несогласованность нормализации и evaluator подтверждена как дефект контракта. Отказ от индекса при одной оси соответствует текущей модели. Нельзя назвать превышение 100% доказанно ошибочным или доказанно корректной «долей участия» без определения метрики и событийной проверки. Исправление должно быть отдельной задачей после согласования семантики; RI-02 не меняет статус иных этапов.
