"""Synthetic 10-player fixtures; no live match/statistics presented as real evidence."""
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from app.integrations.opendota import parse_match_response
from app.integrations.opendota_matchups import MatchupBatch, MatchupStat
from app.models.matches import NormalizedMatch, Team
from app.services.draft.analyzer import analyze_draft
from app.services.draft.config import DraftConfig, VisibilityPolicy, default_config
from app.services.draft.scoring import matchup, applicable_profiles
from app.services.match_normalization import normalize_match_snapshot

# One coherent All Pick fixture: 2+2, 2+2, 1+1. Position knowledge intentionally absent.
ORDER = ((111, 0), (123, 0), (5, 1), (25, 1), (81, 0), (43, 0), (1, 1), (27, 1), (67, 0), (7, 1))


def fixture_snapshot() -> dict[str, Any]:
    players = []
    for side in (0, 1):
        for index, (hero, _) in enumerate(pair for pair in ORDER if pair[1] == side):
            players.append({'hero_id': hero, 'player_slot': side * 128 + index,
                            'kills': 0, 'deaths': 0, 'assists': 0})
    return {
        'schema_version': 1, 'source': 'opendota', 'source_fetched_at': '2026-10-22T11:00:00+00:00',
        'match': {'match_id': 9223372036854775807, 'duration': 2400, 'patch': 60, 'game_mode': 22,
                  'players': players, 'radiant_win': True, 'radiant_score': 40, 'dire_score': 10,
                  'picks_bans': [{'hero_id': h, 'team': t, 'order': i, 'is_pick': True}
                                 for i, (h, t) in enumerate(ORDER)]},
    }


def fixture_config(kind: str = 'hidden_221') -> DraftConfig:
    # Explicitly a test-only verification, never represented as verified production policy for patch 60.
    policy = VisibilityPolicy.model_validate({
        'name': 'fixture-only-visibility', 'game_mode': 22, 'patches': (60,), 'kind': kind,
        'source_refs': ('fixture://visibility-contract',),
    })
    base = default_config()
    # Synthetic patch evidence: exercises numeric rules without claiming production patch verification.
    return base.model_copy(update={
        'policies': (policy,),
        'profiles': tuple(p.model_copy(update={'verified_numeric_patches': (60,),
                                              'source_refs': ('fixture://verified-capabilities',)}) for p in base.profiles),
        'rules': tuple(r.model_copy(update={'verified_numeric_patches': (60,),
                                           'source_refs': ('fixture://verified-interaction',)}) for r in base.rules),
    })


def stats_for(match: NormalizedMatch, games: int = 1000) -> tuple[MatchupBatch, ...]:
    return tuple(MatchupBatch(hero_id=p.hero_id, status='ok', rows=tuple(
        MatchupStat(hero_id=p.hero_id, opponent_id=e.hero_id, games_played=games, wins=games // 2,
                    source_ref=f'fixture://matchups/{p.hero_id}', fetched_at=datetime(2026, 10, 22, tzinfo=UTC))
        for e in match.players if e.hero_id is not None and e.team != p.team
    )) for p in match.players if p.hero_id is not None)


def test_ten_heroes_both_teams_and_hidden_round_visibility() -> None:
    match = normalize_match_snapshot(fixture_snapshot())
    report = analyze_draft(match, config=fixture_config(), matchups=stats_for(match))
    assert report.mode == 'SEQUENTIAL' and len(report.pick_events) == 10
    assert set(report.teams) == {Team.RADIANT, Team.DIRE}
    hoodwink = next(p for p in report.pick_events if p.hero_id == 123)
    maiden = next(p for p in report.pick_events if p.hero_id == 5)
    assert hoodwink.visibility.own_known_picks_before == (111,)
    assert maiden.visibility.enemy_revealed_before == ()  # Earlier order but same hidden round!
    ck = next(p for p in report.pick_events if p.hero_id == 81)
    assert ck.stage == 2 and ck.visibility.enemy_revealed_before == (5, 25)
    assert ck.visibility.own_known_picks_before == (111, 123)
    spectre = next(p for p in report.pick_events if p.hero_id == 67)
    assert spectre.stage == 3 and 7 not in spectre.visibility.enemy_revealed_before
    assert any(r.code == 'conditional_farm_conflict' and r.confidence == 'low' for r in ck.resource_warnings)
    assert any(r.code == 'save_sustained' for r in ck.ally_synergies)
    for p in report.pick_events:
        assert p.final_score is None or 0 <= p.final_score <= 100
        assert len(p.pros) <= 2 and len(p.cons) <= 2
    assert sum(p.final_score is not None for p in report.pick_events) == 8
    assert next(p for p in report.pick_events if p.hero_id == 1).final_score is None
    for t in report.teams.values():
        assert t.evaluation.score is not None
        assert t.breakdown['laning'] is None and t.breakdown['farm_economy'] is None
        assert t.team_win_conditions


