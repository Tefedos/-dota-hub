**RI-02-CAL-01-DATA / READY FOR QA.** Дата: 24.10.2026. HEAD `f222ee9dc322e98b8890ec642c9038244fe1e5a2`. Исследуется рабочее дерево с уже существующими незакоммиченными RI/PL/UI изменениями, а не чистый HEAD. Код, настройки, сохранённые матчи и прежние отчёты не изменены.

## Ответ на основной вопрос

**Частично.** Численные scalar inputs существующих осей на доступных snapshots корректно доходят до evaluator; произвольный «полный raw→все решения» путь не подтверждён. Найдены дефекты/риски сохранения last-good snapshot, потери leaver context, согласованности version metadata и инвалидации диагностического кэша. На реальных20 игроках current replay совпал с сохранёнными индексами, все10 local section responses совпали с сохранёнными DTO после штатной проекции. Отдельная проблема Timeline не влияет на RI. Обоснованности самих весов и причинной интерпретации индекса этот технический аудит не доказывает.

## Репозиторий и область изменений

HEAD приведён выше. Полные Git status до/после — `qa/ri02/data01/baseline.json` и `scope_verification.json`. Исходное дерево уже содержало изменения backend/api/models/normalization/performance, frontend и тестов предыдущих задач. Они сохранены. В этом задании добавлены только шесть документов ниже, evidence под `docs/qa/ri02/data01/` и три standalone audit scripts. Нет коммита, изменений production/config/API/UI/миграций/существующих fixtures. Raw и все report rows двух пилотов сравнены до/после read-only SQL: одинаковы. Проверка SHA production/frontend/существующих tests — в scope_verification.json. Тесты писали только в выделенные тестовые БД по существующим защитным fixtures.

## Полнота P0: три разных знаменателя

Матрица содержит58 различных имён P0:11 match-полей и47 player-полей. На каждый10-player snapshot приходится481 проверяемый путь (включая альтернативный is_radiant). Инвентаризация **58/58=100%**, заполнено5772 P0 строк для12 матчей. Проверяемость исходного HTTP account_id ограничена sanitizer:120 строк UNVERIFIED, остальные5652/5772=97.921% классифицированы по сохранённому источнику. Это полнота аудита, не полнота данных или доказательств модели.

| Матч | P0 paths | Non-null raw | Raw presence % | Typed mapped | Not mapped | Leaver lost to model | Missing/null source | HTTP unverified |
|---|---|---|---|---|---|---|---|---|
| 9051271323 | 481 | 451 | 93.76% | 239 | 202 | 10 | 20 | 10 |
| 9057722463 | 481 | 230 | 47.82% | 159 | 61 | 10 | 241 | 10 |

Счёт raw presence: «не-null поле / все перечисленные пути». В знаменатель намеренно входит альтернативный alias и приватный account_id, поэтому это описательная доля, не норматив готовности. Убедительно восстановить original HTTP completeness нельзя. Даже100% полей не означает минимум usable осей. Matched source_status: первый FOUND_FULL, второй FOUND_PARTIAL; summary/stats первого и второго могут быть complete при недостатке roles/timeline.

На12 матчах:1947 P0 PRESENT_CORRECT,868 NOT_MAPPED,100 LOST_IN_BACKEND (leaver по пути к решению, raw сохранён),2737 MISSING_IN_SOURCE,120 UNVERIFIED. На этом наборе нет PRESENT_INCORRECT для mapped ненулевого scalar. Полная матрица содержит13750 строк P0/P1/P2, включая вложенные draft actions. Source path и match ID находятся в source_json_path/evidence, для игрока указан player_slot. NOT_MAPPED — не автоматически дефект. Огромные logs/maps не скопированы в каждую CSV ячейку: сохранены SHA/размер/sample и ссылка на полный frozen raw.

## Потери, null и нули

- Подтверждена потеря leaver_status из typed normalization/evaluator/preliminary, при сохранении raw. Остальные unmapped P0/P1 перечислены в CSV; многие не нужны текущей формуле (teamfight_participation, stuns в RI, stacks, gold totals, ability/item logs, variant).
- K/A остаются1/11 для Oracle. **Usable** participation становится null из-за unverified превышения, исходное1.2 сохранено в current normalized/observed diagnostic; live старый report ещё без нового поля. Hoodwink собственный KP .8 известен, null появляется только в peer axis.
- Missing и явный null остаются null. Некорректный negative/bool/numeric-string/float для integer-поля отклоняется в null. В experiments GPM211.5 и строка211 не округляются; real snapshots не содержали такого валидного scalar, потерянного при маппинге.
- Неподтверждённой подстановки исходного отсутствующего показателя в0 не найдено. Индекс0 может получиться из clip(base−credit), это итог модели. Credit0 означает отсутствие пригодного положительного кредита, а не доказанный нулевой вклад игрока. Empty item0 сохраняет семантику пустого слота, не заменяет missing item.
- В9057722463 team scores44/42, сумма личных kills43/40, сумма смертей противника44/42. Эти разные счётчики сохраняются, один не подменяется другим; причина разницы не доказана этим snapshot. В9051271323 соответствующие три величины совпадают10/45. Предположение «sum(player kills) обязано равняться score» не используется для коррекции.

Производные метрики, единицы и полная формула приведены в MATCH_TRACE: DPM, HDPM, TDPM, healing/min, descriptive KDA, raw counter-ratio, usable participation, неизменные GPM/XPM, ward counters. Нормализатор round4; evaluator использует исходную float точность, signals magnitude round6/value round4, credit DTO round4, индекс half-up integer. Rates не вычисляются повторно из уже per-minute GPM/XPM.

## Реальные проверки и существующие тесты

Выполнен полный backend pytest: **408 PASS, 0 FAIL, 0 ERROR, 0 SKIP**, время 7.572s. JUnit `pytest.xml`, stdout `pytest.log`. Одно существующее StarletteDeprecationWarning об httpx/TestClient. Новые production-тесты не добавлялись. Дополнительная команда validate выполнила3864 элементарных сверки raw/scalar/rates/derived/axes/CSV/ссылок без расхождений (это не3864 новых pytest-теста); artifact_checks.json содержит счётчики. Offline evidence/дополнительные experiments находятся в самостоятельном audit script.

| Существующий файл / группа | Фактически PASS |
|---|---|
| tests/test_api.py | 7 |
| tests/test_auth_api.py | 4 |
| tests/test_bot_config.py | 11 |
| tests/test_bot_handlers.py | 16 |
| tests/test_bot_services.py | 23 |
| tests/test_database_health.py | 4 |
| tests/test_draft_alpha_bugfix.py | 5 |
| tests/test_draft_analyzer.py | 23 |
| tests/test_draft_universality.py | 10 |
| tests/test_group_flow.py | 19 |
| tests/test_local_alpha.py | 3 |
| tests/test_match_ingestion.py | 6 |
| tests/test_match_normalization.py | 15 |
| tests/test_migrations.py | 1 |
| tests/test_opendota.py | 17 |
| tests/test_opendota_matchups.py | 14 |
| tests/test_overview.py | 5 |
| tests/test_performance.py | 33 |
| tests/test_performance_integration.py | 5 |
| tests/test_performance_participation_contract.py | 14 |
| tests/test_performance_preliminary.py | 38 |
| tests/test_performance_preliminary_api.py | 2 |
| tests/test_performance_preliminary_qa.py | 26 |
| tests/test_player_catalog.py | 2 |
| tests/test_repositories.py | 21 |
| tests/test_sessions.py | 24 |
| tests/test_telegram_auth.py | 46 |
| tests/test_timeline.py | 14 |

Полный поимённый список parametrized случаев и результатов:

