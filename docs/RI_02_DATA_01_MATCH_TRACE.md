**RI-02-CAL-01-DATA / READY FOR QA.** Дата: 24.10.2026. HEAD `f222ee9dc322e98b8890ec642c9038244fe1e5a2`. Исследуется рабочее дерево с уже существующими незакоммиченными RI/PL/UI изменениями, а не чистый HEAD. Код, настройки, сохранённые матчи и прежние отчёты не изменены.

## Методика и формула

В таблицах ниже — фактические сохранённые inputs, новый **offline** replay текущим кодом, а не перезаписанные live отчёты. `traces.json` содержит полную точность всех 120 расчётов; здесь подробно приведены 20 игроков двух пилотов. В JSON `comparisons` содержит также контрольные математические сравнения GPM/XPM для support/unknown: evaluator их **не вызывает** и штрафов по ним нет. Наличие сравнения в диагностике не означает использование в модели.

`minutes=duration/60`; DPM=D/minutes; HDPM=hero_damage/minutes; TDPM=tower_damage/minutes; HPM=hero_healing/minutes. GPM/XPM уже имеют минутную единицу, передаются как float без повторного деления. Wards — исходные четыре счётчика, а не purchase/maps/log lengths. Oracle имеет obs_placed9 при purchase_ward_observer10 и sen_placed22 при purchase_ward_sentry23: сохраняются именно9/22, покупки не подставляются. KDA=(K+A)/D только при D>0, иначе null. Normalized derived округляет KDA/counter-ratio до4 знаков; observed считает из исходных целых с float точностью.

Counter ratio=(K+A)/team_score, если K,A и положительный score известны. Participation usable дополнительно требует score>=10, K<=score, при полных10 deaths K+A<=sum(all deaths); превышение score при пройденном sanity-check даёт over_team_score_unverified. Raw ratio не обрезается. В observed отдельный counter_ratio появляется **только при отказе usable** и доступной арифметике; normalized derived имеет историческое имя kill_participation, но статус available означает доступность арифметики, не оси.

Peers — союзники того же role_group без самого игрока; unknown сравнивается со всеми союзниками. Ref=median(доступных peer значений), minimum_cohort=2 включая себя. У смерти higher=bad, у остальных lower=bad. Floor=60/duration для rates, 1/team_score для KP, 1 для прочего. `bad=clip((own-ref)/max(ref,floor),0,1)` для смертей, иначе `clip((ref-own)/max(ref,floor),0,1)`. `good` — противоположное отклонение. При ref=0 для positive-oriented метрики сравнение null, наблюдаемый ненулевой вклад получает descriptive signal без кредитной величины.

Core weights S=.30,P=.25,E=.25,I=.20. Support/unknown S=.50,P=.50. Economy=mean(GPM_bad,XPM_bad), только если оба известны. Impact=HDPM_bad. Credit=15*max(good) для tower/healing/четырёх ward counters и для hero damage у noncore. Смерти/участие/economy good могут давать положительный сигнал, но не входят в credit. Credit-only bad не штрафуется. Coverage=sum(weights доступных осей). Нужно >=2 осей, coverage>=.70, разрешённый mode1/2/22, duration>=900 и валидная команда. Index=int(max(0,100*Σ(w*axis)/coverage-credit)+.5), иначе null. Округление credit в DTO до4 не используется обратно в расчёте. Signals показываются от .20; это не порог включения вклада в формулу. Confidence medium требует полных осей и confirmed ролей всей cohort. В этих12 матчах все low. Победитель в формулу не входит.

| Матч | Raw fetched UTC | duration s | score R/D | status | Индексов |
|---|---|---|---|---|---|
| 9051271323 | 2026-10-24T00:16:34.943391+00:00 | 1933 | 10/45 | FOUND_FULL | 8 |
| 9057722463 | 2026-10-23T13:37:42.905460+00:00 | 4349 | 44/42 | FOUND_PARTIAL | 10 |
| 9058839900 | 2026-10-24T00:29:46.155611+00:00 | 1257 | 32/11 | FOUND_PARTIAL | 10 |
| 9058840226 | 2026-10-24T00:29:44.731363+00:00 | 1154 | 16/2 | FOUND_PARTIAL | 0 |
| 9058840429 | 2026-10-24T00:29:43.276221+00:00 | 1100 | 1/62 | FOUND_PARTIAL | 0 |
| 9058840901 | 2026-10-24T00:29:41.838699+00:00 | 1113 | 8/47 | FOUND_PARTIAL | 5 |
| 9058841363 | 2026-10-24T00:29:40.410230+00:00 | 1103 | 7/51 | FOUND_PARTIAL | 5 |
| 9058841784 | 2026-10-24T00:29:38.976578+00:00 | 1137 | 13/31 | FOUND_PARTIAL | 10 |
| 9058841898 | 2026-10-24T00:29:37.536797+00:00 | 998 | 1/97 | FOUND_PARTIAL | 0 |
| 9058842039 | 2026-10-24T00:29:36.127912+00:00 | 1016 | 23/2 | FOUND_PARTIAL | 0 |
| 9058842359 | 2026-10-24T00:29:34.730913+00:00 | 901 | 17/5 | FOUND_PARTIAL | 5 |
| 9058843327 | 2026-10-24T00:29:33.080992+00:00 | 1023 | 4/44 | FOUND_PARTIAL | 0 |

## Матч 9051271323: все10 игроков

| Slot | Hero | Team | K/D/A raw=normalized | GPM/XPM | Role | Axes S/P/E/I | Coverage | Credit | Base | Index | confidence |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | Hoodwink | radiant | 1/12/7 | 211/329 | support 4 | 0.5/null/null/null | 0.5 | 3.994211288 | 50 | null | low |
| 1 | Oracle | radiant | 1/8/11 | 221/265 | support 5 | 0/null/null/null | 0.5 | 15 | 0 | null | low |
| 2 | Death Prophet | radiant | 5/12/1 | 436/531 | core 2 | 0.8461538462/0.07692307692/0/0 | 1 | 15 | 27.30769231 | 12 | low |
| 3 | Spectre | radiant | 1/8/5 | 358/386 | core 1 | 0/0.07692307692/0.1083315143/0.0751953125 | 1 | 0 | 6.135271031 | 6 | low |
| 4 | Chaos Knight | radiant | 2/5/5 | 336/371 | core 3 | 0/0/0.1722460438/0.5296786167 | 1 | 0 | 14.89972343 | 15 | low |
| 128 | Earthshaker | dire | 6/2/25 | 493/565 | core 3 | 0/0.1388888889/0.2278435168/0.150289225 | 1 | 0 | 12.17409464 | 12 | low |
| 129 | Sniper | dire | 19/3/16 | 777/745 | core 1 | 1/0/0/0 | 1 | 15 | 30 | 15 | low |
| 130 | Mirana | dire | 6/1/21 | 351/534 | support 4 | 0/0.06896551724/null/null | 1 | 15 | 3.448275862 | 0 | low |
| 131 | Kunkka | dire | 11/1/26 | 522/694 | core 2 | 0/0/0.08897637795/0.3234346264 | 1 | 0 | 8.693101976 | 9 | low |
| 132 | Undying | dire | 3/3/26 | 313/567 | support 5 | 1/0/null/null | 1 | 15 | 50 | 35 | low |

### Hoodwink, slot 0

Role evidence: `{"position": 4, "evidence": "estimated", "source_field": "position_est"}`; peer slots `[1]`; weights `{"survival": 0.5, "participation": 0.5}`.

| Raw field | Raw value | Normalized field/value |
|---|---|---|
| kills | 1 | kills=1 |
| deaths | 12 | deaths=12 |
| assists | 7 | assists=7 |
| hero_damage | 7875 | hero_damage=7875 |
| tower_damage | 229 | tower_damage=229 |
| hero_healing | 125 | hero_healing=125 |
| gold_per_min | 211 | gpm=211 |
| xp_per_min | 329 | xpm=329 |
| obs_placed | 3 | obs_placed=3 |
| sen_placed | 5 | sen_placed=5 |
| observer_kills | 1 | observer_kills=1 |
| sentry_kills | 0 | sentry_kills=0 |
| stuns | 29.466688 | stun_duration_seconds=29.466688 |
| leaver_status | 0 | leaver_status=NOT_MAPPED |
| position_est | 4 | performance_position={"position": 4, "evidence": "estimated", "source_field": "position_est"} |
| Metric | Observed | Peer slot:value | Median | Floor | Bad | Good | Использование |
|---|---|---|---|---|---|---|---|
| deaths_per_min | 0.3724780135 | {"1": 0.24831867563372995} | 0.2483186756 | 0.03103983445 | 0.5 | 0 | survival |
| kill_participation | 0.8 | {} | null | 0.1 | null | null | participation |
| gpm | 211 | {"1": 221.0} | 221 | 1 | 0.04524886878 | 0 | descriptive only; no compare in evaluator |
| xpm | 329 | {"1": 265.0} | 265 | 1 | 0 | 0.241509434 | descriptive only; no compare in evaluator |
| hero_damage_per_min | 244.4386963 | {"1": 193.0367304707708} | 193.0367305 | 0.03103983445 | 0 | 0.2662807525 | positive credit only |
| tower_damage_per_min | 7.10812209 | {"1": 0.0} | 0 | 0.03103983445 | null | null | positive credit only |
| healing_per_min | 3.879979307 | {"1": 294.90946714950854} | 294.9094671 | 0.03103983445 | 0.9868434902 | 0 | positive credit only |
| obs_placed | 3 | {"1": 9.0} | 9 | 1 | 0.6666666667 | 0 | positive credit only |
| sen_placed | 5 | {"1": 22.0} | 22 | 1 | 0.7727272727 | 0 | positive credit only |
| observer_kills | 1 | {"1": 2.0} | 2 | 1 | 0.5 | 0 | positive credit only |
| sentry_kills | 0 | {"1": 5.0} | 5 | 1 | 1 | 0 | positive credit only |

KDA observed=0.6666666667; normalized derived={"player_slot": 0, "kda": {"value": 0.6667, "status": "available", "decimal_places": 4}, "kill_participation": {"value": 0.8, "status": "available", "decimal_places": 4}}. Weighted sum=0.25; base=50; credit(full)=3.994211288; index=null. При недостающих осях base приведена только как промежуточная арифметика, не как разрешённая оценка.

Negative: ["relative_high:deaths_per_min"]. Positive: ["positive:hero_damage_per_min", "observed_contribution:tower_damage_per_min"].

Missing metrics: []. Reasons: ["position_estimated", "economy_not_penalized", "kda_descriptive_only", "comparison_unavailable:kill_participation", "zero_comparison_reference:tower_damage_per_min", "insufficient_data", "positive:hero_damage_per_min", "observed_contribution:tower_damage_per_min", "relative_high:deaths_per_min"].

### Oracle, slot 1

Role evidence: `{"position": 5, "evidence": "estimated", "source_field": "position_est"}`; peer slots `[0]`; weights `{"survival": 0.5, "participation": 0.5}`.