def test_late_earthshaker_changes_final_not_ck_at_pick() -> None:
    original = fixture_snapshot()
    alternate = deepcopy(original)
    alternate['match']['players'][-1]['hero_id'] = 29
    alternate['match']['picks_bans'][-1]['hero_id'] = 29
    # Remove AoE from the alternative in this counterfactual fixture, keeping all other capabilities.
    config = fixture_config()
    config = config.model_copy(update={'profiles': tuple(
        p.model_copy(update={'tags': tuple(t for t in p.tags if t != 'aoe')}) if p.hero_id == 29 else p
        for p in config.profiles)})
    a, b = normalize_match_snapshot(original), normalize_match_snapshot(alternate)
    first = analyze_draft(a, config=config, matchups=stats_for(a))
    second = analyze_draft(b, config=config, matchups=stats_for(b))
    ck1 = next(p for p in first.pick_events if p.hero_id == 81)
    ck2 = next(p for p in second.pick_events if p.hero_id == 81)
    assert ck1.at_pick_score is not None
    assert ck1.at_pick == ck2.at_pick
    assert ck1.final_score is not None and ck2.final_score is not None
    assert ck1.final_score < ck2.final_score
    assert 7 in ck1.threatened_by_heroes
    later = next(r for r in ck1.later_revealed_counters if r.hero_id == 7)
    assert later.score_delta is not None and later.score_delta < 0
    assert all(7 not in r.hero_ids for r in ck1.at_pick.reasons)


def test_same_round_cannot_be_called_later_counterpick() -> None:
    match = normalize_match_snapshot(fixture_snapshot())
    result = analyze_draft(match, config=fixture_config(), matchups=stats_for(match))
    spectre = next(p for p in result.pick_events if p.hero_id == 67)
    assert 7 in spectre.threatened_by_heroes
    assert all(l.hero_id != 7 for l in spectre.later_revealed_counters)


def test_final_only_with_null_picks_has_identical_final_evaluations() -> None:
    snapshot = fixture_snapshot()
    match = normalize_match_snapshot(snapshot)
    full = analyze_draft(match, config=fixture_config(), matchups=stats_for(match))
    snapshot['match']['picks_bans'] = None
    final = analyze_draft(normalize_match_snapshot(snapshot), config=fixture_config(), matchups=stats_for(match))
    assert final.mode == 'FINAL_ONLY' and len(final.pick_events) == 10
    assert final.teams == full.teams
    assert {p.hero_id: p.final_context for p in final.pick_events} == {p.hero_id: p.final_context for p in full.pick_events}
    for pick in final.pick_events:
        assert pick.action_order is None and pick.stage is None and pick.at_pick_score is None
        assert not pick.later_revealed_counters


@pytest.mark.parametrize('problem', ['duplicate', 'partial', 'gap', 'wrong_team', 'wrong_hero', 'invalid_round', 'huge_order', 'ban_conflict'])
def test_bad_order_falls_back_without_losing_actions(problem: str) -> None:
    snapshot = fixture_snapshot()
    actions = snapshot['match']['picks_bans']
    if problem == 'duplicate':
        actions[1]['order'] = 0
    elif problem == 'partial':
        actions.pop()
    elif problem == 'gap':
        actions[-1]['order'] = 11
    elif problem == 'huge_order':
        actions[-1]['order'] = 9223372036854775807
    elif problem == 'wrong_team':
        actions[0]['team'] = 1
    elif problem == 'wrong_hero':
        actions[0]['hero_id'] = 99999
    elif problem == 'ban_conflict':
        actions[0]['is_pick'] = False
    else:
        actions[2]['order'], actions[4]['order'] = actions[4]['order'], actions[2]['order']
    match = normalize_match_snapshot(snapshot)
    report = analyze_draft(match, config=fixture_config())
    assert report.mode == 'FINAL_ONLY' and len(report.actions) == len(actions)
    assert all(p.at_pick_score is None for p in report.pick_events)


def test_unique_out_of_order_array_sorted_by_valid_order_source_index_preserved() -> None:
    snapshot = fixture_snapshot()
    snapshot['match']['picks_bans'].reverse()
    report = analyze_draft(normalize_match_snapshot(snapshot), config=fixture_config())
    assert report.mode == 'SEQUENTIAL'
    assert [a.order for a in report.actions] == list(range(10))
    assert report.actions[0].source_order == 9


def test_public_policy_neutral_sequence_has_no_invented_cm_stage() -> None:
    match = normalize_match_snapshot(fixture_snapshot())
    report = analyze_draft(match, config=fixture_config('public_sequence'))
    assert report.pick_events[2].visibility.enemy_revealed_before == (111, 123)
    assert all(p.stage is None for p in report.pick_events)