| Test node | Результат |
|---|---|
| tests.test_api::test_health_contract | PASS |
| tests.test_api::test_missing_endpoint | PASS |
| tests.test_api::test_method_not_allowed | PASS |
| tests.test_api::test_internal_error_does_not_expose_details | PASS |
| tests.test_api::test_validation_error_does_not_echo_input | PASS |
| tests.test_api::test_settings_can_disable_documentation | PASS |
| tests.test_api::test_no_cross_origin_access_is_enabled | PASS |
| tests.test_auth_api::test_public_health_missing_auth_and_config | PASS |
| tests.test_auth_api::test_invalid_input_never_reaches_database_or_leaks | PASS |
| tests.test_auth_api::test_cors_is_explicit | PASS |
| tests.test_auth_api::test_login_upsert_me_and_rejections | PASS |
| tests.test_bot_config::test_bot_settings_are_safe_by_default | PASS |
| tests.test_bot_config::test_bot_settings_load_exact_env_names | PASS |
| tests.test_bot_config::test_allowed_chat_ids_reject_unsafe_values[values0] | PASS |
| tests.test_bot_config::test_allowed_chat_ids_reject_unsafe_values[values1] | PASS |
| tests.test_bot_config::test_allowed_chat_ids_reject_unsafe_values[values2] | PASS |
| tests.test_bot_config::test_allowed_chat_ids_reject_unsafe_values[values3] | PASS |
| tests.test_bot_config::test_bot_username_is_validated[bad] | PASS |
| tests.test_bot_config::test_bot_username_is_validated[bad-name] | PASS |
| tests.test_bot_config::test_bot_username_is_validated[xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx] | PASS |
| tests.test_bot_config::test_bot_username_is_validated[\u044e\u0437\u0435\u0440\u0431\u043e\u0442] | PASS |
| tests.test_bot_config::test_bot_refuses_to_start_without_token | PASS |
| tests.test_bot_handlers::test_group_match_and_addressed_command_ingest_in_background | PASS |
| tests.test_bot_handlers::test_command_for_another_bot_is_ignored | PASS |
| tests.test_bot_handlers::test_invalid_match_id_has_friendly_error[/match] | PASS |
| tests.test_bot_handlers::test_invalid_match_id_has_friendly_error[/match ] | PASS |
| tests.test_bot_handlers::test_invalid_match_id_has_friendly_error[/match 0] | PASS |
| tests.test_bot_handlers::test_invalid_match_id_has_friendly_error[/match -1] | PASS |
| tests.test_bot_handlers::test_invalid_match_id_has_friendly_error[/match 123 extra] | PASS |
| tests.test_bot_handlers::test_invalid_match_id_has_friendly_error[/match https://example.org/123] | PASS |
| tests.test_bot_handlers::test_invalid_match_id_has_friendly_error[/match@FixtureBot] | PASS |
| tests.test_bot_handlers::test_invalid_match_id_has_friendly_error[/match 9223372036854775808] | PASS |
| tests.test_bot_handlers::test_invalid_match_id_has_friendly_error[/match <b>123</b>] | PASS |
| tests.test_bot_handlers::test_allowlist_is_fail_closed | PASS |
| tests.test_bot_handlers::test_cooldown_only_blocks_same_user_in_same_chat | PASS |
| tests.test_bot_handlers::test_private_chat_explains_group_usage | PASS |
| tests.test_bot_handlers::test_group_help_is_available_without_allowlist | PASS |
| tests.test_bot_handlers::test_duplicate_update_does_not_trigger_external_calls | PASS |
| tests.test_bot_services::test_match_id_accepts_canonical_positive_bigint[1] | PASS |
| tests.test_bot_services::test_match_id_accepts_canonical_positive_bigint[123456789] | PASS |
| tests.test_bot_services::test_match_id_accepts_canonical_positive_bigint[9223372036854775807] | PASS |
| tests.test_bot_services::test_match_id_rejects_ambiguous_or_unsafe_input[None] | PASS |
| tests.test_bot_services::test_match_id_rejects_ambiguous_or_unsafe_input[] | PASS |
| tests.test_bot_services::test_match_id_rejects_ambiguous_or_unsafe_input[ ] | PASS |
| tests.test_bot_services::test_match_id_rejects_ambiguous_or_unsafe_input[0] | PASS |
| tests.test_bot_services::test_match_id_rejects_ambiguous_or_unsafe_input[-1] | PASS |
| tests.test_bot_services::test_match_id_rejects_ambiguous_or_unsafe_input[+1] | PASS |
| tests.test_bot_services::test_match_id_rejects_ambiguous_or_unsafe_input[01] | PASS |
| tests.test_bot_services::test_match_id_rejects_ambiguous_or_unsafe_input[1.0] | PASS |
| tests.test_bot_services::test_match_id_rejects_ambiguous_or_unsafe_input[1e3] | PASS |
| tests.test_bot_services::test_match_id_rejects_ambiguous_or_unsafe_input[1 2] | PASS |
| tests.test_bot_services::test_match_id_rejects_ambiguous_or_unsafe_input[123\n] | PASS |
| tests.test_bot_services::test_match_id_rejects_ambiguous_or_unsafe_input[https://example.org/123] | PASS |
| tests.test_bot_services::test_match_id_rejects_ambiguous_or_unsafe_input[9223372036854775808] | PASS |
| tests.test_bot_services::test_match_id_rejects_ambiguous_or_unsafe_input[9999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999] | PASS |
| tests.test_bot_services::test_match_id_rejects_ambiguous_or_unsafe_input[\uff11\uff12\uff13] | PASS |
| tests.test_bot_services::test_match_id_rejects_ambiguous_or_unsafe_input[123_456] | PASS |
| tests.test_bot_services::test_match_id_rejects_ambiguous_or_unsafe_input[<b>123</b>] | PASS |
| tests.test_bot_services::test_main_mini_app_link_has_validated_payload | PASS |
| tests.test_bot_services::test_job_service_cooldown_is_per_chat_and_user | PASS |
| tests.test_bot_services::test_job_service_runs_ingestion_and_notifies | PASS |
| tests.test_database_health::test_liveness_without_database_and_safe_unavailable_response | PASS |
| tests.test_database_health::test_unreachable_database_does_not_break_liveness_or_leak_errors | PASS |
| tests.test_database_health::test_live_database_and_one_session_per_request | PASS |
| tests.test_database_health::test_request_failure_rolls_back_pending_writes | PASS |
| tests.test_draft_alpha_bugfix::test_real_match_has_no_team_claims_on_individual_heroes_or_unverified_scores | PASS |
| tests.test_draft_alpha_bugfix::test_farm_warning_belongs_only_to_pair_and_team | PASS |
| tests.test_draft_alpha_bugfix::test_symmetric_synergy_once_per_pair_and_directed_rule_keeps_direction | PASS |
| tests.test_draft_alpha_bugfix::test_unknown_capabilities_do_not_create_negative_evidence | PASS |
| tests.test_draft_alpha_bugfix::test_final_team_score_ignores_storage_order_of_roster | PASS |
| tests.test_draft_analyzer::test_ten_heroes_both_teams_and_hidden_round_visibility | PASS |
| tests.test_draft_analyzer::test_late_earthshaker_changes_final_not_ck_at_pick | PASS |
| tests.test_draft_analyzer::test_same_round_cannot_be_called_later_counterpick | PASS |
| tests.test_draft_analyzer::test_final_only_with_null_picks_has_identical_final_evaluations | PASS |
| tests.test_draft_analyzer::test_bad_order_falls_back_without_losing_actions[duplicate] | PASS |
| tests.test_draft_analyzer::test_bad_order_falls_back_without_losing_actions[partial] | PASS |
| tests.test_draft_analyzer::test_bad_order_falls_back_without_losing_actions[gap] | PASS |
| tests.test_draft_analyzer::test_bad_order_falls_back_without_losing_actions[wrong_team] | PASS |
| tests.test_draft_analyzer::test_bad_order_falls_back_without_losing_actions[wrong_hero] | PASS |
| tests.test_draft_analyzer::test_bad_order_falls_back_without_losing_actions[invalid_round] | PASS |
| tests.test_draft_analyzer::test_bad_order_falls_back_without_losing_actions[huge_order] | PASS |
| tests.test_draft_analyzer::test_bad_order_falls_back_without_losing_actions[ban_conflict] | PASS |
| tests.test_draft_analyzer::test_unique_out_of_order_array_sorted_by_valid_order_source_index_preserved | PASS |
| tests.test_draft_analyzer::test_public_policy_neutral_sequence_has_no_invented_cm_stage | PASS |
| tests.test_draft_analyzer::test_default_only_enables_exact_verified_mode_patch_and_cm_falls_back | PASS |
| tests.test_draft_analyzer::test_missing_evidence_never_returns_fake_fifty[patch_none] | PASS |
| tests.test_draft_analyzer::test_missing_evidence_never_returns_fake_fifty[unknown_patch] | PASS |
| tests.test_draft_analyzer::test_missing_evidence_never_returns_fake_fifty[unknown_heroes] | PASS |
| tests.test_draft_analyzer::test_missing_evidence_never_returns_fake_fifty[no_roster] | PASS |
| tests.test_draft_analyzer::test_matchup_sample_smoothing_and_no_causal_label_from_winrate | PASS |
| tests.test_draft_analyzer::test_outcome_kda_lane_gold_duration_do_not_affect_draft_report_and_no_mutation | PASS |
| tests.test_draft_analyzer::test_config_rejects_missing_weights_and_ambiguous_policies | PASS |
| tests.test_draft_analyzer::test_fixture_pipeline_opendota_snapshot_normalization_report_preserves_bans | PASS |
| tests.test_draft_universality::test_independent_ten_heroes_have_descriptors_but_no_invented_mechanics | PASS |
| tests.test_draft_universality::test_catalog_is_descriptive_and_cannot_change_scores | PASS |
| tests.test_draft_universality::test_independent_profiles_use_same_generic_engine_and_rules_change_scores | PASS |
| tests.test_draft_universality::test_changed_roster_changes_scores_without_any_outcome_change | PASS |
| tests.test_draft_universality::test_renaming_every_hero_id_preserves_all_scores | PASS |
| tests.test_draft_universality::test_match_id_is_only_report_identity[fixture_snapshot] | PASS |
| tests.test_draft_universality::test_match_id_is_only_report_identity[independent_snapshot] | PASS |
| tests.test_draft_universality::test_independent_partial_picks_keep_final_analysis | PASS |
| tests.test_draft_universality::test_inconsistent_team_code_rejects_sequence | PASS |
| tests.test_draft_universality::test_real_match_replay_preserves_invalid_picks_and_never_invents_stages | PASS |
| tests.test_group_flow::test_dispatcher_storage_authenticated_api_and_public_contract | PASS |
| tests.test_group_flow::test_repeated_concurrent_chats_and_restart_reuse_reports | PASS |
| tests.test_group_flow::test_provider_errors_and_no_fabricated_reports[API_UNAVAILABLE-503] | PASS |
| tests.test_group_flow::test_provider_errors_and_no_fabricated_reports[RATE_LIMITED-429] | PASS |
| tests.test_group_flow::test_provider_errors_and_no_fabricated_reports[NOT_FOUND-404] | PASS |
| tests.test_group_flow::test_provider_errors_and_no_fabricated_reports[MALFORMED_RESPONSE-502] | PASS |
| tests.test_group_flow::test_pending_unknown_and_interrupted_worker | PASS |
| tests.test_group_flow::test_partial_missing_arrays_and_timeline_filters | PASS |
| tests.test_group_flow::test_section_failure_isolated_and_safe | PASS |
| tests.test_group_flow::test_unauthorized_match_routes_and_unavailable_database | PASS |
| tests.test_group_flow::test_public_openapi_schema_snapshot | PASS |
| tests.test_group_flow::test_malformed_array_is_502_not_an_invented_analysis | PASS |
| tests.test_group_flow::test_partial_roster_keeps_available_overview_without_fabrication | PASS |
| tests.test_group_flow::test_refreshed_source_invalidates_cached_sections | PASS |
| tests.test_group_flow::test_group_flow_fetches_matchups_and_persists_evidence | PASS |
| tests.test_group_flow::test_sequential_contract_preserves_separate_pick_and_final_fields | PASS |
| tests.test_group_flow::test_corrupt_saved_dto_is_safe_503_without_reanalysis | PASS |
| tests.test_group_flow::test_forwarded_match_link_is_public_to_other_authenticated_user | PASS |
| tests.test_group_flow::test_group_rate_limit_applies_across_senders | PASS |
| tests.test_local_alpha::test_local_routes_absent_when_flag_off | PASS |
| tests.test_local_alpha::test_local_flag_rejects_remote_database | PASS |
| tests.test_local_alpha::test_local_routes_reject_remote_clients_and_origins | PASS |
| tests.test_match_ingestion::test_concurrent_requests_cache_restart_and_ttl | PASS |
| tests.test_match_ingestion::test_old_cached_snapshot_without_public_player_version_is_refetched | PASS |
| tests.test_match_ingestion::test_pending_row_is_recovered_after_restart | PASS |
| tests.test_match_ingestion::test_error_statuses_are_cached_without_response_body[RATE_LIMITED-failed] | PASS |
| tests.test_match_ingestion::test_error_statuses_are_cached_without_response_body[API_UNAVAILABLE-failed] | PASS |
| tests.test_match_ingestion::test_error_statuses_are_cached_without_response_body[MALFORMED_RESPONSE-failed] | PASS |
| tests.test_match_normalization::test_full_match_creates_summary_ten_players_raw_and_derived | PASS |
| tests.test_match_normalization::test_partial_match_keeps_zero_and_marks_unknown_as_unavailable | PASS |
| tests.test_match_normalization::test_invalid_or_duplicate_player_slots_are_rejected[players0] | PASS |
| tests.test_match_normalization::test_invalid_or_duplicate_player_slots_are_rejected[players1] | PASS |
| tests.test_match_normalization::test_invalid_or_duplicate_player_slots_are_rejected[players2] | PASS |
| tests.test_match_normalization::test_invalid_or_duplicate_player_slots_are_rejected[players3] | PASS |
| tests.test_match_normalization::test_unknown_hero_and_fallback_names_do_not_invent_pick_order | PASS |
| tests.test_match_normalization::test_public_nickname_is_used_only_when_present | PASS |
| tests.test_match_normalization::test_parsed_player_fields_preserve_zero_and_reject_invalid_values | PASS |
| tests.test_match_normalization::test_public_inventory_distinguishes_empty_unknown_and_missing_without_changing_raw_ids | PASS |
| tests.test_match_normalization::test_player_lane_limitation_matches_actual_unknown_count | PASS |
| tests.test_match_normalization::test_bad_draft_order_records_source_without_reconstruction | PASS |
| tests.test_match_normalization::test_absent_teamfight_log_and_invalid_advantage_are_partial | PASS |
| tests.test_match_normalization::test_role_is_unknown_without_evidence_and_not_estimated | PASS |
| tests.test_match_normalization::test_normalization_is_deterministic_json_and_does_not_mutate_snapshot | PASS |
| tests.test_migrations::test_migrations_on_separate_empty_postgresql | PASS |
| tests.test_opendota::test_full_match_keeps_public_nickname_and_removes_private_identifiers | PASS |
| tests.test_opendota::test_missing_or_null_extended_fields_are_partial[picks_bans] | PASS |
| tests.test_opendota::test_missing_or_null_extended_fields_are_partial[objectives] | PASS |
| tests.test_opendota::test_missing_or_null_extended_fields_are_partial[teamfights] | PASS |
| tests.test_opendota::test_missing_or_null_extended_fields_are_partial[radiant_gold_adv] | PASS |
| tests.test_opendota::test_missing_or_null_extended_fields_are_partial[patch] | PASS |
| tests.test_opendota::test_malformed_and_wrong_match_are_rejected[payload0] | PASS |
| tests.test_opendota::test_malformed_and_wrong_match_are_rejected[payload1] | PASS |
| tests.test_opendota::test_malformed_and_wrong_match_are_rejected[payload2] | PASS |
| tests.test_opendota::test_malformed_and_wrong_match_are_rejected[payload3] | PASS |
| tests.test_opendota::test_malformed_and_wrong_match_are_rejected[payload4] | PASS |
| tests.test_opendota::test_http_status_mapping[404-NOT_FOUND] | PASS |
| tests.test_opendota::test_http_status_mapping[401-API_UNAVAILABLE] | PASS |
| tests.test_opendota::test_rate_limit_respects_retry_after_without_retry | PASS |
| tests.test_opendota::test_transient_failures_have_bounded_backoff[500] | PASS |
| tests.test_opendota::test_transient_failures_have_bounded_backoff[timeout] | PASS |
| tests.test_opendota::test_malformed_json_and_api_key_do_not_leak | PASS |
| tests.test_opendota_matchups::test_bad_matchup_data_rejected[None] | PASS |
| tests.test_opendota_matchups::test_bad_matchup_data_rejected[body1] | PASS |
| tests.test_opendota_matchups::test_bad_matchup_data_rejected[body2] | PASS |
| tests.test_opendota_matchups::test_bad_matchup_data_rejected[body3] | PASS |
| tests.test_opendota_matchups::test_bad_matchup_data_rejected[body4] | PASS |
| tests.test_opendota_matchups::test_bad_matchup_data_rejected[body5] | PASS |
| tests.test_opendota_matchups::test_bad_matchup_data_rejected[body6] | PASS |
| tests.test_opendota_matchups::test_matchup_http_headers_cache_singleflight_and_ttl | PASS |
| tests.test_opendota_matchups::test_429_halts_batch_and_cooldown_covers_other_heroes | PASS |
| tests.test_opendota_matchups::test_http_failures_are_safe_and_retry_bounded[404-not_found] | PASS |
| tests.test_opendota_matchups::test_http_failures_are_safe_and_retry_bounded[500-unavailable] | PASS |
| tests.test_opendota_matchups::test_http_failures_are_safe_and_retry_bounded[200-malformed] | PASS |
| tests.test_opendota_matchups::test_timeout_is_unavailable_without_raw_exception | PASS |
| tests.test_opendota_matchups::test_unknown_out_of_range_heroes_do_not_crash_or_make_http_calls | PASS |
| tests.test_overview::test_existing_match_fixtures_keep_real_roster[timeline/9051271323.json-9051271323] | PASS |
| tests.test_overview::test_existing_match_fixtures_keep_real_roster[draft/independent.json-1000000001] | PASS |
| tests.test_overview::test_partial_roster_and_unknown_metadata_do_not_invent_values | PASS |
| tests.test_overview::test_missing_optional_overview_fields_from_old_report_still_parse | PASS |
| tests.test_overview::test_metadata_catalog_is_pinned_and_unknown_ids_return_none | PASS |
| tests.test_performance::test_both_teams_ten_players_deterministic_json_no_mutation | PASS |
| tests.test_performance::test_support_low_gpm_with_healing_and_assists_is_not_penalized_as_core | PASS |
| tests.test_performance::test_low_core_economy_is_compared_only_with_same_team_cores | PASS |
| tests.test_performance::test_unconfirmed_position_never_confidently_selects[missing] | PASS |
| tests.test_performance::test_unconfirmed_position_never_confidently_selects[lane_only] | PASS |
| tests.test_performance::test_unconfirmed_position_never_confidently_selects[estimated] | PASS |
| tests.test_performance::test_no_role_no_farm_inference_from_hero_or_gpm | PASS |
| tests.test_performance::test_unsupported_modes_are_explicitly_unscored[None] | PASS |
| tests.test_performance::test_unsupported_modes_are_explicitly_unscored[0] | PASS |
| tests.test_performance::test_unsupported_modes_are_explicitly_unscored[23] | PASS |
| tests.test_performance::test_unsupported_modes_are_explicitly_unscored[999] | PASS |
| tests.test_performance::test_short_or_missing_duration_never_amplifies_rates_into_scores[None] | PASS |
| tests.test_performance::test_short_or_missing_duration_never_amplifies_rates_into_scores[1] | PASS |
| tests.test_performance::test_short_or_missing_duration_never_amplifies_rates_into_scores[899] | PASS |
| tests.test_performance::test_duration_gate_boundary_and_outlier_fifty_deaths_is_bounded | PASS |
| tests.test_performance::test_absent_small_team_kill_totals_disable_participation[None] | PASS |
| tests.test_performance::test_absent_small_team_kill_totals_disable_participation[0] | PASS |
| tests.test_performance::test_absent_small_team_kill_totals_disable_participation[1] | PASS |
| tests.test_performance::test_absent_small_team_kill_totals_disable_participation[9] | PASS |
| tests.test_performance::test_zero_kills_zero_deaths_and_inconsistent_participation_are_safe | PASS |
| tests.test_performance::test_missing_wards_unparsed_match_and_missing_damage_do_not_imply_zero | PASS |
| tests.test_performance::test_completely_missing_stats_produce_null_and_no_selected_player | PASS |
| tests.test_performance::test_winner_draft_and_opponent_performance_do_not_drive_own_scores | PASS |
| tests.test_performance::test_selection_is_team_scoped_and_never_assumes_our_team | PASS |
| tests.test_performance::test_selection_threshold_margin_ties_and_independent_axes | PASS |
| tests.test_performance::test_conflicting_roles_incomplete_roster_and_invalid_evidence | PASS |
| tests.test_performance::test_normalizer_wards_and_estimated_position_validate_and_preserve_zero | PASS |
| tests.test_performance::test_config_rejects_bad_weights_and_thresholds | PASS |
| tests.test_performance::test_saved_real_match_offline_snapshot_to_performance | PASS |
| tests.test_performance::test_zero_reference_does_not_invent_large_credit_from_one_unit_of_healing | PASS |
| tests.test_performance::test_extreme_positive_contributions_are_capped_and_not_added_repeatedly | PASS |
| tests.test_performance::test_empty_roster_has_both_teams_and_no_fabricated_players | PASS |
| tests.test_performance::test_low_missing_metrics_are_not_replaced_by_zero_penalties | PASS |
| tests.test_performance_integration::test_ingestion_normalization_shared_evaluator_bot_notification | PASS |
| tests.test_performance_integration::test_group_dispatcher_publishes_both_teams_through_stub_transport | PASS |
| tests.test_performance_integration::test_analysis_failure_preserves_ingestion_success_and_does_not_leak_exception | PASS |
| tests.test_performance_integration::test_unavailable_match_does_not_call_evaluator | PASS |
| tests.test_performance_integration::test_mismatched_snapshot_identity_is_not_published | PASS |
| tests.test_performance_participation_contract::test_ratio_contract_and_refusal_reasons[KP-QA-01-4-10-0.6-0.6-None] | PASS |
| tests.test_performance_participation_contract::test_ratio_contract_and_refusal_reasons[KP-QA-02-8-10-1.0-1.0-None] | PASS |
| tests.test_performance_participation_contract::test_ratio_contract_and_refusal_reasons[KP-QA-03-9-10-1.1-None-kill_participation_over_team_score_unverified] | PASS |
| tests.test_performance_participation_contract::test_ratio_contract_and_refusal_reasons[KP-QA-04-10-10-1.2-None-kill_participation_over_team_score_unverified] | PASS |
| tests.test_performance_participation_contract::test_ratio_contract_and_refusal_reasons[KP-QA-05-9998-10-1000.0-None-kill_participation_counter_anomaly] | PASS |
| tests.test_performance_participation_contract::test_ratio_contract_and_refusal_reasons[KP-QA-06-8-0-None-None-kill_participation_team_score_zero] | PASS |
| tests.test_performance_participation_contract::test_ratio_contract_and_refusal_reasons[KP-QA-07-8-9-1.1111111111111112-None-kill_participation_team_score_small] | PASS |
| tests.test_performance_participation_contract::test_ratio_contract_and_refusal_reasons[score_missing-8-None-None-None-kill_participation_team_score_missing] | PASS |
| tests.test_performance_participation_contract::test_missing_counter_has_distinct_reason[kills] | PASS |
| tests.test_performance_participation_contract::test_missing_counter_has_distinct_reason[assists] | PASS |
| tests.test_performance_participation_contract::test_player_kills_exceeding_team_score_is_anomalous | PASS |
| tests.test_performance_participation_contract::test_peer_dependency_axes_coverage_confidence_and_teams | PASS |
| tests.test_performance_participation_contract::test_existing_persisted_ruiner_report_is_read_without_rewriting | PASS |
| tests.test_performance_participation_contract::test_api_returns_safe_diagnostic_without_reanalysis_or_db_write | PASS |
| tests.test_performance_preliminary::test_selection_table[scores0-single-slots0] | PASS |
| tests.test_performance_preliminary::test_selection_table[scores1-single-slots1] | PASS |
| tests.test_performance_preliminary::test_selection_table[scores2-group-slots2] | PASS |
| tests.test_performance_preliminary::test_selection_table[scores3-group-slots3] | PASS |
| tests.test_performance_preliminary::test_selection_table[scores4-group-slots4] | PASS |
| tests.test_performance_preliminary::test_selection_table[scores5-none-slots5] | PASS |
| tests.test_performance_preliminary::test_selection_table[scores6-none-slots6] | PASS |
| tests.test_performance_preliminary::test_selection_table[scores7-group-slots7] | PASS |
| tests.test_performance_preliminary::test_selection_table[scores8-group-slots8] | PASS |
| tests.test_performance_preliminary::test_selection_table[scores9-single-slots9] | PASS |
| tests.test_performance_preliminary::test_selection_table[scores10-group-slots10] | PASS |
| tests.test_performance_preliminary::test_selection_table[scores11-group-slots11] | PASS |
| tests.test_performance_preliminary::test_missing_top_signal_refuses_including_ties[scores0] | PASS |
| tests.test_performance_preliminary::test_missing_top_signal_refuses_including_ties[scores1] | PASS |
| tests.test_performance_preliminary::test_group_member_below_signal_display_threshold_is_included | PASS |
| tests.test_performance_preliminary::test_invalid_input_refusal[change0-invalid_roster] | PASS |
| tests.test_performance_preliminary::test_invalid_input_refusal[change1-invalid_roster] | PASS |
| tests.test_performance_preliminary::test_invalid_input_refusal[change2-invalid_roster] | PASS |
| tests.test_performance_preliminary::test_invalid_input_refusal[change3-invalid_roster] | PASS |
| tests.test_performance_preliminary::test_invalid_input_refusal[change4-invalid_roster] | PASS |
| tests.test_performance_preliminary::test_invalid_input_refusal[change5-incomplete_player_scores] | PASS |
| tests.test_performance_preliminary::test_invalid_input_refusal[change6-invalid_player_scores] | PASS |
| tests.test_performance_preliminary::test_invalid_input_refusal[change7-invalid_player_scores] | PASS |
| tests.test_performance_preliminary::test_invalid_input_refusal[change8-invalid_player_scores] | PASS |
| tests.test_performance_preliminary::test_invalid_input_refusal[change9-invalid_player_scores] | PASS |
| tests.test_performance_preliminary::test_invalid_input_refusal[change10-blocking_player_context] | PASS |
| tests.test_performance_preliminary::test_incomplete_team_and_leaver_evidence | PASS |
| tests.test_performance_preliminary::test_roles_confidence_and_strict_selection_unchanged | PASS |
| tests.test_performance_preliminary::test_real_saved_report_projection_is_compatible_and_does_not_mutate | PASS |
| tests.test_performance_preliminary::test_winner_opponents_and_match_id_do_not_change_selection | PASS |
| tests.test_performance_preliminary::test_9051271323_all_existing_fields_remain_identical | PASS |
| tests.test_performance_preliminary::test_strict_dto_rejects_incoherent_states[change0] | PASS |
| tests.test_performance_preliminary::test_strict_dto_rejects_incoherent_states[change1] | PASS |
| tests.test_performance_preliminary::test_strict_dto_rejects_incoherent_states[change2] | PASS |
| tests.test_performance_preliminary::test_strict_dto_rejects_incoherent_states[change3] | PASS |
| tests.test_performance_preliminary::test_strict_dto_rejects_incoherent_states[change4] | PASS |
| tests.test_performance_preliminary::test_strict_dto_rejects_incoherent_states[change5] | PASS |
| tests.test_performance_preliminary::test_strict_dto_rejects_incoherent_states[change6] | PASS |
| tests.test_performance_preliminary_api::test_preliminary_storage_cached_read_api_and_legacy_projection[False] | PASS |
| tests.test_performance_preliminary_api::test_preliminary_storage_cached_read_api_and_legacy_projection[True] | PASS |
| tests.test_performance_preliminary_qa::test_qa_decision_table[RI-QA-01-scores0-single-slots0-20-highest_relative_index] | PASS |
| tests.test_performance_preliminary_qa::test_qa_decision_table[RI-QA-02-scores1-single-slots1-15-highest_relative_index] | PASS |
| tests.test_performance_preliminary_qa::test_qa_decision_table[RI-QA-03-scores2-group-slots2-14-close_scores] | PASS |
| tests.test_performance_preliminary_qa::test_qa_decision_table[RI-QA-04-scores3-group-slots3-5-close_scores] | PASS |
| tests.test_performance_preliminary_qa::test_qa_decision_table[RI-QA-05-scores4-group-slots4-0-close_scores] | PASS |
| tests.test_performance_preliminary_qa::test_qa_decision_table[RI-QA-06-scores5-none-slots5-None-all_indices_zero] | PASS |
| tests.test_performance_preliminary_qa::test_qa_decision_table[RI-QA-07-scores6-none-slots6-None-incomplete_player_scores] | PASS |
| tests.test_performance_preliminary_qa::test_qa_decision_table[RI-QA-09-scores7-group-slots7-14-close_scores] | PASS |
| tests.test_performance_preliminary_qa::test_qa_decision_table[RI-QA-10-scores8-group-slots8-14-close_scores] | PASS |
| tests.test_performance_preliminary_qa::test_qa_decision_table[RI-QA-11-scores9-single-slots9-16-highest_relative_index] | PASS |
| tests.test_performance_preliminary_qa::test_qa_decision_table[RI-QA-12-scores10-group-slots10-1-close_scores] | PASS |
| tests.test_performance_preliminary_qa::test_qa_08_missing_top_signal_is_none | PASS |
| tests.test_performance_preliminary_qa::test_live_saved_9051271323_matches_api_and_new_projection | PASS |
| tests.test_performance_preliminary_qa::test_two_team_projections_are_pure_under_concurrency | PASS |
| tests.test_performance_preliminary_qa::test_existing_projection_rejects_semantically_inconsistent_confidence_and_reason | PASS |
| tests.test_performance_preliminary_qa::test_fix_qa_semantic_corruptions[FIX-QA-02-projection_change0-None] | PASS |
| tests.test_performance_preliminary_qa::test_fix_qa_semantic_corruptions[FIX-QA-03-projection_change1-None] | PASS |
| tests.test_performance_preliminary_qa::test_fix_qa_semantic_corruptions[FIX-QA-04-projection_change2-player_change2] | PASS |
| tests.test_performance_preliminary_qa::test_fix_qa_semantic_corruptions[FIX-QA-05-projection_change3-None] | PASS |
| tests.test_performance_preliminary_qa::test_fix_qa_semantic_corruptions[FIX-QA-07-projection_change4-player_change4] | PASS |
| tests.test_performance_preliminary_qa::test_fix_qa_semantic_corruptions[FIX-QA-extra-highest-projection_change5-None] | PASS |
| tests.test_performance_preliminary_qa::test_fix_qa_valid_legacy_leaver_and_lost_context | PASS |
| tests.test_performance_preliminary_qa::test_fix_qa_structural_mismatch_stays_invalid | PASS |
| tests.test_performance_preliminary_qa::test_api_rejects_inconsistent_persisted_preliminary | PASS |
| tests.test_performance_preliminary_qa::test_api_rejects_structurally_invalid_saved_projection[change0] | PASS |
| tests.test_performance_preliminary_qa::test_api_rejects_structurally_invalid_saved_projection[change1] | PASS |
| tests.test_player_catalog::test_pinned_catalogs_cover_known_heroes_and_items | PASS |
| tests.test_player_catalog::test_empty_missing_and_unknown_items_are_distinct | PASS |
| tests.test_repositories::test_user_upsert_preserves_bigint_and_creation | PASS |
| tests.test_repositories::test_match_upsert_jsonb_and_null | PASS |
| tests.test_repositories::test_analysis_versions_are_unique_and_keep_uuid | PASS |
| tests.test_repositories::test_history_upsert_order_isolation_and_late_events | PASS |
| tests.test_repositories::test_database_constraints[INSERT INTO telegram_users (telegram_user_id) VALUES (9007199254740993)] | PASS |
| tests.test_repositories::test_database_constraints[INSERT INTO matches (match_id) VALUES (9007199254740995)] | PASS |
| tests.test_repositories::test_database_constraints[INSERT INTO match_analyses (match_id, algorithm_version) VALUES (9007199254740995, 'fixture-v1')] | PASS |
| tests.test_repositories::test_database_constraints[INSERT INTO user_match_history (telegram_user_id, match_id) VALUES (9007199254740993, 9007199254740995)] | PASS |
| tests.test_repositories::test_database_constraints[INSERT INTO match_analyses (match_id, algorithm_version) VALUES (77777, 'fixture-v1')] | PASS |
| tests.test_repositories::test_database_constraints[INSERT INTO user_match_history (telegram_user_id, match_id) VALUES (77777, 9007199254740995)] | PASS |
| tests.test_repositories::test_database_constraints[INSERT INTO user_match_history (telegram_user_id, match_id) VALUES (9007199254740993, 77777)] | PASS |
| tests.test_repositories::test_database_constraints[UPDATE matches SET fetch_status = 'invented' WHERE match_id = 9007199254740995] | PASS |
| tests.test_repositories::test_database_constraints[UPDATE match_analyses SET status = 'invented' WHERE match_id = 9007199254740995] | PASS |
| tests.test_repositories::test_database_constraints[UPDATE match_analyses SET completeness = 'invented' WHERE match_id = 9007199254740995] | PASS |
| tests.test_repositories::test_database_constraints[UPDATE match_analyses SET algorithm_version = '' WHERE match_id = 9007199254740995] | PASS |
| tests.test_repositories::test_database_constraints[INSERT INTO matches (match_id) VALUES (0)] | PASS |
| tests.test_repositories::test_database_constraints[INSERT INTO telegram_users (telegram_user_id) VALUES (-1)] | PASS |
| tests.test_repositories::test_database_constraints[DELETE FROM matches WHERE match_id = 9007199254740995] | PASS |
| tests.test_repositories::test_database_constraints[DELETE FROM telegram_users WHERE telegram_user_id = 9007199254740993] | PASS |
| tests.test_repositories::test_repository_input_boundaries | PASS |
| tests.test_repositories::test_transaction_rollback | PASS |
| tests.test_sessions::test_session_round_trip_and_unique_token | PASS |
| tests.test_sessions::test_invalid_sessions[expired] | PASS |
| tests.test_sessions::test_invalid_sessions[wrong-key] | PASS |
| tests.test_sessions::test_invalid_sessions[tampered] | PASS |
| tests.test_sessions::test_invalid_sessions[garbage] | PASS |
| tests.test_sessions::test_invalid_sessions[empty] | PASS |
| tests.test_sessions::test_invalid_sessions[long] | PASS |
| tests.test_sessions::test_invalid_sessions[alg-none] | PASS |
| tests.test_sessions::test_invalid_sessions[alg-hs384] | PASS |
| tests.test_sessions::test_invalid_sessions[no-exp] | PASS |
| tests.test_sessions::test_invalid_sessions[bad-aud] | PASS |
| tests.test_sessions::test_invalid_sessions[bad-iss] | PASS |
| tests.test_sessions::test_invalid_sessions[future] | PASS |
| tests.test_sessions::test_invalid_sessions[bad-sub] | PASS |
| tests.test_sessions::test_invalid_sessions[bad-time] | PASS |
| tests.test_sessions::test_invalid_sessions[long-ttl] | PASS |
| tests.test_sessions::test_invalid_sessions[deep-header] | PASS |
| tests.test_sessions::test_auth_missing_short_or_reused_secret_fails_closed | PASS |
| tests.test_sessions::test_unsafe_cors_rejected[*] | PASS |
| tests.test_sessions::test_unsafe_cors_rejected[https://*.example.org] | PASS |
| tests.test_sessions::test_unsafe_cors_rejected[http://example.org] | PASS |
| tests.test_sessions::test_unsafe_cors_rejected[https://example.org/path] | PASS |
| tests.test_sessions::test_unsafe_cors_rejected[https://user:password@example.org] | PASS |
| tests.test_sessions::test_unsafe_cors_rejected[null] | PASS |
| tests.test_telegram_auth::test_hmac_optional_signature_unknown_fields_unicode_and_plus | PASS |
| tests.test_telegram_auth::test_rejects_invalid_data[empty] | PASS |
| tests.test_telegram_auth::test_rejects_invalid_data[wrong-key] | PASS |
| tests.test_telegram_auth::test_rejects_invalid_data[wrong-hash] | PASS |
| tests.test_telegram_auth::test_rejects_invalid_data[empty-hash] | PASS |
| tests.test_telegram_auth::test_rejects_invalid_data[short-hash] | PASS |
| tests.test_telegram_auth::test_rejects_invalid_data[upper-hash] | PASS |
| tests.test_telegram_auth::test_rejects_invalid_data[id-tamper] | PASS |
| tests.test_telegram_auth::test_rejects_invalid_data[time-tamper] | PASS |
| tests.test_telegram_auth::test_rejects_invalid_data[missing-user] | PASS |
| tests.test_telegram_auth::test_rejects_invalid_data[missing-date] | PASS |
| tests.test_telegram_auth::test_rejects_invalid_data[missing-hash] | PASS |
| tests.test_telegram_auth::test_rejects_invalid_data[old] | PASS |
| tests.test_telegram_auth::test_rejects_invalid_data[future] | PASS |
| tests.test_telegram_auth::test_rejects_invalid_data[bad-date] | PASS |
| tests.test_telegram_auth::test_rejects_invalid_data[zero-date] | PASS |
| tests.test_telegram_auth::test_rejects_invalid_data[bad-percent] | PASS |
| tests.test_telegram_auth::test_rejects_invalid_data[bad-utf8] | PASS |
| tests.test_telegram_auth::test_rejects_invalid_data[bad-surrogate] | PASS |
| tests.test_telegram_auth::test_rejects_invalid_data[duplicate-user] | PASS |
| tests.test_telegram_auth::test_rejects_invalid_data[duplicate-auth_date] | PASS |
| tests.test_telegram_auth::test_rejects_invalid_data[duplicate-hash] | PASS |
| tests.test_telegram_auth::test_rejects_invalid_data[duplicate-extra] | PASS |
| tests.test_telegram_auth::test_rejects_invalid_data[bad-json] | PASS |
| tests.test_telegram_auth::test_rejects_invalid_data[duplicate-json] | PASS |
| tests.test_telegram_auth::test_rejects_invalid_data[json-nan] | PASS |
| tests.test_telegram_auth::test_rejects_invalid_data[json-list] | PASS |
| tests.test_telegram_auth::test_rejects_invalid_data[negative-id] | PASS |
| tests.test_telegram_auth::test_rejects_invalid_data[zero-id] | PASS |
| tests.test_telegram_auth::test_rejects_invalid_data[float-id] | PASS |
| tests.test_telegram_auth::test_rejects_invalid_data[bool-id] | PASS |
| tests.test_telegram_auth::test_rejects_invalid_data[string-id] | PASS |
| tests.test_telegram_auth::test_rejects_invalid_data[huge-id] | PASS |
| tests.test_telegram_auth::test_rejects_invalid_data[missing-id] | PASS |
| tests.test_telegram_auth::test_rejects_invalid_data[missing-name] | PASS |
| tests.test_telegram_auth::test_rejects_invalid_data[null-name] | PASS |
| tests.test_telegram_auth::test_rejects_invalid_data[long-name] | PASS |
| tests.test_telegram_auth::test_rejects_invalid_data[long-username] | PASS |
| tests.test_telegram_auth::test_rejects_invalid_data[nul-name] | PASS |
| tests.test_telegram_auth::test_rejects_invalid_data[newline-field] | PASS |
| tests.test_telegram_auth::test_rejects_invalid_data[empty-key] | PASS |
| tests.test_telegram_auth::test_rejects_invalid_data[no-equals] | PASS |
| tests.test_telegram_auth::test_rejects_invalid_data[too-many-fields] | PASS |
| tests.test_telegram_auth::test_rejects_invalid_data[too-long] | PASS |
| tests.test_telegram_auth::test_configurable_age_boundaries[-60] | PASS |
| tests.test_telegram_auth::test_configurable_age_boundaries[5] | PASS |
| tests.test_timeline::test_full_match_chronology_evidence_and_turning_point | PASS |
| tests.test_timeline::test_partial_without_fights_and_missing_sources | PASS |
| tests.test_timeline::test_empty_arrays_are_available_but_no_events_or_curves_is_unavailable | PASS |
| tests.test_timeline::test_duplicate_kill_and_fight_are_merged_without_making_extra_kills | PASS |
| tests.test_timeline::test_malformed_times_actors_and_nullable_entries_are_skipped | PASS |
| tests.test_timeline::test_roshan_without_owner_is_not_given_a_team | PASS |
| tests.test_timeline::test_boolean_team_marker_is_not_interpreted_as_radiant | PASS |
| tests.test_timeline::test_advantage_signs_and_zero_are_correct | PASS |
| tests.test_timeline::test_missing_curves_never_create_a_turning_point | PASS |
| tests.test_timeline::test_gap_in_minute_grid_is_not_interpolated | PASS |
| tests.test_timeline::test_buyback_and_filters | PASS |
| tests.test_timeline::test_miniboss_does_not_become_roshan_and_no_synthesized_fight | PASS |
| tests.test_timeline::test_deterministic_ids_and_input_is_unchanged | PASS |
| tests.test_timeline::test_real_match_redacted_projection | PASS |

## 28 граничных сценариев

PASS означает совпадение с заявленным безопасным поведением. Проверка, успешно воспроизводящая дефект, помечена FAIL для целевого инварианта. Синтетические значения относятся исключительно к копиям в памяти, не к реальному матчу.

| ID | Сценарий | Ожидаемое / фактическое | Статус | Доказательство |
|---|---|---|---|---|
| B01 | Полный snapshot | baseline full сохранён; 10 players | PASS | test_full_match_keeps_public_nickname_and_removes_private_identifiers; offline9051271323 |
| B02 | Частичный snapshot | null сохранён, доступные оси доступны | PASS | test_partial_match_keeps_zero_and_marks_unknown_as_unavailable;9057722463 |
| B03 | Нераспарсенный | нет fabricated events/wards | PASS | test_missing_wards_unparsed_match_and_missing_damage_do_not_imply_zero |
| B04 | Нет match ID | MALFORMED_RESPONSE/MatchNormalizationError | PASS | experiments missing_match_id; test_malformed_and_wrong_match_are_rejected |
| B05 | OpenDota404 | NOT_FOUND, no fabricated data | PASS | test_http_status_mapping; test_provider_errors_and_no_fabricated_reports |
| B06 | 429 | RATE_LIMITED, Retry-After bounded; no immediate retry | PASS | test_rate_limit_respects_retry_after_without_retry |
| B07 | Timeout | bounded retries, API_UNAVAILABLE | PASS | test_transient_failures_have_bounded_backoff |
| B08 | Unexpected JSON | MALFORMED_RESPONSE | PASS | test_malformed_json_and_api_key_do_not_leak |
| B09 | Неполный roster | incomplete_team; нет вымышленных игроков | PASS | experiments incomplete_roster; test_partial_roster_keeps_available_overview_without_fabrication |
| B10 | Duplicate slot | normalization rejects | PASS | experiments duplicate_slot; test_invalid_or_duplicate_player_slots_are_rejected |
| B11 | Missing hero | hero null, invalid team unscored | PASS | experiments missing_hero |
| B12 | Unknown account | no ID invention, anonymous only missing nickname | PASS | test_full_match_keeps_public_nickname_and_removes_private_identifiers; test_public_nickname_is_used_only_when_present |
| B13 | Missing K/D/A | observed null, explicit reasons | PASS | experiments missing_kda; test_missing_counter_has_distinct_reason |
| B14 | Team score0 | no division; team_score_zero | PASS | test_ratio_contract_and_refusal_reasons[KP-QA-06]; experiments zero_score |
| B15 | Score below10 | raw ratio retained; usable null | PASS | test_ratio_contract_and_refusal_reasons[KP-QA-07]; experiments small_score |
| B16 | K+A>score и boundary=score | raw>1 retained, usable null; equality accepted | PASS | test_ratio_contract_and_refusal_reasons; experiments kp_boundary_equal/kp_over_score |
| B17 | Negative values | invalid->null без отрицательного score | PASS | experiments negative_stats; validation diagnostics missing F07 |
| B18 | Duration0 | parser rejects; direct normalization duration null, RI unavailable | PASS | experiments zero_duration; test_short_or_missing_duration_never_amplifies_rates_into_scores |
| B19 | Missing damage | не0, no fabricated impact/credit | PASS | experiments missing_damage_wards; test_low_missing_metrics_are_not_replaced_by_zero_penalties |
| B20 | Missing wards | не0 | PASS | test_missing_wards_unparsed_match_and_missing_damage_do_not_imply_zero |
| B21 | Missing events | Timeline unavailable/partial | PASS | test_partial_without_fights_and_missing_sources; test_empty_arrays_are_available_but_no_events_or_curves_is_unavailable |
| B22 | Estimated position | group assigned; low confidence | PASS | test_unconfirmed_position_never_confidently_selects;20-player traces |
| B23 | Unknown position | no inferred farm role, unknown cohort | PASS | test_no_role_no_farm_inference_from_hero_or_gpm; experiments unknown_position |
| B24 | Confirmed/unknown leaver | direct context works; raw end-to-end ignored | FAIL | test_incomplete_team_and_leaver_evidence PASS, experiments leaver_end_to_end unchanged ->F02 |
| B25 | Stale analysis | cached historical data accepted; new implementation not invalidated | FAIL | api_comparison flow_config_matches_current plus stale diagnostic ->F04; experiments stale_raw ->F05 |
| B26 | Model/config mismatch | contradictory metadata must fail safely; actual200 | FAIL | experiments stored_model_mismatch/config_mismatch/schema_mismatch ->F03 |
| B27 | Legacy preliminary missing | read-time projection, DB unchanged | PASS | 9057722463 live; test_preliminary_storage_cached_read_api_and_legacy_projection |
| B28 | Corrupt preliminary | semantic none or structural503 | PASS | test_api_rejects_inconsistent_persisted_preliminary; test_api_rejects_structurally_invalid_saved_projection; experiments |

## DATA-QA-01…25

| ID | Проверка | Результат | Основание |
|---|---|---|---|
| DATA-QA-01 | Полная цепочка OpenDota | PASS | CODE_MAP, actual symbols, parser/ingestion/group_flow tests |
| DATA-QA-02 | Место сохранения raw | PASS | JSONB подтверждено; найден F01, а не потеря scalar в parser |
| DATA-QA-03 | PostgreSQL схема | PASS | capture.schema + db_verification.constraints/indexes; migrations/repository tests |
| DATA-QA-04 | Все P0 поля | PASS | 58/58 inventoried; account original120 UNVERIFIED явно выделены |
| DATA-QA-05 | Все20 игроков | PASS | MATCH_TRACE + independently reconstructed120 indexes |
| DATA-QA-06 | Teams/slots | PASS | raw isRadiant agrees slot; same-team cohorts; отдельный event-space риск F10 |
| DATA-QA-07 | K/D/A/team scores | PASS | raw=normalized; расхождения aggregate counters второго матча описаны, не исправлялись |
| DATA-QA-08 | GPM/XPM units | PASS | нет повторного деления на duration; число type сохранено |
| DATA-QA-09 | Damage/healing | PASS | rates full precision, scalar сохранён |
| DATA-QA-10 | Observer/sentry | PASS | four counts preserved, no purchase/log substitution; отсутствующие null |
| DATA-QA-11 | Position/role | PASS | estimated≠confirmed lane; second unknown; конфликт duplicate positions tested |
| DATA-QA-12 | Leaver storage/use | FAIL | raw сохранён, typed decision path теряет — F02 |
| DATA-QA-13 | Null vs zero | PASS | source null not replaced0; gates/clamp объяснены |
| DATA-QA-14 | Все derived metrics | PASS | formulas and120 reconstructions; normalized round4 ≠ observed precision |
| DATA-QA-15 | Oracle1.2 | PASS | trace source→current diagnostic; game semantics остаётся UNVERIFIED |
| DATA-QA-16 | Spectre6 | PASS | 6.135271030802414→6; signals threshold.20 |
| DATA-QA-17 | Ruiner serialization | PASS | real local responses + current/legacy DTO tests; F03 corruption отдельно FAIL |
| DATA-QA-18 | Оба REST маршрута live авторизованно | BLOCKED | local200 и auth401 реальны; authenticated200 только существующие isolated tests |
| DATA-QA-19 | Quality/status/limitations | FAIL | семантика охватов исследована, но Timeline confirmed противоречит actor/team F10; stale diagnostic F04 |
| DATA-QA-20 | Legacy reports | PASS | 9057722463 projection only, unchanged DB |
| DATA-QA-21 | P1 other sections inventory | PASS | CSV поля и draft nested; API all sections, Timeline F10 отмечен |
| DATA-QA-22 | Backend vs source | PASS | F01–F11 classifications; отсутствующее parsed не названо потерей |
| DATA-QA-23 | Нет production edits | PASS | scope SHA, live raw/reports unchanged, no commit |
| DATA-QA-24 | Воспроизводимость | PASS | frozen local raw/hash, scripts, JUnit; перенос на чужую машину требует gitignored snapshots |
| DATA-QA-25 | Findings с evidence | PASS | F01–F11, files/functions/steps/impact/minimal fixes/dependencies |

## Не выполненные / ограниченные проверки

- Live authenticated HTTP200 и Telegram Mini App: BLOCKED отсутствующей сессией, изолированный auth-тест не заменяет это.
- Верификация первоначальных raw HTTP bytes до удаления приватных полей: UNVERIFIED; новые API ответы не могут восстановить прежний ответ.
- Причина Oracle11 assists и event-level уникальная kill participation: UNVERIFIED, полный assist журнал отсутствует. Простое число teamfight_participation1.2 не независимая верификация.
- Платные сервисы, POST parsing, новые live fetch матчей, массовый persisted reanalysis, frontend/UI/browser QA: NOT RUN, вне read-only задания.
- Реальное аварийное обновление рабочей БД: NOT RUN намеренно; F01 доказан MemorySession и UPSERT-кодом. Успех существующих408 тестов не покрывает этот инвариант, новую продуктивную регрессионную проверку следует добавить в багфиксе.
- Roshan source team2/3 без actor: synthetic _side возвращает unknown; корректная кодировка должна быть отдельно закреплена primary source/spec перед исправлением. Real snapshot подтверждает team3 для miniboss, но это не доказательство Roshan semantics. Slot0..9 vs player_slot пространство — отдельный риск, не установленная массовая порча этих20 игроков.
- Смысл team scores vs сумма personal kills второго матча не восстановлен; пользовательские счётчики не корректировались.

## Воспроизведение

Из корня dota-hub:

```sh
.venv/bin/python scripts/ri02_data01.py offline
.venv/bin/python scripts/ri02_data01.py experiments
.venv/bin/python scripts/ri02_data01.py timeline
.venv/bin/python scripts/ri02_data01_report.py
.venv/bin/python scripts/ri02_data01.py verify
.venv/bin/python scripts/ri02_data01.py validate
```

`capture` был выполнен один раз; повторная запись frozen capture запрещена самим скриптом. Он читает рабочую БД только после `SET TRANSACTION READ ONLY`, делает только GET локального API. `verifydb` повторно читает и сравнивает raw/reports, без writes. `sources` читает только публичные GitHub исходники. Не вызывать POST /analyze для повторения аудита. Raw/cal snapshots и private API/DB captures gitignored; перед переносом проверки нужен доступ к этим локальным исходникам. Не подменять их частичной test fixture.

Существующий тестовый запуск из backend:

```sh
../.venv/bin/python -m pytest -q --tb=short --junitxml=../docs/qa/ri02/data01/pytest.xml
```

TEST_DATABASE_URL должен указывать на отдельную localhost `dota_hub_test`, MIGRATION_TEST_DATABASE_URL — отдельную migration test DB. Existing checked_test_url запрещает совпадение с рабочей БД. Секреты в команды/логи не подставляются.

CSV создаётся из matrix_rows.json через bundled Artifact Tool:13,750 строк ×17 колонок, верифицирован round-trip ячеек, UTF-8 quoted CSV. Ячейки содержат диагностические данные/JSON, не выполняемые формулы. Пользователь запросил CSV, поэтому XLSX и визуальный редизайн таблицы не создавались. Для воспроизведения builder `scripts/ri02_data01_matrix.mjs` скопировать в временную папку с node_modules symlink на bundle; запустить bundled node с абсолютным root проекта аргументом. Набор dependencies берётся из load_workspace_dependencies. Пакетные директории не изменяются. Проверки структуры CSV и machine evidence сохранены рядом с отчётами.

## Шесть итоговых артефактов

1. [FIELD_MATRIX.csv](RI_02_DATA_01_FIELD_MATRIX.csv) —13750 строк, точные source paths, mappings, status/evidence.
2. [CODE_MAP.md](RI_02_DATA_01_CODE_MAP.md) — цепочка, функции, storage, HTTP и источники.
3. [MATCH_TRACE.md](RI_02_DATA_01_MATCH_TRACE.md) —20 детальных трасс, Oracle/Hoodwink/Spectre, формулы.
4. [API_CONTRACT_AUDIT.md](RI_02_DATA_01_API_CONTRACT_AUDIT.md) — DB→REST, legacy/current, auth граница.
5. [FINDINGS.md](RI_02_DATA_01_FINDINGS.md) — классифицированные дефекты, риски, рекомендации без реализации.
6. [QA_REPORT.md](RI_02_DATA_01_QA_REPORT.md) — фактические408 тестов,28 сценариев,25 критериев, ограничения.

**Итоговый статус: READY FOR QA.** DONE не присваивался. Аудит пригоден для независимой проверки, но полная исправность backend data pipeline и готовность RI к достоверным игровым выводам не подтверждены. Следующий шаг — согласование отдельных точечных багфиксов; ни один не применён этим заданием.