| Raw field | Raw value | Normalized field/value |
|---|---|---|
| kills | 1 | kills=1 |
| deaths | 8 | deaths=8 |
| assists | 11 | assists=11 |
| hero_damage | 6219 | hero_damage=6219 |
| tower_damage | 0 | tower_damage=0 |
| hero_healing | 9501 | hero_healing=9501 |
| gold_per_min | 221 | gpm=221 |
| xp_per_min | 265 | xpm=265 |
| obs_placed | 9 | obs_placed=9 |
| sen_placed | 22 | sen_placed=22 |
| observer_kills | 2 | observer_kills=2 |
| sentry_kills | 5 | sentry_kills=5 |
| stuns | 35.133186 | stun_duration_seconds=35.133186 |
| leaver_status | 0 | leaver_status=NOT_MAPPED |
| position_est | 5 | performance_position={"position": 5, "evidence": "estimated", "source_field": "position_est"} |
| Metric | Observed | Peer slot:value | Median | Floor | Bad | Good | Использование |
|---|---|---|---|---|---|---|---|
| deaths_per_min | 0.2483186756 | {"0": 0.3724780134505949} | 0.3724780135 | 0.03103983445 | 0 | 0.3333333333 | survival |
| kill_participation | null | {"0": 0.8} | 0.8 | 0.1 | null | null | participation |
| gpm | 221 | {"0": 211.0} | 211 | 1 | 0 | 0.04739336493 | descriptive only; no compare in evaluator |
| xpm | 265 | {"0": 329.0} | 329 | 1 | 0.1945288754 | 0 | descriptive only; no compare in evaluator |
| hero_damage_per_min | 193.0367305 | {"0": 244.4386963269529} | 244.4386963 | 0.03103983445 | 0.2102857143 | 0 | positive credit only |
| tower_damage_per_min | 0 | {"0": 7.108122090015519} | 7.10812209 | 0.03103983445 | 1 | 0 | positive credit only |
| healing_per_min | 294.9094671 | {"0": 3.8799793067770305} | 3.879979307 | 0.03103983445 | 0 | 1 | positive credit only |
| obs_placed | 9 | {"0": 3.0} | 3 | 1 | 0 | 1 | positive credit only |
| sen_placed | 22 | {"0": 5.0} | 5 | 1 | 0 | 1 | positive credit only |
| observer_kills | 2 | {"0": 1.0} | 1 | 1 | 0 | 1 | positive credit only |
| sentry_kills | 5 | {"0": 0.0} | 0 | 1 | null | null | positive credit only |

KDA observed=1.5; normalized derived={"player_slot": 1, "kda": {"value": 1.5, "status": "available", "decimal_places": 4}, "kill_participation": {"value": 1.2, "status": "available", "decimal_places": 4}}. Weighted sum=0; base=0; credit(full)=15; index=null. При недостающих осях base приведена только как промежуточная арифметика, не как разрешённая оценка.

Negative: []. Positive: ["positive:deaths_per_min", "positive:healing_per_min", "positive:obs_placed", "positive:sen_placed", "positive:observer_kills", "observed_contribution:sentry_kills"].

Missing metrics: ["kill_participation"]. Reasons: ["position_estimated", "economy_not_penalized", "kill_participation_over_team_score_unverified", "kda_descriptive_only", "comparison_unavailable:kill_participation", "zero_comparison_reference:sentry_kills", "insufficient_data", "positive:deaths_per_min", "positive:healing_per_min", "positive:obs_placed", "positive:sen_placed", "positive:observer_kills", "observed_contribution:sentry_kills"].

### Death Prophet, slot 2

Role evidence: `{"position": 2, "evidence": "estimated", "source_field": "position_est"}`; peer slots `[3, 4]`; weights `{"survival": 0.3, "participation": 0.25, "economy": 0.25, "impact": 0.2}`.

| Raw field | Raw value | Normalized field/value |
|---|---|---|
| kills | 5 | kills=5 |
| deaths | 12 | deaths=12 |
| assists | 1 | assists=1 |
| hero_damage | 20689 | hero_damage=20689 |
| tower_damage | 1719 | tower_damage=1719 |
| hero_healing | 0 | hero_healing=0 |
| gold_per_min | 436 | gpm=436 |
| xp_per_min | 531 | xpm=531 |
| obs_placed | 2 | obs_placed=2 |
| sen_placed | 2 | sen_placed=2 |
| observer_kills | 1 | observer_kills=1 |
| sentry_kills | 0 | sentry_kills=0 |
| stuns | 0 | stun_duration_seconds=0 |
| leaver_status | 0 | leaver_status=NOT_MAPPED |
| position_est | 2 | performance_position={"position": 2, "evidence": "estimated", "source_field": "position_est"} |
| Metric | Observed | Peer slot:value | Median | Floor | Bad | Good | Использование |
|---|---|---|---|---|---|---|---|
| deaths_per_min | 0.3724780135 | {"3": 0.24831867563372995, "4": 0.1551991722710812} | 0.201758924 | 0.03103983445 | 0.8461538462 | 0 | survival |
| kill_participation | 0.6 | {"3": 0.6, "4": 0.7} | 0.65 | 0.1 | 0.07692307692 | 0 | participation |
| gpm | 436 | {"3": 358.0, "4": 336.0} | 347 | 1 | 0 | 0.2564841499 | economy |
| xpm | 531 | {"3": 386.0, "4": 371.0} | 378.5 | 1 | 0 | 0.4029062087 | economy |
| hero_damage_per_min | 642.183135 | {"3": 411.52612519399895, "4": 247.79099844800825} | 329.6585618 | 0.03103983445 | 0 | 0.9480250459 | impact |
| tower_damage_per_min | 53.35747543 | {"3": 1.5830315571650284, "4": 9.591308846352819} | 5.587170202 | 0.03103983445 | 0 | 1 | positive credit only |
| healing_per_min | 0 | {"3": 0.0, "4": 0.0} | 0 | 0.03103983445 | null | null | positive credit only |
| obs_placed | 2 | {"3": 0.0, "4": 0.0} | 0 | 1 | null | null | positive credit only |
| sen_placed | 2 | {"3": 0.0, "4": 0.0} | 0 | 1 | null | null | positive credit only |
| observer_kills | 1 | {"3": 0.0, "4": 0.0} | 0 | 1 | null | null | positive credit only |
| sentry_kills | 0 | {"3": 0.0, "4": 0.0} | 0 | 1 | null | null | positive credit only |

KDA observed=0.5; normalized derived={"player_slot": 2, "kda": {"value": 0.5, "status": "available", "decimal_places": 4}, "kill_participation": {"value": 0.6, "status": "available", "decimal_places": 4}}. Weighted sum=0.2730769231; base=27.30769231; credit(full)=15; index=12. При недостающих осях base приведена только как промежуточная арифметика, не как разрешённая оценка.

Negative: ["relative_high:deaths_per_min"]. Positive: ["positive:gpm", "positive:xpm", "positive:hero_damage_per_min", "positive:tower_damage_per_min", "observed_contribution:obs_placed", "observed_contribution:sen_placed", "observed_contribution:observer_kills"].

Missing metrics: []. Reasons: ["position_estimated", "kda_descriptive_only", "zero_comparison_reference:healing_per_min", "zero_comparison_reference:obs_placed", "zero_comparison_reference:sen_placed", "zero_comparison_reference:observer_kills", "zero_comparison_reference:sentry_kills", "positive:gpm", "positive:xpm", "positive:hero_damage_per_min", "positive:tower_damage_per_min", "observed_contribution:obs_placed", "observed_contribution:sen_placed", "observed_contribution:observer_kills", "relative_high:deaths_per_min"].

### Spectre, slot 3

Role evidence: `{"position": 1, "evidence": "estimated", "source_field": "position_est"}`; peer slots `[2, 4]`; weights `{"survival": 0.3, "participation": 0.25, "economy": 0.25, "impact": 0.2}`.

| Raw field | Raw value | Normalized field/value |
|---|---|---|
| kills | 1 | kills=1 |
| deaths | 8 | deaths=8 |
| assists | 5 | assists=5 |
| hero_damage | 13258 | hero_damage=13258 |
| tower_damage | 51 | tower_damage=51 |
| hero_healing | 0 | hero_healing=0 |
| gold_per_min | 358 | gpm=358 |
| xp_per_min | 386 | xpm=386 |
| obs_placed | 0 | obs_placed=0 |
| sen_placed | 0 | sen_placed=0 |
| observer_kills | 0 | observer_kills=0 |
| sentry_kills | 0 | sentry_kills=0 |
| stuns | 0 | stun_duration_seconds=0 |
| leaver_status | 0 | leaver_status=NOT_MAPPED |
| position_est | 1 | performance_position={"position": 1, "evidence": "estimated", "source_field": "position_est"} |
| Metric | Observed | Peer slot:value | Median | Floor | Bad | Good | Использование |
|---|---|---|---|---|---|---|---|
| deaths_per_min | 0.2483186756 | {"2": 0.3724780134505949, "4": 0.1551991722710812} | 0.2638385929 | 0.03103983445 | 0 | 0.05882352941 | survival |
| kill_participation | 0.6 | {"2": 0.6, "4": 0.7} | 0.65 | 0.1 | 0.07692307692 | 0 | participation |
| gpm | 358 | {"2": 436.0, "4": 336.0} | 386 | 1 | 0.0725388601 | 0 | economy |
| xpm | 386 | {"2": 531.0, "4": 371.0} | 451 | 1 | 0.1441241685 | 0 | economy |
| hero_damage_per_min | 411.5261252 | {"2": 642.1831350232799, "4": 247.79099844800825} | 444.9870667 | 0.03103983445 | 0.0751953125 | 0 | impact |
| tower_damage_per_min | 1.583031557 | {"2": 53.35747542679772, "4": 9.591308846352819} | 31.47439214 | 0.03103983445 | 0.949704142 | 0 | positive credit only |
| healing_per_min | 0 | {"2": 0.0, "4": 0.0} | 0 | 0.03103983445 | null | null | positive credit only |
| obs_placed | 0 | {"2": 2.0, "4": 0.0} | 1 | 1 | 1 | 0 | positive credit only |
| sen_placed | 0 | {"2": 2.0, "4": 0.0} | 1 | 1 | 1 | 0 | positive credit only |
| observer_kills | 0 | {"2": 1.0, "4": 0.0} | 0.5 | 1 | 0.5 | 0 | positive credit only |
| sentry_kills | 0 | {"2": 0.0, "4": 0.0} | 0 | 1 | null | null | positive credit only |

KDA observed=0.75; normalized derived={"player_slot": 3, "kda": {"value": 0.75, "status": "available", "decimal_places": 4}, "kill_participation": {"value": 0.6, "status": "available", "decimal_places": 4}}. Weighted sum=0.06135271031; base=6.135271031; credit(full)=0; index=6. При недостающих осях base приведена только как промежуточная арифметика, не как разрешённая оценка.

Negative: []. Positive: [].

Missing metrics: []. Reasons: ["position_estimated", "kda_descriptive_only", "zero_comparison_reference:healing_per_min", "zero_comparison_reference:sentry_kills"].

### Chaos Knight, slot 4

Role evidence: `{"position": 3, "evidence": "estimated", "source_field": "position_est"}`; peer slots `[2, 3]`; weights `{"survival": 0.3, "participation": 0.25, "economy": 0.25, "impact": 0.2}`.