def test_default_only_enables_exact_verified_mode_patch_and_cm_falls_back() -> None:
    snapshot = fixture_snapshot()
    config = default_config()
    report = analyze_draft(normalize_match_snapshot(snapshot), config=config)
    assert report.mode == 'FINAL_ONLY'  # Modern RAP rules not assumed from a 2020 patch.
    snapshot['match']['patch'] = 46
    assert analyze_draft(normalize_match_snapshot(snapshot), config=config).mode == 'SEQUENTIAL'
    snapshot['match']['game_mode'] = 2
    assert analyze_draft(normalize_match_snapshot(snapshot), config=config).mode == 'FINAL_ONLY'


@pytest.mark.parametrize('problem', ['patch_none', 'unknown_patch', 'unknown_heroes', 'no_roster'])
def test_missing_evidence_never_returns_fake_fifty(problem: str) -> None:
    snapshot = fixture_snapshot()
    if problem == 'patch_none':
        snapshot['match']['patch'] = None
    elif problem == 'unknown_patch':
        snapshot['match']['patch'] = 99999
    elif problem == 'unknown_heroes':
        for p in snapshot['match']['players']:
            p['hero_id'] += 10000
    else:
        snapshot['match']['players'] = []
    report = analyze_draft(normalize_match_snapshot(snapshot))
    assert report.draft_advantage == 'insufficient_data'
    for pick in report.pick_events:
        assert pick.final_score is None
        assert pick.final_context.confidence == 'low'
        assert 'insufficient_data' in {r.code for r in pick.final_context.reasons}
    assert all(t.evaluation.score is None for t in report.teams.values())


def test_matchup_sample_smoothing_and_no_causal_label_from_winrate() -> None:
    config = fixture_config()
    small = MatchupStat(hero_id=81, opponent_id=25, games_played=10, wins=10,
                        source_ref='fixture://small', fetched_at=datetime(2026, 1, 1, tzinfo=UTC))
    value, reasons = matchup(81, 25, applicable_profiles(config, 60), 60, {(81, 25): small}, config)
    assert value is None and reasons[0].code == 'small_matchup_sample'
    large = small.model_copy(update={'games_played': 1000, 'wins': 800})
    value, reasons = matchup(81, 25, {}, None, {(81, 25): large}, config)
    assert value is not None and 50 < value < 80
    assert all(r.kind != 'mechanic' for r in reasons)
    assert reasons[0].patch_applicability == 'aggregate_unknown'


def test_outcome_kda_lane_gold_duration_do_not_affect_draft_report_and_no_mutation() -> None:
    snapshot = fixture_snapshot()
    original = deepcopy(snapshot)
    match = normalize_match_snapshot(snapshot)
    config = fixture_config()
    before = analyze_draft(match, config=config, matchups=stats_for(match))
    snapshot['match'].update(radiant_win=False, radiant_score=0, dire_score=999, duration=9000)
    for p in snapshot['match']['players']:
        p.update(kills=500, deaths=800, assists=300, net_worth=999999, lane_role=2)
    changed = normalize_match_snapshot(snapshot)
    after = analyze_draft(changed, config=config, matchups=stats_for(changed))
    assert before.model_dump_json() == after.model_dump_json()
    assert before.model_dump_json() == analyze_draft(match, config=config, matchups=stats_for(match)).model_dump_json()
    assert original == fixture_snapshot()
    assert match.model_dump_json() == normalize_match_snapshot(original).model_dump_json()


def test_config_rejects_missing_weights_and_ambiguous_policies() -> None:
    config = fixture_config()
    data = config.model_dump()
    data['weights'] = {'matchup': 1.}
    with pytest.raises(ValidationError):
        DraftConfig.model_validate(data)
    data = config.model_dump()
    data['policies'] = (*data['policies'], *data['policies'])
    with pytest.raises(ValidationError):
        DraftConfig.model_validate(data)


def test_fixture_pipeline_opendota_snapshot_normalization_report_preserves_bans() -> None:
    payload = fixture_snapshot()['match']
    for action in payload['picks_bans']:
        action['order'] += 1
    payload['picks_bans'].insert(0, {'hero_id': 29, 'team': 0, 'is_pick': False, 'order': 0})
    response = parse_match_response(payload['match_id'], payload, datetime(2026, 10, 22, tzinfo=UTC))
    assert response.snapshot is not None
    snapshot_before = deepcopy(response.snapshot)
    match = normalize_match_snapshot(response.snapshot)
    report = analyze_draft(match, config=fixture_config(), matchups=stats_for(match))
    assert report.mode == 'SEQUENTIAL' and len(report.actions) == 11 and len(report.pick_events) == 10
    assert report.pick_events[0].visibility.bans_known_before == (29,)
    assert response.snapshot == snapshot_before
