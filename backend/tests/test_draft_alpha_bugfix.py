"""Regression for Alpha findings; the real match is frozen evidence, never a code path."""
import json
from copy import deepcopy
from pathlib import Path
from statistics import mean

from app.integrations.opendota_matchups import MatchupBatch
from app.models.matches import Team
from app.services.draft.analyzer import analyze_draft
from app.services.draft.config import default_config
from app.services.match_normalization import normalize_match_snapshot
from test_draft_analyzer import fixture_config, fixture_snapshot, stats_for
from test_draft_universality import independent_snapshot

EVIDENCE = Path(__file__).parent / 'fixtures/draft/9051271323/evidence.json'


def real_report():
    evidence = json.loads(EVIDENCE.read_text())
    match = normalize_match_snapshot(evidence['snapshot'])
    batches = tuple(MatchupBatch.model_validate_json(json.dumps(row)) for row in evidence['matchups'])
    return analyze_draft(match, matchups=batches)


def test_real_match_has_no_team_claims_on_individual_heroes_or_unverified_scores() -> None:
    report = real_report()
    assert report.mode == 'FINAL_ONLY' and 'picks_roster_mismatch' in report.source_quality
    assert len(report.pick_events) == 10
    assert {p.hero_id for p in report.pick_events if p.team == Team.RADIANT} == {123, 111, 43, 67, 81}
    assert {p.hero_id for p in report.pick_events if p.team == Team.DIRE} == {7, 35, 9, 23, 85}
    assert all(p.at_pick_score is None and p.final_score is None for p in report.pick_events)
    assert all(p.final_context.axes['matchup'] is None for p in report.pick_events)
    assert all(p.hero_name and not p.hero_name.startswith('Герой #') for p in report.pick_events)
    sniper = next(p for p in report.pick_events if p.hero_id == 35)
    assert sniper.hero_name == 'Sniper' and not sniper.pros
    assert all(r.scope != 'team' for r in sniper.final_context.reasons)
    for pick in report.pick_events:
        assert not pick.pros and not pick.cons  # No exact-patch mechanical proof in production config.
        assert all(reason.scope != 'team' for reason in pick.final_context.reasons)
        assert all(pick.hero_id in reason.hero_ids for reason in pick.final_context.reasons if reason.scope == 'interaction')
        assert all(reason.hero_ids == (pick.hero_id,) for reason in pick.final_context.reasons if reason.scope == 'individual')
        assert all(reason.patch_applicability != 'exact_patch:60' for reason in pick.final_context.reasons)
    assert any(r.code == 'composition_initiation_control' for r in report.teams[Team.DIRE].evaluation.reasons)
    assert not any(r.polarity == 'negative' and r.code.startswith('composition_')
                   for team in report.teams.values() for r in team.evaluation.reasons)


def test_farm_warning_belongs_only_to_pair_and_team() -> None:
    report = real_report()
    warnings = {pick.hero_id: pick.resource_warnings for pick in report.pick_events}
    assert warnings[81] and warnings[67]
    assert all(not warnings[hero] for hero in (111, 123, 43, 7, 35, 9, 23, 85))
    assert any(r.code == 'conditional_farm_conflict' and set(r.hero_ids) == {81, 67}
               and r.scope == 'team' and r.polarity == 'neutral'
               for r in report.teams[Team.RADIANT].evaluation.reasons)


def test_symmetric_synergy_once_per_pair_and_directed_rule_keeps_direction() -> None:
    match = normalize_match_snapshot(fixture_snapshot())
    config = fixture_config()
    report = analyze_draft(match, config=config, matchups=stats_for(match))
    reasons = report.teams[Team.RADIANT].evaluation.reasons
    pair = [r for r in reasons if r.code == 'control_followup' and set(r.hero_ids) == {111, 123}]
    assert len(pair) == 1 and pair[0].hero_ids == (111, 123)
    synergy_codes = {rule.code for rule in config.rules if rule.kind == 'synergy'}
    numeric = [float(r.evidence['utility']) for r in reasons if r.code in synergy_codes and 'utility' in r.evidence]
    assert report.teams[Team.RADIANT].evaluation.axes['synergy'] == mean(numeric)
    directed = config.model_copy(update={'rules': tuple(
        rule.model_copy(update={'directionality': 'directed'}) if rule.code == 'control_followup' else rule
        for rule in config.rules)})
    other = analyze_draft(match, config=directed, matchups=stats_for(match))
    directions = {r.hero_ids for r in other.teams[Team.RADIANT].evaluation.reasons
                  if r.code == 'control_followup' and set(r.hero_ids) == {111, 123}}
    assert directions == {(111, 123), (123, 111)}
    assert other == analyze_draft(match, config=directed, matchups=stats_for(match))


def test_unknown_capabilities_do_not_create_negative_evidence() -> None:
    match = normalize_match_snapshot(independent_snapshot())
    report = analyze_draft(match, config=default_config(), matchups=stats_for(match))
    assert all(p.final_score is None for p in report.pick_events)
    assert all(not any(r.polarity == 'negative' and r.scope == 'team' for r in t.evaluation.reasons)
               for t in report.teams.values())
    assert any(r.code == 'capability_coverage_unknown' for t in report.teams.values() for r in t.evaluation.reasons)


def test_final_team_score_ignores_storage_order_of_roster() -> None:
    original = fixture_snapshot()
    reordered = deepcopy(original)
    reordered['match']['players'].reverse()
    first = normalize_match_snapshot(original)
    second = normalize_match_snapshot(reordered)
    config = fixture_config()
    first_report = analyze_draft(first, config=config, matchups=stats_for(first))
    second_report = analyze_draft(second, config=config, matchups=stats_for(second))
    assert first_report.teams == second_report.teams
    assert {p.hero_id: p.final_context for p in first_report.pick_events} == {
        p.hero_id: p.final_context for p in second_report.pick_events
    }