| Raw field | Raw value | Normalized field/value |
|---|---|---|
| kills | 2 | kills=2 |
| deaths | 5 | deaths=5 |
| assists | 5 | assists=5 |
| hero_damage | 7983 | hero_damage=7983 |
| tower_damage | 309 | tower_damage=309 |
| hero_healing | 0 | hero_healing=0 |
| gold_per_min | 336 | gpm=336 |
| xp_per_min | 371 | xpm=371 |
| obs_placed | 0 | obs_placed=0 |
| sen_placed | 0 | sen_placed=0 |
| observer_kills | 0 | observer_kills=0 |
| sentry_kills | 0 | sentry_kills=0 |
| stuns | 23.500038 | stun_duration_seconds=23.500038 |
| leaver_status | 0 | leaver_status=NOT_MAPPED |
| position_est | 3 | performance_position={"position": 3, "evidence": "estimated", "source_field": "position_est"} |
| Metric | Observed | Peer slot:value | Median | Floor | Bad | Good | Использование |
|---|---|---|---|---|---|---|---|
| deaths_per_min | 0.1551991723 | {"2": 0.3724780134505949, "3": 0.24831867563372995} | 0.3103983445 | 0.03103983445 | 0 | 0.5 | survival |
| kill_participation | 0.7 | {"2": 0.6, "3": 0.6} | 0.6 | 0.1 | 0 | 0.1666666667 | participation |
| gpm | 336 | {"2": 436.0, "3": 358.0} | 397 | 1 | 0.1536523929 | 0 | economy |
| xpm | 371 | {"2": 531.0, "3": 386.0} | 458.5 | 1 | 0.1908396947 | 0 | economy |
| hero_damage_per_min | 247.7909984 | {"2": 642.1831350232799, "3": 411.52612519399895} | 526.8546301 | 0.03103983445 | 0.5296786167 | 0 | impact |
| tower_damage_per_min | 9.591308846 | {"2": 53.35747542679772, "3": 1.5830315571650284} | 27.47025349 | 0.03103983445 | 0.6508474576 | 0 | positive credit only |
| healing_per_min | 0 | {"2": 0.0, "3": 0.0} | 0 | 0.03103983445 | null | null | positive credit only |
| obs_placed | 0 | {"2": 2.0, "3": 0.0} | 1 | 1 | 1 | 0 | positive credit only |
| sen_placed | 0 | {"2": 2.0, "3": 0.0} | 1 | 1 | 1 | 0 | positive credit only |
| observer_kills | 0 | {"2": 1.0, "3": 0.0} | 0.5 | 1 | 0.5 | 0 | positive credit only |
| sentry_kills | 0 | {"2": 0.0, "3": 0.0} | 0 | 1 | null | null | positive credit only |

KDA observed=1.4; normalized derived={"player_slot": 4, "kda": {"value": 1.4, "status": "available", "decimal_places": 4}, "kill_participation": {"value": 0.7, "status": "available", "decimal_places": 4}}. Weighted sum=0.1489972343; base=14.89972343; credit(full)=0; index=15. При недостающих осях base приведена только как промежуточная арифметика, не как разрешённая оценка.

Negative: ["relative_low:hero_damage_per_min"]. Positive: ["positive:deaths_per_min"].

Missing metrics: []. Reasons: ["position_estimated", "kda_descriptive_only", "zero_comparison_reference:healing_per_min", "zero_comparison_reference:sentry_kills", "positive:deaths_per_min", "relative_low:hero_damage_per_min"].

### Earthshaker, slot 128

Role evidence: `{"position": 3, "evidence": "estimated", "source_field": "position_est"}`; peer slots `[129, 131]`; weights `{"survival": 0.3, "participation": 0.25, "economy": 0.25, "impact": 0.2}`.

| Raw field | Raw value | Normalized field/value |
|---|---|---|
| kills | 6 | kills=6 |
| deaths | 2 | deaths=2 |
| assists | 25 | assists=25 |
| hero_damage | 23650 | hero_damage=23650 |
| tower_damage | 1696 | tower_damage=1696 |
| hero_healing | 0 | hero_healing=0 |
| gold_per_min | 493 | gpm=493 |
| xp_per_min | 565 | xpm=565 |
| obs_placed | 0 | obs_placed=0 |
| sen_placed | 0 | sen_placed=0 |
| observer_kills | 0 | observer_kills=0 |
| sentry_kills | 0 | sentry_kills=0 |
| stuns | 168.83093 | stun_duration_seconds=168.83093 |
| leaver_status | 0 | leaver_status=NOT_MAPPED |
| position_est | 3 | performance_position={"position": 3, "evidence": "estimated", "source_field": "position_est"} |
| Metric | Observed | Peer slot:value | Median | Floor | Bad | Good | Использование |
|---|---|---|---|---|---|---|---|
| deaths_per_min | 0.06207966891 | {"129": 0.09311950336264872, "131": 0.031039834454216243} | 0.06207966891 | 0.03103983445 | 0 | 0 | survival |
| kill_participation | 0.6888888889 | {"129": 0.7777777777777778, "131": 0.8222222222222222} | 0.8 | 0.02222222222 | 0.1388888889 | 0 | participation |
| gpm | 493 | {"129": 777.0, "131": 522.0} | 649.5 | 1 | 0.2409545804 | 0 | economy |
| xpm | 565 | {"129": 745.0, "131": 694.0} | 719.5 | 1 | 0.2147324531 | 0 | economy |
| hero_damage_per_min | 734.0920848 | {"129": 1105.54578375582, "131": 622.3176409725814} | 863.9317124 | 0.03103983445 | 0.150289225 | 0 | impact |
| tower_damage_per_min | 52.64355923 | {"129": 638.0548370408691, "131": 103.92136575271599} | 370.9881014 | 0.03103983445 | 0.8580990629 | 0 | positive credit only |
| healing_per_min | 0 | {"129": 0.0, "131": 0.0} | 0 | 0.03103983445 | null | null | positive credit only |
| obs_placed | 0 | {"129": 0.0, "131": 0.0} | 0 | 1 | null | null | positive credit only |
| sen_placed | 0 | {"129": 0.0, "131": 0.0} | 0 | 1 | null | null | positive credit only |
| observer_kills | 0 | {"129": 0.0, "131": 0.0} | 0 | 1 | null | null | positive credit only |
| sentry_kills | 0 | {"129": 0.0, "131": 0.0} | 0 | 1 | null | null | positive credit only |

KDA observed=15.5; normalized derived={"player_slot": 128, "kda": {"value": 15.5, "status": "available", "decimal_places": 4}, "kill_participation": {"value": 0.6889, "status": "available", "decimal_places": 4}}. Weighted sum=0.1217409464; base=12.17409464; credit(full)=0; index=12. При недостающих осях base приведена только как промежуточная арифметика, не как разрешённая оценка.

Negative: ["relative_low:gpm", "relative_low:xpm"]. Positive: [].

Missing metrics: []. Reasons: ["position_estimated", "kda_descriptive_only", "zero_comparison_reference:healing_per_min", "zero_comparison_reference:obs_placed", "zero_comparison_reference:sen_placed", "zero_comparison_reference:observer_kills", "zero_comparison_reference:sentry_kills", "relative_low:gpm", "relative_low:xpm"].

### Sniper, slot 129

Role evidence: `{"position": 1, "evidence": "estimated", "source_field": "position_est"}`; peer slots `[128, 131]`; weights `{"survival": 0.3, "participation": 0.25, "economy": 0.25, "impact": 0.2}`.

| Raw field | Raw value | Normalized field/value |
|---|---|---|
| kills | 19 | kills=19 |
| deaths | 3 | deaths=3 |
| assists | 16 | assists=16 |
| hero_damage | 35617 | hero_damage=35617 |
| tower_damage | 20556 | tower_damage=20556 |
| hero_healing | 0 | hero_healing=0 |
| gold_per_min | 777 | gpm=777 |
| xp_per_min | 745 | xpm=745 |
| obs_placed | 0 | obs_placed=0 |
| sen_placed | 0 | sen_placed=0 |
| observer_kills | 0 | observer_kills=0 |
| sentry_kills | 0 | sentry_kills=0 |
| stuns | 0.06669189 | stun_duration_seconds=0.06669189 |
| leaver_status | 0 | leaver_status=NOT_MAPPED |
| position_est | 1 | performance_position={"position": 1, "evidence": "estimated", "source_field": "position_est"} |
| Metric | Observed | Peer slot:value | Median | Floor | Bad | Good | Использование |
|---|---|---|---|---|---|---|---|
| deaths_per_min | 0.09311950336 | {"128": 0.062079668908432487, "131": 0.031039834454216243} | 0.04655975168 | 0.03103983445 | 1 | 0 | survival |
| kill_participation | 0.7777777778 | {"128": 0.6888888888888889, "131": 0.8222222222222222} | 0.7555555556 | 0.02222222222 | 0 | 0.02941176471 | participation |
| gpm | 777 | {"128": 493.0, "131": 522.0} | 507.5 | 1 | 0 | 0.5310344828 | economy |
| xpm | 745 | {"128": 565.0, "131": 694.0} | 629.5 | 1 | 0 | 0.1834789515 | economy |
| hero_damage_per_min | 1105.545784 | {"128": 734.0920848422141, "131": 622.3176409725814} | 678.2048629 | 0.03103983445 | 0 | 0.6301059521 | impact |
| tower_damage_per_min | 638.054837 | {"128": 52.64355923435075, "131": 103.92136575271599} | 78.28246249 | 0.03103983445 | 0 | 1 | positive credit only |
| healing_per_min | 0 | {"128": 0.0, "131": 0.0} | 0 | 0.03103983445 | null | null | positive credit only |
| obs_placed | 0 | {"128": 0.0, "131": 0.0} | 0 | 1 | null | null | positive credit only |
| sen_placed | 0 | {"128": 0.0, "131": 0.0} | 0 | 1 | null | null | positive credit only |
| observer_kills | 0 | {"128": 0.0, "131": 0.0} | 0 | 1 | null | null | positive credit only |
| sentry_kills | 0 | {"128": 0.0, "131": 0.0} | 0 | 1 | null | null | positive credit only |

KDA observed=11.66666667; normalized derived={"player_slot": 129, "kda": {"value": 11.6667, "status": "available", "decimal_places": 4}, "kill_participation": {"value": 0.7778, "status": "available", "decimal_places": 4}}. Weighted sum=0.3; base=30; credit(full)=15; index=15. При недостающих осях base приведена только как промежуточная арифметика, не как разрешённая оценка.

Negative: ["relative_high:deaths_per_min"]. Positive: ["positive:gpm", "positive:hero_damage_per_min", "positive:tower_damage_per_min"].

Missing metrics: []. Reasons: ["position_estimated", "kda_descriptive_only", "zero_comparison_reference:healing_per_min", "zero_comparison_reference:obs_placed", "zero_comparison_reference:sen_placed", "zero_comparison_reference:observer_kills", "zero_comparison_reference:sentry_kills", "positive:gpm", "positive:hero_damage_per_min", "positive:tower_damage_per_min", "relative_high:deaths_per_min"].

### Mirana, slot 130

Role evidence: `{"position": 4, "evidence": "estimated", "source_field": "position_est"}`; peer slots `[132]`; weights `{"survival": 0.5, "participation": 0.5}`.

| Raw field | Raw value | Normalized field/value |
|---|---|---|
| kills | 6 | kills=6 |
| deaths | 1 | deaths=1 |
| assists | 21 | assists=21 |
| hero_damage | 13847 | hero_damage=13847 |
| tower_damage | 2370 | tower_damage=2370 |
| hero_healing | 1329 | hero_healing=1329 |
| gold_per_min | 351 | gpm=351 |
| xp_per_min | 534 | xpm=534 |
| obs_placed | 2 | obs_placed=2 |
| sen_placed | 2 | sen_placed=2 |
| observer_kills | 1 | observer_kills=1 |
| sentry_kills | 1 | sentry_kills=1 |
| stuns | 25.566797 | stun_duration_seconds=25.566797 |
| leaver_status | 0 | leaver_status=NOT_MAPPED |
| position_est | 4 | performance_position={"position": 4, "evidence": "estimated", "source_field": "position_est"} |
| Metric | Observed | Peer slot:value | Median | Floor | Bad | Good | Использование |
|---|---|---|---|---|---|---|---|
| deaths_per_min | 0.03103983445 | {"132": 0.09311950336264872} | 0.09311950336 | 0.03103983445 | 0 | 0.6666666667 | survival |
| kill_participation | 0.6 | {"132": 0.6444444444444445} | 0.6444444444 | 0.02222222222 | 0.06896551724 | 0 | participation |
| gpm | 351 | {"132": 313.0} | 313 | 1 | 0 | 0.1214057508 | descriptive only; no compare in evaluator |
| xpm | 534 | {"132": 567.0} | 567 | 1 | 0.0582010582 | 0 | descriptive only; no compare in evaluator |
| hero_damage_per_min | 429.8085877 | {"132": 171.33988618727366} | 171.3398862 | 0.03103983445 | 0 | 1 | positive credit only |
| tower_damage_per_min | 73.56440766 | {"132": 25.91826176927056} | 25.91826177 | 0.03103983445 | 0 | 1 | positive credit only |
| healing_per_min | 41.25193999 | {"132": 311.54681841696845} | 311.5468184 | 0.03103983445 | 0.8675899173 | 0 | positive credit only |
| obs_placed | 2 | {"132": 9.0} | 9 | 1 | 0.7777777778 | 0 | positive credit only |
| sen_placed | 2 | {"132": 13.0} | 13 | 1 | 0.8461538462 | 0 | positive credit only |
| observer_kills | 1 | {"132": 0.0} | 0 | 1 | null | null | positive credit only |
| sentry_kills | 1 | {"132": 8.0} | 8 | 1 | 0.875 | 0 | positive credit only |

KDA observed=27; normalized derived={"player_slot": 130, "kda": {"value": 27.0, "status": "available", "decimal_places": 4}, "kill_participation": {"value": 0.6, "status": "available", "decimal_places": 4}}. Weighted sum=0.03448275862; base=3.448275862; credit(full)=15; index=0. При недостающих осях base приведена только как промежуточная арифметика, не как разрешённая оценка.

Negative: []. Positive: ["positive:deaths_per_min", "positive:hero_damage_per_min", "positive:tower_damage_per_min", "observed_contribution:observer_kills"].

Missing metrics: []. Reasons: ["position_estimated", "economy_not_penalized", "kda_descriptive_only", "zero_comparison_reference:observer_kills", "positive:deaths_per_min", "positive:hero_damage_per_min", "positive:tower_damage_per_min", "observed_contribution:observer_kills"].

### Kunkka, slot 131

Role evidence: `{"position": 2, "evidence": "estimated", "source_field": "position_est"}`; peer slots `[128, 129]`; weights `{"survival": 0.3, "participation": 0.25, "economy": 0.25, "impact": 0.2}`.

| Raw field | Raw value | Normalized field/value |
|---|---|---|
| kills | 11 | kills=11 |
| deaths | 1 | deaths=1 |
| assists | 26 | assists=26 |
| hero_damage | 20049 | hero_damage=20049 |
| tower_damage | 3348 | tower_damage=3348 |
| hero_healing | 0 | hero_healing=0 |
| gold_per_min | 522 | gpm=522 |
| xp_per_min | 694 | xpm=694 |
| obs_placed | 0 | obs_placed=0 |
| sen_placed | 0 | sen_placed=0 |
| observer_kills | 0 | observer_kills=0 |
| sentry_kills | 0 | sentry_kills=0 |
| stuns | 43.3004 | stun_duration_seconds=43.3004 |
| leaver_status | 0 | leaver_status=NOT_MAPPED |
| position_est | 2 | performance_position={"position": 2, "evidence": "estimated", "source_field": "position_est"} |
| Metric | Observed | Peer slot:value | Median | Floor | Bad | Good | Использование |
|---|---|---|---|---|---|---|---|
| deaths_per_min | 0.03103983445 | {"128": 0.062079668908432487, "129": 0.09311950336264872} | 0.07759958614 | 0.03103983445 | 0 | 0.6 | survival |
| kill_participation | 0.8222222222 | {"128": 0.6888888888888889, "129": 0.7777777777777778} | 0.7333333333 | 0.02222222222 | 0 | 0.1212121212 | participation |
| gpm | 522 | {"128": 493.0, "129": 777.0} | 635 | 1 | 0.1779527559 | 0 | economy |
| xpm | 694 | {"128": 565.0, "129": 745.0} | 655 | 1 | 0 | 0.05954198473 | economy |
| hero_damage_per_min | 622.317641 | {"128": 734.0920848422141, "129": 1105.54578375582} | 919.8189343 | 0.03103983445 | 0.3234346264 | 0 | impact |
| tower_damage_per_min | 103.9213658 | {"128": 52.64355923435075, "129": 638.0548370408691} | 345.3491981 | 0.03103983445 | 0.6990832285 | 0 | positive credit only |
| healing_per_min | 0 | {"128": 0.0, "129": 0.0} | 0 | 0.03103983445 | null | null | positive credit only |
| obs_placed | 0 | {"128": 0.0, "129": 0.0} | 0 | 1 | null | null | positive credit only |
| sen_placed | 0 | {"128": 0.0, "129": 0.0} | 0 | 1 | null | null | positive credit only |
| observer_kills | 0 | {"128": 0.0, "129": 0.0} | 0 | 1 | null | null | positive credit only |
| sentry_kills | 0 | {"128": 0.0, "129": 0.0} | 0 | 1 | null | null | positive credit only |

KDA observed=37; normalized derived={"player_slot": 131, "kda": {"value": 37.0, "status": "available", "decimal_places": 4}, "kill_participation": {"value": 0.8222, "status": "available", "decimal_places": 4}}. Weighted sum=0.08693101976; base=8.693101976; credit(full)=0; index=9. При недостающих осях base приведена только как промежуточная арифметика, не как разрешённая оценка.

Negative: ["relative_low:hero_damage_per_min"]. Positive: ["positive:deaths_per_min"].

Missing metrics: []. Reasons: ["position_estimated", "kda_descriptive_only", "zero_comparison_reference:healing_per_min", "zero_comparison_reference:obs_placed", "zero_comparison_reference:sen_placed", "zero_comparison_reference:observer_kills", "zero_comparison_reference:sentry_kills", "positive:deaths_per_min", "relative_low:hero_damage_per_min"].

### Undying, slot 132

Role evidence: `{"position": 5, "evidence": "estimated", "source_field": "position_est"}`; peer slots `[130]`; weights `{"survival": 0.5, "participation": 0.5}`.

| Raw field | Raw value | Normalized field/value |
|---|---|---|
| kills | 3 | kills=3 |
| deaths | 3 | deaths=3 |
| assists | 26 | assists=26 |
| hero_damage | 5520 | hero_damage=5520 |
| tower_damage | 835 | tower_damage=835 |
| hero_healing | 10037 | hero_healing=10037 |
| gold_per_min | 313 | gpm=313 |
| xp_per_min | 567 | xpm=567 |
| obs_placed | 9 | obs_placed=9 |
| sen_placed | 13 | sen_placed=13 |
| observer_kills | 0 | observer_kills=0 |
| sentry_kills | 8 | sentry_kills=8 |
| stuns | 0 | stun_duration_seconds=0 |
| leaver_status | 0 | leaver_status=NOT_MAPPED |
| position_est | 5 | performance_position={"position": 5, "evidence": "estimated", "source_field": "position_est"} |
| Metric | Observed | Peer slot:value | Median | Floor | Bad | Good | Использование |
|---|---|---|---|---|---|---|---|
| deaths_per_min | 0.09311950336 | {"130": 0.031039834454216243} | 0.03103983445 | 0.03103983445 | 1 | 0 | survival |
| kill_participation | 0.6444444444 | {"130": 0.6} | 0.6 | 0.02222222222 | 0 | 0.07407407407 | participation |
| gpm | 313 | {"130": 351.0} | 351 | 1 | 0.1082621083 | 0 | descriptive only; no compare in evaluator |
| xpm | 567 | {"130": 534.0} | 534 | 1 | 0 | 0.06179775281 | descriptive only; no compare in evaluator |
| hero_damage_per_min | 171.3398862 | {"130": 429.8085876875323} | 429.8085877 | 0.03103983445 | 0.6013576948 | 0 | positive credit only |
| tower_damage_per_min | 25.91826177 | {"130": 73.56440765649249} | 73.56440766 | 0.03103983445 | 0.6476793249 | 0 | positive credit only |
| healing_per_min | 311.5468184 | {"130": 41.25193998965339} | 41.25193999 | 0.03103983445 | 0 | 1 | positive credit only |
| obs_placed | 9 | {"130": 2.0} | 2 | 1 | 0 | 1 | positive credit only |
| sen_placed | 13 | {"130": 2.0} | 2 | 1 | 0 | 1 | positive credit only |
| observer_kills | 0 | {"130": 1.0} | 1 | 1 | 1 | 0 | positive credit only |
| sentry_kills | 8 | {"130": 1.0} | 1 | 1 | 0 | 1 | positive credit only |

KDA observed=9.666666667; normalized derived={"player_slot": 132, "kda": {"value": 9.6667, "status": "available", "decimal_places": 4}, "kill_participation": {"value": 0.6444, "status": "available", "decimal_places": 4}}. Weighted sum=0.5; base=50; credit(full)=15; index=35. При недостающих осях base приведена только как промежуточная арифметика, не как разрешённая оценка.

Negative: ["relative_high:deaths_per_min"]. Positive: ["positive:healing_per_min", "positive:obs_placed", "positive:sen_placed", "positive:sentry_kills"].

Missing metrics: []. Reasons: ["position_estimated", "economy_not_penalized", "kda_descriptive_only", "positive:healing_per_min", "positive:obs_placed", "positive:sen_placed", "positive:sentry_kills", "relative_high:deaths_per_min"].

### Командный выбор

| Team | scored | strict | preliminary |
|---|---|---|---|
| radiant | 3 | {"selected_player_slot": null, "selected_team": null, "selection_status": "no_confident_selection", "evidence": ["incomplete_or_low_confidence_team"]} | {"projection_version": "ri_preliminary_v1", "minimum_margin": 15, "status": "none", "player_slots": [], "leader_slot": null, "highest_index": null, "margin": null, "confidence": "low", "reason_codes": ["incomplete_player_scores", "roles_unconfirmed", "leaver_context_unknown"]} |
| dire | 5 | {"selected_player_slot": null, "selected_team": null, "selection_status": "no_confident_selection", "evidence": ["incomplete_or_low_confidence_team"]} | {"projection_version": "ri_preliminary_v1", "minimum_margin": 15, "status": "single", "player_slots": [132], "leader_slot": 132, "highest_index": 35, "margin": 20, "confidence": "low", "reason_codes": ["highest_relative_index", "roles_unconfirmed", "leaver_context_unknown"]} |

## Матч 9057722463: все10 игроков

| Slot | Hero | Team | K/D/A raw=normalized | GPM/XPM | Role | Axes S/P/E/I | Coverage | Credit | Base | Index | confidence |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | Techies | radiant | 2/16/26 | 429/729 | unknown null | 1/0/null/null | 1 | 0 | 50 | 50 | low |
| 1 | Shadow Fiend | radiant | 11/3/13 | 665/967 | unknown null | 0/0.1724137931/null/null | 1 | 15 | 8.620689655 | 0 | low |
| 2 | Anti-Mage | radiant | 13/4/13 | 769/1018 | unknown null | 0/0.1034482759/null/null | 1 | 15 | 5.172413793 | 0 | low |
| 3 | Tidehunter | radiant | 10/8/20 | 692/901 | unknown null | 0.06666666667/0/null/null | 1 | 3.656575315 | 3.333333333 | 0 | low |
| 4 | Mirana | radiant | 7/11/23 | 398/730 | unknown null | 0.8333333333/0/null/null | 1 | 0 | 41.66666667 | 42 | low |
| 128 | Centaur Warrunner | dire | 5/8/27 | 685/948 | unknown null | 0/0/null/null | 1 | 15 | 0 | 0 | low |
| 129 | Sven | dire | 9/8/13 | 559/741 | unknown null | 0/0.2/null/null | 1 | 14.39440994 | 10 | 0 | low |
| 130 | Invoker | dire | 7/6/16 | 637/840 | unknown null | 0/0.1636363636/null/null | 1 | 12.93698879 | 8.181818182 | 0 | low |
| 131 | Pudge | dire | 7/13/22 | 346/709 | unknown null | 0.625/0/null/null | 1 | 0 | 31.25 | 31 | low |
| 132 | Lion | dire | 12/9/14 | 350/610 | unknown null | 0.125/0/null/null | 1 | 0 | 6.25 | 6 | low |

### Techies, slot 0

Role evidence: `{"position": null, "evidence": "unknown", "source_field": null}`; peer slots `[1, 2, 3, 4]`; weights `{"survival": 0.5, "participation": 0.5}`.

| Raw field | Raw value | Normalized field/value |
|---|---|---|
| kills | 2 | kills=2 |
| deaths | 16 | deaths=16 |
| assists | 26 | assists=26 |
| hero_damage | 34275 | hero_damage=34275 |
| tower_damage | 1874 | tower_damage=1874 |
| hero_healing | 1530 | hero_healing=1530 |
| gold_per_min | 429 | gpm=429 |
| xp_per_min | 729 | xpm=729 |
| obs_placed | <absent> | obs_placed=null |
| sen_placed | <absent> | sen_placed=null |
| observer_kills | <absent> | observer_kills=null |
| sentry_kills | <absent> | sentry_kills=null |
| stuns | <absent> | stun_duration_seconds=null |
| leaver_status | 0 | leaver_status=NOT_MAPPED |
| position_est | <absent> | performance_position={"position": null, "evidence": "unknown", "source_field": null} |
| Metric | Observed | Peer slot:value | Median | Floor | Bad | Good | Использование |
|---|---|---|---|---|---|---|---|
| deaths_per_min | 0.2207404001 | {"1": 0.04138882501724534, "2": 0.05518510002299379, "3": 0.11037020004598758, "4": 0.15175902506323294} | 0.08277765003 | 0.01379627501 | 1 | 0 | survival |
| kill_participation | 0.6363636364 | {"1": 0.5454545454545454, "2": 0.5909090909090909, "3": 0.6818181818181818, "4": 0.6818181818181818} | 0.6363636364 | 0.02272727273 | 0 | 0 | participation |
| gpm | 429 | {"1": 665.0, "2": 769.0, "3": 692.0, "4": 398.0} | 678.5 | 1 | 0.3677229182 | 0 | descriptive only; no compare in evaluator |
| xpm | 729 | {"1": 967.0, "2": 1018.0, "3": 901.0, "4": 730.0} | 934 | 1 | 0.2194860814 | 0 | descriptive only; no compare in evaluator |
| hero_damage_per_min | 472.8673258 | {"1": 689.3170843872155, "2": 908.1535985283973, "3": 798.6249712577604, "4": 594.8815819728674} | 743.9710278 | 0.01379627501 | 0.3644008864 | 0 | positive credit only |
| tower_damage_per_min | 25.85421936 | {"1": 89.20671418716947, "2": 154.84939066452057, "3": 27.854679236606117, "4": 17.121177282133825} | 58.53069671 | 0.01379627501 | 0.5582793164 | 0 | positive credit only |
| healing_per_min | 21.10830076 | {"1": 0.0, "2": 0.0, "3": 0.0, "4": 11.312945504713728} | 0 | 0.01379627501 | null | null | positive credit only |
| obs_placed | null | {} | null | 1 | null | null | positive credit only |
| sen_placed | null | {} | null | 1 | null | null | positive credit only |
| observer_kills | null | {} | null | 1 | null | null | positive credit only |
| sentry_kills | null | {} | null | 1 | null | null | positive credit only |

KDA observed=1.75; normalized derived={"player_slot": 0, "kda": {"value": 1.75, "status": "available", "decimal_places": 4}, "kill_participation": {"value": 0.6364, "status": "available", "decimal_places": 4}}. Weighted sum=0.5; base=50; credit(full)=0; index=50. При недостающих осях base приведена только как промежуточная арифметика, не как разрешённая оценка.

Negative: ["relative_high:deaths_per_min"]. Positive: ["observed_contribution:healing_per_min"].

Missing metrics: ["obs_placed", "sen_placed", "observer_kills", "sentry_kills"]. Reasons: ["position_unknown", "economy_not_penalized", "kda_descriptive_only", "zero_comparison_reference:healing_per_min", "comparison_unavailable:obs_placed", "comparison_unavailable:sen_placed", "comparison_unavailable:observer_kills", "comparison_unavailable:sentry_kills", "observed_contribution:healing_per_min", "relative_high:deaths_per_min"].

### Shadow Fiend, slot 1

Role evidence: `{"position": null, "evidence": "unknown", "source_field": null}`; peer slots `[0, 2, 3, 4]`; weights `{"survival": 0.5, "participation": 0.5}`.

| Raw field | Raw value | Normalized field/value |
|---|---|---|
| kills | 11 | kills=11 |
| deaths | 3 | deaths=3 |
| assists | 13 | assists=13 |
| hero_damage | 49964 | hero_damage=49964 |
| tower_damage | 6466 | tower_damage=6466 |
| hero_healing | 0 | hero_healing=0 |
| gold_per_min | 665 | gpm=665 |
| xp_per_min | 967 | xpm=967 |
| obs_placed | <absent> | obs_placed=null |
| sen_placed | <absent> | sen_placed=null |
| observer_kills | <absent> | observer_kills=null |
| sentry_kills | <absent> | sentry_kills=null |
| stuns | <absent> | stun_duration_seconds=null |
| leaver_status | 0 | leaver_status=NOT_MAPPED |
| position_est | <absent> | performance_position={"position": null, "evidence": "unknown", "source_field": null} |
| Metric | Observed | Peer slot:value | Median | Floor | Bad | Good | Использование |
|---|---|---|---|---|---|---|---|
| deaths_per_min | 0.04138882502 | {"0": 0.22074040009197515, "2": 0.05518510002299379, "3": 0.11037020004598758, "4": 0.15175902506323294} | 0.1310646126 | 0.01379627501 | 0 | 0.6842105263 | survival |
| kill_participation | 0.5454545455 | {"0": 0.6363636363636364, "2": 0.5909090909090909, "3": 0.6818181818181818, "4": 0.6818181818181818} | 0.6590909091 | 0.02272727273 | 0.1724137931 | 0 | participation |
| gpm | 665 | {"0": 429.0, "2": 769.0, "3": 692.0, "4": 398.0} | 560.5 | 1 | 0 | 0.186440678 | descriptive only; no compare in evaluator |
| xpm | 967 | {"0": 729.0, "2": 1018.0, "3": 901.0, "4": 730.0} | 815.5 | 1 | 0 | 0.1857755978 | descriptive only; no compare in evaluator |
| hero_damage_per_min | 689.3170844 | {"0": 472.867325822028, "2": 908.1535985283973, "3": 798.6249712577604, "4": 594.8815819728674} | 696.7532766 | 0.01379627501 | 0.01067263331 | 0 | positive credit only |
| tower_damage_per_min | 89.20671419 | {"0": 25.854219360772593, "2": 154.84939066452057, "3": 27.854679236606117, "4": 17.121177282133825} | 26.8544493 | 0.01379627501 | 0 | 1 | positive credit only |
| healing_per_min | 0 | {"0": 21.108300758795124, "2": 0.0, "3": 0.0, "4": 11.312945504713728} | 5.656472752 | 0.01379627501 | 1 | 0 | positive credit only |
| obs_placed | null | {} | null | 1 | null | null | positive credit only |
| sen_placed | null | {} | null | 1 | null | null | positive credit only |
| observer_kills | null | {} | null | 1 | null | null | positive credit only |
| sentry_kills | null | {} | null | 1 | null | null | positive credit only |

KDA observed=8; normalized derived={"player_slot": 1, "kda": {"value": 8.0, "status": "available", "decimal_places": 4}, "kill_participation": {"value": 0.5455, "status": "available", "decimal_places": 4}}. Weighted sum=0.08620689655; base=8.620689655; credit(full)=15; index=0. При недостающих осях base приведена только как промежуточная арифметика, не как разрешённая оценка.

Negative: []. Positive: ["positive:deaths_per_min", "positive:tower_damage_per_min"].

Missing metrics: ["obs_placed", "sen_placed", "observer_kills", "sentry_kills"]. Reasons: ["position_unknown", "economy_not_penalized", "kda_descriptive_only", "comparison_unavailable:obs_placed", "comparison_unavailable:sen_placed", "comparison_unavailable:observer_kills", "comparison_unavailable:sentry_kills", "positive:deaths_per_min", "positive:tower_damage_per_min"].

### Anti-Mage, slot 2

Role evidence: `{"position": null, "evidence": "unknown", "source_field": null}`; peer slots `[0, 1, 3, 4]`; weights `{"survival": 0.5, "participation": 0.5}`.

| Raw field | Raw value | Normalized field/value |
|---|---|---|
| kills | 13 | kills=13 |
| deaths | 4 | deaths=4 |
| assists | 13 | assists=13 |
| hero_damage | 65826 | hero_damage=65826 |
| tower_damage | 11224 | tower_damage=11224 |
| hero_healing | 0 | hero_healing=0 |
| gold_per_min | 769 | gpm=769 |
| xp_per_min | 1018 | xpm=1018 |
| obs_placed | <absent> | obs_placed=null |
| sen_placed | <absent> | sen_placed=null |
| observer_kills | <absent> | observer_kills=null |
| sentry_kills | <absent> | sentry_kills=null |
| stuns | <absent> | stun_duration_seconds=null |
| leaver_status | 0 | leaver_status=NOT_MAPPED |
| position_est | <absent> | performance_position={"position": null, "evidence": "unknown", "source_field": null} |
| Metric | Observed | Peer slot:value | Median | Floor | Bad | Good | Использование |
|---|---|---|---|---|---|---|---|
| deaths_per_min | 0.05518510002 | {"0": 0.22074040009197515, "1": 0.04138882501724534, "3": 0.11037020004598758, "4": 0.15175902506323294} | 0.1310646126 | 0.01379627501 | 0 | 0.5789473684 | survival |
| kill_participation | 0.5909090909 | {"0": 0.6363636363636364, "1": 0.5454545454545454, "3": 0.6818181818181818, "4": 0.6818181818181818} | 0.6590909091 | 0.02272727273 | 0.1034482759 | 0 | participation |
| gpm | 769 | {"0": 429.0, "1": 665.0, "3": 692.0, "4": 398.0} | 547 | 1 | 0 | 0.4058500914 | descriptive only; no compare in evaluator |
| xpm | 1018 | {"0": 729.0, "1": 967.0, "3": 901.0, "4": 730.0} | 815.5 | 1 | 0 | 0.2483139178 | descriptive only; no compare in evaluator |
| hero_damage_per_min | 908.1535985 | {"0": 472.867325822028, "1": 689.3170843872155, "3": 798.6249712577604, "4": 594.8815819728674} | 642.0993332 | 0.01379627501 | 0 | 0.4143506333 | positive credit only |
| tower_damage_per_min | 154.8493907 | {"0": 25.854219360772593, "1": 89.20671418716947, "3": 27.854679236606117, "4": 17.121177282133825} | 26.8544493 | 0.01379627501 | 0 | 1 | positive credit only |
| healing_per_min | 0 | {"0": 21.108300758795124, "1": 0.0, "3": 0.0, "4": 11.312945504713728} | 5.656472752 | 0.01379627501 | 1 | 0 | positive credit only |
| obs_placed | null | {} | null | 1 | null | null | positive credit only |
| sen_placed | null | {} | null | 1 | null | null | positive credit only |
| observer_kills | null | {} | null | 1 | null | null | positive credit only |
| sentry_kills | null | {} | null | 1 | null | null | positive credit only |

KDA observed=6.5; normalized derived={"player_slot": 2, "kda": {"value": 6.5, "status": "available", "decimal_places": 4}, "kill_participation": {"value": 0.5909, "status": "available", "decimal_places": 4}}. Weighted sum=0.05172413793; base=5.172413793; credit(full)=15; index=0. При недостающих осях base приведена только как промежуточная арифметика, не как разрешённая оценка.

Negative: []. Positive: ["positive:deaths_per_min", "positive:hero_damage_per_min", "positive:tower_damage_per_min"].

Missing metrics: ["obs_placed", "sen_placed", "observer_kills", "sentry_kills"]. Reasons: ["position_unknown", "economy_not_penalized", "kda_descriptive_only", "comparison_unavailable:obs_placed", "comparison_unavailable:sen_placed", "comparison_unavailable:observer_kills", "comparison_unavailable:sentry_kills", "positive:deaths_per_min", "positive:hero_damage_per_min", "positive:tower_damage_per_min"].

### Tidehunter, slot 3

Role evidence: `{"position": null, "evidence": "unknown", "source_field": null}`; peer slots `[0, 1, 2, 4]`; weights `{"survival": 0.5, "participation": 0.5}`.

| Raw field | Raw value | Normalized field/value |
|---|---|---|
| kills | 10 | kills=10 |
| deaths | 8 | deaths=8 |
| assists | 20 | assists=20 |
| hero_damage | 57887 | hero_damage=57887 |
| tower_damage | 2019 | tower_damage=2019 |
| hero_healing | 0 | hero_healing=0 |
| gold_per_min | 692 | gpm=692 |
| xp_per_min | 901 | xpm=901 |
| obs_placed | <absent> | obs_placed=null |
| sen_placed | <absent> | sen_placed=null |
| observer_kills | <absent> | observer_kills=null |
| sentry_kills | <absent> | sentry_kills=null |
| stuns | <absent> | stun_duration_seconds=null |
| leaver_status | 0 | leaver_status=NOT_MAPPED |
| position_est | <absent> | performance_position={"position": null, "evidence": "unknown", "source_field": null} |
| Metric | Observed | Peer slot:value | Median | Floor | Bad | Good | Использование |
|---|---|---|---|---|---|---|---|
| deaths_per_min | 0.1103702 | {"0": 0.22074040009197515, "1": 0.04138882501724534, "2": 0.05518510002299379, "4": 0.15175902506323294} | 0.1034720625 | 0.01379627501 | 0.06666666667 | 0 | survival |
| kill_participation | 0.6818181818 | {"0": 0.6363636363636364, "1": 0.5454545454545454, "2": 0.5909090909090909, "4": 0.6818181818181818} | 0.6136363636 | 0.02272727273 | 0 | 0.1111111111 | participation |
| gpm | 692 | {"0": 429.0, "1": 665.0, "2": 769.0, "4": 398.0} | 547 | 1 | 0 | 0.2650822669 | descriptive only; no compare in evaluator |
| xpm | 901 | {"0": 729.0, "1": 967.0, "2": 1018.0, "4": 730.0} | 848.5 | 1 | 0 | 0.06187389511 | descriptive only; no compare in evaluator |
| hero_damage_per_min | 798.6249713 | {"0": 472.867325822028, "1": 689.3170843872155, "2": 908.1535985283973, "4": 594.8815819728674} | 642.0993332 | 0.01379627501 | 0 | 0.2437716876 | positive credit only |
| tower_damage_per_min | 27.85467924 | {"0": 25.854219360772593, "1": 89.20671418716947, "2": 154.84939066452057, "4": 17.121177282133825} | 57.53046677 | 0.01379627501 | 0.5158273381 | 0 | positive credit only |
| healing_per_min | 0 | {"0": 21.108300758795124, "1": 0.0, "2": 0.0, "4": 11.312945504713728} | 5.656472752 | 0.01379627501 | 1 | 0 | positive credit only |
| obs_placed | null | {} | null | 1 | null | null | positive credit only |
| sen_placed | null | {} | null | 1 | null | null | positive credit only |
| observer_kills | null | {} | null | 1 | null | null | positive credit only |
| sentry_kills | null | {} | null | 1 | null | null | positive credit only |

KDA observed=3.75; normalized derived={"player_slot": 3, "kda": {"value": 3.75, "status": "available", "decimal_places": 4}, "kill_participation": {"value": 0.6818, "status": "available", "decimal_places": 4}}. Weighted sum=0.03333333333; base=3.333333333; credit(full)=3.656575315; index=0. При недостающих осях base приведена только как промежуточная арифметика, не как разрешённая оценка.

Negative: []. Positive: ["positive:hero_damage_per_min"].

Missing metrics: ["obs_placed", "sen_placed", "observer_kills", "sentry_kills"]. Reasons: ["position_unknown", "economy_not_penalized", "kda_descriptive_only", "comparison_unavailable:obs_placed", "comparison_unavailable:sen_placed", "comparison_unavailable:observer_kills", "comparison_unavailable:sentry_kills", "positive:hero_damage_per_min"].

### Mirana, slot 4

Role evidence: `{"position": null, "evidence": "unknown", "source_field": null}`; peer slots `[0, 1, 2, 3]`; weights `{"survival": 0.5, "participation": 0.5}`.

| Raw field | Raw value | Normalized field/value |
|---|---|---|
| kills | 7 | kills=7 |
| deaths | 11 | deaths=11 |
| assists | 23 | assists=23 |
| hero_damage | 43119 | hero_damage=43119 |
| tower_damage | 1241 | tower_damage=1241 |
| hero_healing | 820 | hero_healing=820 |
| gold_per_min | 398 | gpm=398 |
| xp_per_min | 730 | xpm=730 |
| obs_placed | <absent> | obs_placed=null |
| sen_placed | <absent> | sen_placed=null |
| observer_kills | <absent> | observer_kills=null |
| sentry_kills | <absent> | sentry_kills=null |
| stuns | <absent> | stun_duration_seconds=null |
| leaver_status | 0 | leaver_status=NOT_MAPPED |
| position_est | <absent> | performance_position={"position": null, "evidence": "unknown", "source_field": null} |
| Metric | Observed | Peer slot:value | Median | Floor | Bad | Good | Использование |
|---|---|---|---|---|---|---|---|
| deaths_per_min | 0.1517590251 | {"0": 0.22074040009197515, "1": 0.04138882501724534, "2": 0.05518510002299379, "3": 0.11037020004598758} | 0.08277765003 | 0.01379627501 | 0.8333333333 | 0 | survival |
| kill_participation | 0.6818181818 | {"0": 0.6363636363636364, "1": 0.5454545454545454, "2": 0.5909090909090909, "3": 0.6818181818181818} | 0.6136363636 | 0.02272727273 | 0 | 0.1111111111 | participation |
| gpm | 398 | {"0": 429.0, "1": 665.0, "2": 769.0, "3": 692.0} | 678.5 | 1 | 0.4134119381 | 0 | descriptive only; no compare in evaluator |
| xpm | 730 | {"0": 729.0, "1": 967.0, "2": 1018.0, "3": 901.0} | 934 | 1 | 0.2184154176 | 0 | descriptive only; no compare in evaluator |
| hero_damage_per_min | 594.881582 | {"0": 472.867325822028, "1": 689.3170843872155, "2": 908.1535985283973, "3": 798.6249712577604} | 743.9710278 | 0.01379627501 | 0.2003968438 | 0 | positive credit only |
| tower_damage_per_min | 17.12117728 | {"0": 25.854219360772593, "1": 89.20671418716947, "2": 154.84939066452057, "3": 27.854679236606117} | 58.53069671 | 0.01379627501 | 0.7074837949 | 0 | positive credit only |
| healing_per_min | 11.3129455 | {"0": 21.108300758795124, "1": 0.0, "2": 0.0, "3": 0.0} | 0 | 0.01379627501 | null | null | positive credit only |
| obs_placed | null | {} | null | 1 | null | null | positive credit only |
| sen_placed | null | {} | null | 1 | null | null | positive credit only |
| observer_kills | null | {} | null | 1 | null | null | positive credit only |
| sentry_kills | null | {} | null | 1 | null | null | positive credit only |

KDA observed=2.727272727; normalized derived={"player_slot": 4, "kda": {"value": 2.7273, "status": "available", "decimal_places": 4}, "kill_participation": {"value": 0.6818, "status": "available", "decimal_places": 4}}. Weighted sum=0.4166666667; base=41.66666667; credit(full)=0; index=42. При недостающих осях base приведена только как промежуточная арифметика, не как разрешённая оценка.

Negative: ["relative_high:deaths_per_min"]. Positive: ["observed_contribution:healing_per_min"].

Missing metrics: ["obs_placed", "sen_placed", "observer_kills", "sentry_kills"]. Reasons: ["position_unknown", "economy_not_penalized", "kda_descriptive_only", "zero_comparison_reference:healing_per_min", "comparison_unavailable:obs_placed", "comparison_unavailable:sen_placed", "comparison_unavailable:observer_kills", "comparison_unavailable:sentry_kills", "observed_contribution:healing_per_min", "relative_high:deaths_per_min"].

### Centaur Warrunner, slot 128

Role evidence: `{"position": null, "evidence": "unknown", "source_field": null}`; peer slots `[129, 130, 131, 132]`; weights `{"survival": 0.5, "participation": 0.5}`.

| Raw field | Raw value | Normalized field/value |
|---|---|---|
| kills | 5 | kills=5 |
| deaths | 8 | deaths=8 |
| assists | 27 | assists=27 |
| hero_damage | 72459 | hero_damage=72459 |
| tower_damage | 5499 | tower_damage=5499 |
| hero_healing | 0 | hero_healing=0 |
| gold_per_min | 685 | gpm=685 |
| xp_per_min | 948 | xpm=948 |
| obs_placed | <absent> | obs_placed=null |
| sen_placed | <absent> | sen_placed=null |
| observer_kills | <absent> | observer_kills=null |
| sentry_kills | <absent> | sentry_kills=null |
| stuns | <absent> | stun_duration_seconds=null |
| leaver_status | 0 | leaver_status=NOT_MAPPED |
| position_est | <absent> | performance_position={"position": null, "evidence": "unknown", "source_field": null} |
| Metric | Observed | Peer slot:value | Median | Floor | Bad | Good | Использование |
|---|---|---|---|---|---|---|---|
| deaths_per_min | 0.1103702 | {"129": 0.11037020004598758, "130": 0.08277765003449068, "131": 0.17935157507472982, "132": 0.12416647505173603} | 0.1172683375 | 0.01379627501 | 0 | 0.05882352941 | survival |
| kill_participation | 0.7619047619 | {"129": 0.5238095238095238, "130": 0.5476190476190477, "131": 0.6904761904761905, "132": 0.6190476190476191} | 0.5833333333 | 0.02380952381 | 0 | 0.306122449 | participation |
| gpm | 685 | {"129": 559.0, "130": 637.0, "131": 346.0, "132": 350.0} | 454.5 | 1 | 0 | 0.5071507151 | descriptive only; no compare in evaluator |
| xpm | 948 | {"129": 741.0, "130": 840.0, "131": 709.0, "132": 610.0} | 725 | 1 | 0 | 0.3075862069 | descriptive only; no compare in evaluator |
| hero_damage_per_min | 999.6642906 | {"129": 480.9243504253851, "130": 707.8730742699471, "131": 375.6725684065302, "132": 319.4389514830996} | 428.2984594 | 0.01379627501 | 0 | 1 | positive credit only |
| tower_damage_per_min | 75.86571626 | {"129": 43.527247643136356, "130": 42.40974936767073, "131": 2.0142561508392736, "132": 0.4414808001839503} | 22.21200276 | 0.01379627501 | 0 | 1 | positive credit only |
| healing_per_min | 0 | {"129": 0.0, "130": 0.0, "131": 0.0, "132": 12.416647505173604} | 0 | 0.01379627501 | null | null | positive credit only |
| obs_placed | null | {} | null | 1 | null | null | positive credit only |
| sen_placed | null | {} | null | 1 | null | null | positive credit only |
| observer_kills | null | {} | null | 1 | null | null | positive credit only |
| sentry_kills | null | {} | null | 1 | null | null | positive credit only |

KDA observed=4; normalized derived={"player_slot": 128, "kda": {"value": 4.0, "status": "available", "decimal_places": 4}, "kill_participation": {"value": 0.7619, "status": "available", "decimal_places": 4}}. Weighted sum=0; base=0; credit(full)=15; index=0. При недостающих осях base приведена только как промежуточная арифметика, не как разрешённая оценка.

Negative: []. Positive: ["positive:kill_participation", "positive:hero_damage_per_min", "positive:tower_damage_per_min"].

Missing metrics: ["obs_placed", "sen_placed", "observer_kills", "sentry_kills"]. Reasons: ["position_unknown", "economy_not_penalized", "kda_descriptive_only", "zero_comparison_reference:healing_per_min", "comparison_unavailable:obs_placed", "comparison_unavailable:sen_placed", "comparison_unavailable:observer_kills", "comparison_unavailable:sentry_kills", "positive:kill_participation", "positive:hero_damage_per_min", "positive:tower_damage_per_min"].

### Sven, slot 129

Role evidence: `{"position": null, "evidence": "unknown", "source_field": null}`; peer slots `[128, 130, 131, 132]`; weights `{"survival": 0.5, "participation": 0.5}`.

| Raw field | Raw value | Normalized field/value |
|---|---|---|
| kills | 9 | kills=9 |
| deaths | 8 | deaths=8 |
| assists | 13 | assists=13 |
| hero_damage | 34859 | hero_damage=34859 |
| tower_damage | 3155 | tower_damage=3155 |
| hero_healing | 0 | hero_healing=0 |
| gold_per_min | 559 | gpm=559 |
| xp_per_min | 741 | xpm=741 |
| obs_placed | <absent> | obs_placed=null |
| sen_placed | <absent> | sen_placed=null |
| observer_kills | <absent> | observer_kills=null |
| sentry_kills | <absent> | sentry_kills=null |
| stuns | <absent> | stun_duration_seconds=null |
| leaver_status | 0 | leaver_status=NOT_MAPPED |
| position_est | <absent> | performance_position={"position": null, "evidence": "unknown", "source_field": null} |
| Metric | Observed | Peer slot:value | Median | Floor | Bad | Good | Использование |
|---|---|---|---|---|---|---|---|
| deaths_per_min | 0.1103702 | {"128": 0.11037020004598758, "130": 0.08277765003449068, "131": 0.17935157507472982, "132": 0.12416647505173603} | 0.1172683375 | 0.01379627501 | 0 | 0.05882352941 | survival |
| kill_participation | 0.5238095238 | {"128": 0.7619047619047619, "130": 0.5476190476190477, "131": 0.6904761904761905, "132": 0.6190476190476191} | 0.6547619048 | 0.02380952381 | 0.2 | 0 | participation |
| gpm | 559 | {"128": 685.0, "130": 637.0, "131": 346.0, "132": 350.0} | 493.5 | 1 | 0 | 0.1327254306 | descriptive only; no compare in evaluator |
| xpm | 741 | {"128": 948.0, "130": 840.0, "131": 709.0, "132": 610.0} | 774.5 | 1 | 0.04325371207 | 0 | descriptive only; no compare in evaluator |
| hero_damage_per_min | 480.9243504 | {"128": 999.6642906415268, "130": 707.8730742699471, "131": 375.6725684065302, "132": 319.4389514830996} | 541.7728213 | 0.01379627501 | 0.1123136276 | 0 | positive credit only |
| tower_damage_per_min | 43.52724764 | {"128": 75.86571625661071, "130": 42.40974936767073, "131": 2.0142561508392736, "132": 0.4414808001839503} | 22.21200276 | 0.01379627501 | 0 | 0.9596273292 | positive credit only |
| healing_per_min | 0 | {"128": 0.0, "130": 0.0, "131": 0.0, "132": 12.416647505173604} | 0 | 0.01379627501 | null | null | positive credit only |
| obs_placed | null | {} | null | 1 | null | null | positive credit only |
| sen_placed | null | {} | null | 1 | null | null | positive credit only |
| observer_kills | null | {} | null | 1 | null | null | positive credit only |
| sentry_kills | null | {} | null | 1 | null | null | positive credit only |

KDA observed=2.75; normalized derived={"player_slot": 129, "kda": {"value": 2.75, "status": "available", "decimal_places": 4}, "kill_participation": {"value": 0.5238, "status": "available", "decimal_places": 4}}. Weighted sum=0.1; base=10; credit(full)=14.39440994; index=0. При недостающих осях base приведена только как промежуточная арифметика, не как разрешённая оценка.

Negative: []. Positive: ["positive:tower_damage_per_min"].

Missing metrics: ["obs_placed", "sen_placed", "observer_kills", "sentry_kills"]. Reasons: ["position_unknown", "economy_not_penalized", "kda_descriptive_only", "zero_comparison_reference:healing_per_min", "comparison_unavailable:obs_placed", "comparison_unavailable:sen_placed", "comparison_unavailable:observer_kills", "comparison_unavailable:sentry_kills", "positive:tower_damage_per_min"].

### Invoker, slot 130

Role evidence: `{"position": null, "evidence": "unknown", "source_field": null}`; peer slots `[128, 129, 131, 132]`; weights `{"survival": 0.5, "participation": 0.5}`.

| Raw field | Raw value | Normalized field/value |
|---|---|---|
| kills | 7 | kills=7 |
| deaths | 6 | deaths=6 |
| assists | 16 | assists=16 |
| hero_damage | 51309 | hero_damage=51309 |
| tower_damage | 3074 | tower_damage=3074 |
| hero_healing | 0 | hero_healing=0 |
| gold_per_min | 637 | gpm=637 |
| xp_per_min | 840 | xpm=840 |
| obs_placed | <absent> | obs_placed=null |
| sen_placed | <absent> | sen_placed=null |
| observer_kills | <absent> | observer_kills=null |
| sentry_kills | <absent> | sentry_kills=null |
| stuns | <absent> | stun_duration_seconds=null |
| leaver_status | 0 | leaver_status=NOT_MAPPED |
| position_est | <absent> | performance_position={"position": null, "evidence": "unknown", "source_field": null} |
| Metric | Observed | Peer slot:value | Median | Floor | Bad | Good | Использование |
|---|---|---|---|---|---|---|---|
| deaths_per_min | 0.08277765003 | {"128": 0.11037020004598758, "129": 0.11037020004598758, "131": 0.17935157507472982, "132": 0.12416647505173603} | 0.1172683375 | 0.01379627501 | 0 | 0.2941176471 | survival |
| kill_participation | 0.5476190476 | {"128": 0.7619047619047619, "129": 0.5238095238095238, "131": 0.6904761904761905, "132": 0.6190476190476191} | 0.6547619048 | 0.02380952381 | 0.1636363636 | 0 | participation |
| gpm | 637 | {"128": 685.0, "129": 559.0, "131": 346.0, "132": 350.0} | 454.5 | 1 | 0 | 0.401540154 | descriptive only; no compare in evaluator |
| xpm | 840 | {"128": 948.0, "129": 741.0, "131": 709.0, "132": 610.0} | 725 | 1 | 0 | 0.1586206897 | descriptive only; no compare in evaluator |
| hero_damage_per_min | 707.8730743 | {"128": 999.6642906415268, "129": 480.9243504253851, "131": 375.6725684065302, "132": 319.4389514830996} | 428.2984594 | 0.01379627501 | 0 | 0.6527565269 | positive credit only |
| tower_damage_per_min | 42.40974937 | {"128": 75.86571625661071, "129": 43.527247643136356, "131": 2.0142561508392736, "132": 0.4414808001839503} | 22.7707519 | 0.01379627501 | 0 | 0.8624659194 | positive credit only |
| healing_per_min | 0 | {"128": 0.0, "129": 0.0, "131": 0.0, "132": 12.416647505173604} | 0 | 0.01379627501 | null | null | positive credit only |
| obs_placed | null | {} | null | 1 | null | null | positive credit only |
| sen_placed | null | {} | null | 1 | null | null | positive credit only |
| observer_kills | null | {} | null | 1 | null | null | positive credit only |
| sentry_kills | null | {} | null | 1 | null | null | positive credit only |

KDA observed=3.833333333; normalized derived={"player_slot": 130, "kda": {"value": 3.8333, "status": "available", "decimal_places": 4}, "kill_participation": {"value": 0.5476, "status": "available", "decimal_places": 4}}. Weighted sum=0.08181818182; base=8.181818182; credit(full)=12.93698879; index=0. При недостающих осях base приведена только как промежуточная арифметика, не как разрешённая оценка.

Negative: []. Positive: ["positive:deaths_per_min", "positive:hero_damage_per_min", "positive:tower_damage_per_min"].

Missing metrics: ["obs_placed", "sen_placed", "observer_kills", "sentry_kills"]. Reasons: ["position_unknown", "economy_not_penalized", "kda_descriptive_only", "zero_comparison_reference:healing_per_min", "comparison_unavailable:obs_placed", "comparison_unavailable:sen_placed", "comparison_unavailable:observer_kills", "comparison_unavailable:sentry_kills", "positive:deaths_per_min", "positive:hero_damage_per_min", "positive:tower_damage_per_min"].

### Pudge, slot 131

Role evidence: `{"position": null, "evidence": "unknown", "source_field": null}`; peer slots `[128, 129, 130, 132]`; weights `{"survival": 0.5, "participation": 0.5}`.

| Raw field | Raw value | Normalized field/value |
|---|---|---|
| kills | 7 | kills=7 |
| deaths | 13 | deaths=13 |
| assists | 22 | assists=22 |
| hero_damage | 27230 | hero_damage=27230 |
| tower_damage | 146 | tower_damage=146 |
| hero_healing | 0 | hero_healing=0 |
| gold_per_min | 346 | gpm=346 |
| xp_per_min | 709 | xpm=709 |
| obs_placed | <absent> | obs_placed=null |
| sen_placed | <absent> | sen_placed=null |
| observer_kills | <absent> | observer_kills=null |
| sentry_kills | <absent> | sentry_kills=null |
| stuns | <absent> | stun_duration_seconds=null |
| leaver_status | 0 | leaver_status=NOT_MAPPED |
| position_est | <absent> | performance_position={"position": null, "evidence": "unknown", "source_field": null} |
| Metric | Observed | Peer slot:value | Median | Floor | Bad | Good | Использование |
|---|---|---|---|---|---|---|---|
| deaths_per_min | 0.1793515751 | {"128": 0.11037020004598758, "129": 0.11037020004598758, "130": 0.08277765003449068, "132": 0.12416647505173603} | 0.1103702 | 0.01379627501 | 0.625 | 0 | survival |
| kill_participation | 0.6904761905 | {"128": 0.7619047619047619, "129": 0.5238095238095238, "130": 0.5476190476190477, "132": 0.6190476190476191} | 0.5833333333 | 0.02380952381 | 0 | 0.1836734694 | participation |
| gpm | 346 | {"128": 685.0, "129": 559.0, "130": 637.0, "132": 350.0} | 598 | 1 | 0.4214046823 | 0 | descriptive only; no compare in evaluator |
| xpm | 709 | {"128": 948.0, "129": 741.0, "130": 840.0, "132": 610.0} | 790.5 | 1 | 0.1030993042 | 0 | descriptive only; no compare in evaluator |
| hero_damage_per_min | 375.6725684 | {"128": 999.6642906415268, "129": 480.9243504253851, "130": 707.8730742699471, "132": 319.4389514830996} | 594.3987123 | 0.01379627501 | 0.367978832 | 0 | positive credit only |
| tower_damage_per_min | 2.014256151 | {"128": 75.86571625661071, "129": 43.527247643136356, "130": 42.40974936767073, "132": 0.4414808001839503} | 42.96849851 | 0.01379627501 | 0.9531224916 | 0 | positive credit only |
| healing_per_min | 0 | {"128": 0.0, "129": 0.0, "130": 0.0, "132": 12.416647505173604} | 0 | 0.01379627501 | null | null | positive credit only |
| obs_placed | null | {} | null | 1 | null | null | positive credit only |
| sen_placed | null | {} | null | 1 | null | null | positive credit only |
| observer_kills | null | {} | null | 1 | null | null | positive credit only |
| sentry_kills | null | {} | null | 1 | null | null | positive credit only |

KDA observed=2.230769231; normalized derived={"player_slot": 131, "kda": {"value": 2.2308, "status": "available", "decimal_places": 4}, "kill_participation": {"value": 0.6905, "status": "available", "decimal_places": 4}}. Weighted sum=0.3125; base=31.25; credit(full)=0; index=31. При недостающих осях base приведена только как промежуточная арифметика, не как разрешённая оценка.

Negative: ["relative_high:deaths_per_min"]. Positive: [].

Missing metrics: ["obs_placed", "sen_placed", "observer_kills", "sentry_kills"]. Reasons: ["position_unknown", "economy_not_penalized", "kda_descriptive_only", "zero_comparison_reference:healing_per_min", "comparison_unavailable:obs_placed", "comparison_unavailable:sen_placed", "comparison_unavailable:observer_kills", "comparison_unavailable:sentry_kills", "relative_high:deaths_per_min"].

### Lion, slot 132

Role evidence: `{"position": null, "evidence": "unknown", "source_field": null}`; peer slots `[128, 129, 130, 131]`; weights `{"survival": 0.5, "participation": 0.5}`.

| Raw field | Raw value | Normalized field/value |
|---|---|---|
| kills | 12 | kills=12 |
| deaths | 9 | deaths=9 |
| assists | 14 | assists=14 |
| hero_damage | 23154 | hero_damage=23154 |
| tower_damage | 32 | tower_damage=32 |
| hero_healing | 900 | hero_healing=900 |
| gold_per_min | 350 | gpm=350 |
| xp_per_min | 610 | xpm=610 |
| obs_placed | <absent> | obs_placed=null |
| sen_placed | <absent> | sen_placed=null |
| observer_kills | <absent> | observer_kills=null |
| sentry_kills | <absent> | sentry_kills=null |
| stuns | <absent> | stun_duration_seconds=null |
| leaver_status | 0 | leaver_status=NOT_MAPPED |
| position_est | <absent> | performance_position={"position": null, "evidence": "unknown", "source_field": null} |
| Metric | Observed | Peer slot:value | Median | Floor | Bad | Good | Использование |
|---|---|---|---|---|---|---|---|
| deaths_per_min | 0.1241664751 | {"128": 0.11037020004598758, "129": 0.11037020004598758, "130": 0.08277765003449068, "131": 0.17935157507472982} | 0.1103702 | 0.01379627501 | 0.125 | 0 | survival |
| kill_participation | 0.619047619 | {"128": 0.7619047619047619, "129": 0.5238095238095238, "130": 0.5476190476190477, "131": 0.6904761904761905} | 0.619047619 | 0.02380952381 | 0 | 0 | participation |
| gpm | 350 | {"128": 685.0, "129": 559.0, "130": 637.0, "131": 346.0} | 598 | 1 | 0.4147157191 | 0 | descriptive only; no compare in evaluator |
| xpm | 610 | {"128": 948.0, "129": 741.0, "130": 840.0, "131": 709.0} | 790.5 | 1 | 0.2283364959 | 0 | descriptive only; no compare in evaluator |
| hero_damage_per_min | 319.4389515 | {"128": 999.6642906415268, "129": 480.9243504253851, "130": 707.8730742699471, "131": 375.6725684065302} | 594.3987123 | 0.01379627501 | 0.4625847182 | 0 | positive credit only |
| tower_damage_per_min | 0.4414808002 | {"128": 75.86571625661071, "129": 43.527247643136356, "130": 42.40974936767073, "131": 2.0142561508392736} | 42.96849851 | 0.01379627501 | 0.9897254776 | 0 | positive credit only |
| healing_per_min | 12.41664751 | {"128": 0.0, "129": 0.0, "130": 0.0, "131": 0.0} | 0 | 0.01379627501 | null | null | positive credit only |
| obs_placed | null | {} | null | 1 | null | null | positive credit only |
| sen_placed | null | {} | null | 1 | null | null | positive credit only |
| observer_kills | null | {} | null | 1 | null | null | positive credit only |
| sentry_kills | null | {} | null | 1 | null | null | positive credit only |

KDA observed=2.888888889; normalized derived={"player_slot": 132, "kda": {"value": 2.8889, "status": "available", "decimal_places": 4}, "kill_participation": {"value": 0.619, "status": "available", "decimal_places": 4}}. Weighted sum=0.0625; base=6.25; credit(full)=0; index=6. При недостающих осях base приведена только как промежуточная арифметика, не как разрешённая оценка.

Negative: []. Positive: ["observed_contribution:healing_per_min"].

Missing metrics: ["obs_placed", "sen_placed", "observer_kills", "sentry_kills"]. Reasons: ["position_unknown", "economy_not_penalized", "kda_descriptive_only", "zero_comparison_reference:healing_per_min", "comparison_unavailable:obs_placed", "comparison_unavailable:sen_placed", "comparison_unavailable:observer_kills", "comparison_unavailable:sentry_kills", "observed_contribution:healing_per_min"].

### Командный выбор

| Team | scored | strict | preliminary |
|---|---|---|---|
| radiant | 5 | {"selected_player_slot": null, "selected_team": null, "selection_status": "no_confident_selection", "evidence": ["incomplete_or_low_confidence_team"]} | {"projection_version": "ri_preliminary_v1", "minimum_margin": 15, "status": "group", "player_slots": [0, 4], "leader_slot": null, "highest_index": 50, "margin": 8, "confidence": "low", "reason_codes": ["close_scores", "roles_unknown", "leaver_context_unknown"]} |
| dire | 5 | {"selected_player_slot": null, "selected_team": null, "selection_status": "no_confident_selection", "evidence": ["incomplete_or_low_confidence_team"]} | {"projection_version": "ri_preliminary_v1", "minimum_margin": 15, "status": "single", "player_slots": [131], "leader_slot": 131, "highest_index": 31, "margin": 25, "confidence": "low", "reason_codes": ["highest_relative_index", "roles_unknown", "leaver_context_unknown"]} |

## Три ключевых случая

**Oracle:** raw 1/8/11, score10, duration1933, raw teamfight_participation=1.2. Normalized KDA=1.5, counter ratio=1.2 AVAILABLE. Current observed usable=null, diagnostic counter ratio=1.2, exact reason over_team_score_unverified. Survival0, participation null; coverage.5 и одна ось, поэтому index null независимо от credit15. Сохранённый REST пока не имеет diagnostic ratio и использует прежний team_kills_missing_small_or_inconsistent. Это старый report, не потеря при нынешнем HTTP serializer. Code/config version не различают эти реализации.

**Hoodwink:** raw1/12/7 → usable KP=.8. Единственный другой support Oracle имеет KP null; доступных peers0, сравнение не проходит minimum_cohort2. DPM .372478 против .248319 → survival .5. Coverage.5, credit3.99421128799, index null. `missing_metrics=[]` говорит о наличии собственных observed inputs, а не достаточности peers/осей. Estimated position формирует support корректно, ограничивает confidence, не создаёт этот null.

**Spectre:** raw1/8/5, GPM358,XPM386,hero_damage13258,duration1933. Peers core slots2,4. KP .6 против median.65 → .0769230769231. Economy среднее((386−358)/386,(451−386)/451)=.108331514309. Impact=(14336−13258)/14336=.0751953125. Survival0. `100*(.30*0+.25*.0769230769231+.25*.108331514309+.20*.0751953125)−0=6.1352710308`, half-up → **6**. Все составляющие bad ниже .20, поэтому negative_signals=[] закономерно. Это объяснимость модели, не арифметический дефект. Low confidence при coverage1 обусловлена estimated ролями. Никаких коэффициентов для этого героя или Match ID нет.

Тот факт, что несколько союзников могут получить ассист на одно убийство, объясняет сумму ассистов команды выше score, но не доказывает превышение индивидуальной доли уникальных убийств. Parser хранит собственный игровой teamfight_participation отдельно. Без полного assist→kill события происхождение Oracle11 assists не установлено, 1.2 нельзя автоматически считать процентом или обрезать до1.

[Воспроизводимые свидетельства](qa/ri02/data01/) · [Матрица](RI_02_DATA_01_FIELD_MATRIX.csv) · [QA](RI_02_DATA_01_QA_REPORT.md)
