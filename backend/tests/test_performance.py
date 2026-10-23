from copy import deepcopy
import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from app.models.matches import EvidenceStatus, FarmPositionEvidence, PlayerField, Team
from app.models.performance import RuinerReport
from app.services.match_normalization import normalize_match_snapshot
from app.services.performance import analyze_performance, select_team, format_performance_summary
from app.services.performance_config import PerformanceConfig


def performance_snapshot() -> dict[str, Any]:
    players = []
    for side in (0, 128):
        for i in range(5):
            core = i < 3
            players.append({'player_slot': side+i, 'hero_id': side+i+1, 'kills': 5 if core else 2,
                            'assists': 10 if core else 18, 'deaths': 5, 'gold_per_min': 600 if core else 250,
                            'xp_per_min': 650 if core else 400, 'hero_damage': 20000 if core else 6000,
                            'tower_damage': 2000 if core else 100, 'hero_healing': 0 if core else 1000,
                            'obs_placed': 0 if core else 8, 'sen_placed': 0 if core else 12,
                            'observer_kills': 0 if core else 2, 'sentry_kills': 0 if core else 3})
    return {'schema_version': 1, 'source': 'opendota', 'source_fetched_at': '2026-10-22T11:00:00+00:00',
            'match': {'match_id': 12345, 'duration': 2400, 'game_mode': 22, 'patch': 60,
                      'radiant_score': 30, 'dire_score': 30, 'radiant_win': True, 'players': players}}


def confirmed_positions() -> dict[int, FarmPositionEvidence]:
    return {side+i: FarmPositionEvidence(position=i+1, evidence=EvidenceStatus.CONFIRMED,
                                         source_field='fixture://confirmed-team-assignments')
            for side in (0, 128) for i in range(5)}


def poor_core(snapshot: dict[str, Any]) -> None:
    snapshot['match']['players'][0].update(deaths=50, kills=0, assists=0, gold_per_min=50,
                                          xp_per_min=50, hero_damage=0)


def test_both_teams_ten_players_deterministic_json_no_mutation() -> None:
    snapshot = performance_snapshot()
    before = deepcopy(snapshot)
    match = normalize_match_snapshot(snapshot)
    report = analyze_performance(match, positions=confirmed_positions())
    assert len(report.players) == 10 and set(report.teams) == set(Team)
    assert report.model_version == 'ruiner_v1' and report.quality == 'sufficient'
    assert report == analyze_performance(match, positions=confirmed_positions())
    assert report == RuinerReport.model_validate_json(report.model_dump_json())
    assert before == snapshot
    assert all(p.error_index == 0 for p in report.players)  # Equal observations: no relative deficits.
    assert report.summary.selected_team is None
    assert all(t.selection.selection_status == 'no_confident_selection' for t in report.teams.values())


def test_support_low_gpm_with_healing_and_assists_is_not_penalized_as_core() -> None:
    snapshot = performance_snapshot()
    snapshot['match']['players'][3].update(gold_per_min=30, xp_per_min=80, hero_healing=9000, assists=28)
    report = analyze_performance(normalize_match_snapshot(snapshot), positions=confirmed_positions())
    support = report.players[3]
    assert support.error_index == 0 and support.role_group == 'support'
    assert 'economy' not in support.axes
    assert any(s.metric == 'healing_per_min' for s in support.positive_signals)
    assert any(s.metric == 'kill_participation' for s in support.positive_signals)
    assert not any(s.metric in {'gpm', 'xpm'} for s in support.negative_signals)


def test_low_core_economy_is_compared_only_with_same_team_cores() -> None:
    snapshot = performance_snapshot()
    snapshot['match']['players'][0].update(gold_per_min=100, xp_per_min=100)
    report = analyze_performance(normalize_match_snapshot(snapshot), positions=confirmed_positions())
    core = report.players[0]
    assert core.error_index is not None and core.error_index > 0
    signal = next(s for s in core.negative_signals if s.metric == 'gpm')
    assert signal.reference == 600 and signal.comparison_slots == (1, 2)
    assert report.teams[Team.RADIANT].selection.selection_status == 'no_confident_selection'


@pytest.mark.parametrize('variant', ['missing', 'lane_only', 'estimated'])
def test_unconfirmed_position_never_confidently_selects(variant: str) -> None:
    snapshot = performance_snapshot()
    poor_core(snapshot)
    for p in snapshot['match']['players']:
        if variant == 'lane_only':
            p['lane_role'] = 1
        if variant == 'estimated':
            p['position_est'] = p['player_slot'] % 128 + 1
    report = analyze_performance(normalize_match_snapshot(snapshot), selected_team=Team.RADIANT)
    assert report.quality == 'partial'
    assert all(p.confidence == 'low' for p in report.players)
    assert report.summary.selection_status == 'no_confident_selection'
    if variant != 'estimated':
        assert all(p.role_group == 'unknown' and 'economy' not in p.axes for p in report.players)


def test_no_role_no_farm_inference_from_hero_or_gpm() -> None:
    first = performance_snapshot()
    other = deepcopy(first)
    for p in other['match']['players']:
        p.update(hero_id=p['hero_id']+5000, gold_per_min=0, xp_per_min=0)
    a = analyze_performance(normalize_match_snapshot(first))
    b = analyze_performance(normalize_match_snapshot(other))
    assert [p.error_index for p in a.players] == [p.error_index for p in b.players]
    assert all(p.position.position is None for p in b.players)


@pytest.mark.parametrize('mode', [None, 0, 23, 999])
def test_unsupported_modes_are_explicitly_unscored(mode: int | None) -> None:
    snapshot = performance_snapshot()
    snapshot['match']['game_mode'] = mode
    report = analyze_performance(normalize_match_snapshot(snapshot), positions=confirmed_positions())
    assert all(p.error_index is None and 'unsupported_game_mode' in p.reason_codes for p in report.players)
    assert report.quality == 'insufficient'


@pytest.mark.parametrize('duration', [None, 1, 899])
def test_short_or_missing_duration_never_amplifies_rates_into_scores(duration: int | None) -> None:
    snapshot = performance_snapshot()
    snapshot['match']['duration'] = duration
    report = analyze_performance(normalize_match_snapshot(snapshot), positions=confirmed_positions())
    assert all(p.error_index is None for p in report.players)


def test_duration_gate_boundary_and_outlier_fifty_deaths_is_bounded() -> None:
    snapshot = performance_snapshot()
    snapshot['match']['duration'] = 900
    snapshot['match']['players'][0]['deaths'] = 50
    report = analyze_performance(normalize_match_snapshot(snapshot), positions=confirmed_positions())
    core = report.players[0]
    assert core.axes['survival'] == 1
    assert core.error_index is not None and 0 < core.error_index < 70
    assert report.teams[Team.RADIANT].selection.selection_status == 'no_confident_selection'


@pytest.mark.parametrize('total', [None, 0, 1, 9])
def test_absent_small_team_kill_totals_disable_participation(total: int | None) -> None:
    snapshot = performance_snapshot()
    snapshot['match']['radiant_score'] = total
    report = analyze_performance(normalize_match_snapshot(snapshot))
    assert all(p.error_index is None and p.axes['participation'] is None for p in report.players if p.team == Team.RADIANT)


def test_zero_kills_zero_deaths_and_inconsistent_participation_are_safe() -> None:
    snapshot = performance_snapshot()
    snapshot['match']['radiant_score'] = 0
    for p in snapshot['match']['players']:
        p.update(kills=0, deaths=0, assists=0)
    report = analyze_performance(normalize_match_snapshot(snapshot))
    assert all(p.error_index is None and p.observed_metrics['kda'] is None for p in report.players)
    assert 'NaN' not in report.model_dump_json() and 'Infinity' not in report.model_dump_json()
    snapshot = performance_snapshot()
    snapshot['match']['players'][0]['assists'] = 10000
    player = analyze_performance(normalize_match_snapshot(snapshot)).players[0]
    assert player.observed_metrics['kill_participation'] is None and player.error_index is None


def test_missing_wards_unparsed_match_and_missing_damage_do_not_imply_zero() -> None:
    snapshot = performance_snapshot()
    for p in snapshot['match']['players']:
        for key in ('hero_damage', 'obs_placed', 'sen_placed', 'observer_kills', 'sentry_kills'):
            p.pop(key)
    report = analyze_performance(normalize_match_snapshot(snapshot), positions=confirmed_positions())
    assert all(p.error_index != 100 and 'obs_placed' in p.missing_metrics for p in report.players)
    assert all('hero_damage_per_min' in p.missing_metrics for p in report.players)
    assert all(not any(s.metric == 'obs_placed' for s in p.negative_signals) for p in report.players)
    assert report.players[0].axes['impact'] is None


def test_completely_missing_stats_produce_null_and_no_selected_player() -> None:
    snapshot = performance_snapshot()
    snapshot['match']['players'] = [{'hero_id': p['hero_id'], 'player_slot': p['player_slot']} for p in snapshot['match']['players']]
    report = analyze_performance(normalize_match_snapshot(snapshot), positions=confirmed_positions())
    assert len(report.players) == 10 and all(p.error_index is None for p in report.players)
    assert report.summary.selection_status == 'no_confident_selection'


def test_winner_draft_and_opponent_performance_do_not_drive_own_scores() -> None:
    snapshot = performance_snapshot()
    original = analyze_performance(normalize_match_snapshot(snapshot), positions=confirmed_positions())
    snapshot['match'].update(radiant_win=False, picks_bans=[{'hero_id': 999, 'is_pick': True}],
                             draft_report={'teams': {'radiant': {'score': 0}, 'dire': {'score': 100}}})
    assert original == analyze_performance(normalize_match_snapshot(snapshot), positions=confirmed_positions())
    for p in snapshot['match']['players'][5:]:
        p.update(gold_per_min=100000, hero_damage=999999, deaths=50)
    changed = analyze_performance(normalize_match_snapshot(snapshot), positions=confirmed_positions())
    assert original.players[:5] == changed.players[:5]
    assert original.teams[Team.RADIANT] == changed.teams[Team.RADIANT]


def test_selection_is_team_scoped_and_never_assumes_our_team() -> None:
    snapshot = performance_snapshot()
    poor_core(snapshot)
    match = normalize_match_snapshot(snapshot)
    report = analyze_performance(match, positions=confirmed_positions())
    selection = report.teams[Team.RADIANT].selection
    assert selection.selection_status == 'selected' and selection.selected_player_slot == 0
    assert report.summary.selected_team is None and report.summary.selection_status == 'no_confident_selection'
    assert analyze_performance(match, positions=confirmed_positions(), selected_team=Team.RADIANT).summary == selection
    assert analyze_performance(match, positions=confirmed_positions(), selected_team=Team.DIRE).summary.selected_player_slot is None
    text = format_performance_summary(report)
    assert 'Radiant' in text and 'Dire' in text and 'наша' not in text and 'виновен' not in text


def test_selection_threshold_margin_ties_and_independent_axes() -> None:
    config = PerformanceConfig()
    snapshot = performance_snapshot()
    poor_core(snapshot)
    report = analyze_performance(normalize_match_snapshot(snapshot), positions=confirmed_positions())
    members = tuple(p for p in report.players if p.team == Team.RADIANT)
    def select(score: int, second: int = 0, one_axis: bool = False) -> str:
        first = members[0].model_copy(update={'error_index': score, **({'axes': {'survival': 1., 'participation': 0.}} if one_axis else {})})
        runner = members[1].model_copy(update={'error_index': second})
        return select_team((first, runner, *members[2:]), Team.RADIANT, config).selection_status
    assert select(69) == 'no_confident_selection'
    assert select(70) == 'selected'
    assert select(70, 55) == 'selected'
    assert select(70, 56) == 'no_confident_selection'
    assert select(70, 70) == 'no_confident_selection'
    assert select(100, one_axis=True) == 'no_confident_selection'


def test_conflicting_roles_incomplete_roster_and_invalid_evidence() -> None:
    snapshot = performance_snapshot()
    positions = confirmed_positions()
    positions[1] = positions[0]
    report = analyze_performance(normalize_match_snapshot(snapshot), positions=positions)
    assert all('conflicting_positions' in p.reason_codes for p in report.players[:5])
    snapshot['match']['players'].pop(0)
    report = analyze_performance(normalize_match_snapshot(snapshot))
    assert len(report.players) == 9
    assert all(p.error_index is None for p in report.players if p.team == Team.RADIANT)
    with pytest.raises(ValueError):
        analyze_performance(normalize_match_snapshot(snapshot), positions=confirmed_positions())
    with pytest.raises(ValidationError):
        FarmPositionEvidence(position=1)


def test_normalizer_wards_and_estimated_position_validate_and_preserve_zero() -> None:
    snapshot = performance_snapshot()
    p = snapshot['match']['players'][0]
    p.update(obs_placed=0, sen_placed=True, observer_kills=-1, sentry_kills=2.5, position_est=4, lane_role=1)
    player = normalize_match_snapshot(snapshot).players[0]
    assert player.obs_placed == 0 and PlayerField.OBS_PLACED in player.available_fields
    assert player.sen_placed is None and player.observer_kills is None and player.sentry_kills is None
    assert player.performance_position.position == 4 and player.performance_position.evidence == EvidenceStatus.ESTIMATED
    assert player.position.source_field == 'lane_role'


def test_config_rejects_bad_weights_and_thresholds() -> None:
    with pytest.raises(ValidationError):
        PerformanceConfig(core_weights={'survival': 1.})
    with pytest.raises(ValidationError):
        PerformanceConfig(selection_threshold=101)
    with pytest.raises(ValidationError):
        PerformanceConfig(fallback_weights={'survival': float('nan'), 'participation': .5})


def test_saved_real_match_offline_snapshot_to_performance() -> None:
    evidence = json.loads((Path(__file__).parent / 'fixtures/draft/9051271323/evidence.json').read_text())
    report = analyze_performance(normalize_match_snapshot(evidence['snapshot']))
    assert report.match_id == '9051271323' and len(report.players) == 10
    assert all(p.confidence == 'low' for p in report.players)
    assert all(t.selection.selection_status == 'no_confident_selection' for t in report.teams.values())


def test_zero_reference_does_not_invent_large_credit_from_one_unit_of_healing() -> None:
    snapshot = performance_snapshot()
    poor_core(snapshot)
    before = analyze_performance(normalize_match_snapshot(snapshot), positions=confirmed_positions())
    snapshot['match']['players'][0]['hero_healing'] = 1
    after = analyze_performance(normalize_match_snapshot(snapshot), positions=confirmed_positions())
    assert before.players[0].error_index == after.players[0].error_index
    assert after.players[0].positive_credit == 0
    assert any(s.code == 'observed_contribution:healing_per_min' and s.magnitude == 0 for s in after.players[0].positive_signals)


def test_extreme_positive_contributions_are_capped_and_not_added_repeatedly() -> None:
    snapshot = performance_snapshot()
    poor_core(snapshot)
    for player in snapshot['match']['players'][:3]:
        player.update(hero_healing=1000, obs_placed=5, observer_kills=5)
    before = analyze_performance(normalize_match_snapshot(snapshot), positions=confirmed_positions()).players[0]
    snapshot['match']['players'][0].update(hero_healing=2**63-1, obs_placed=2**63-1, observer_kills=2**63-1)
    after = analyze_performance(normalize_match_snapshot(snapshot), positions=confirmed_positions()).players[0]
    assert after.positive_credit == PerformanceConfig().maximum_positive_credit
    assert before.error_index is not None and after.error_index is not None
    assert 0 <= before.error_index - after.error_index <= 15


def test_empty_roster_has_both_teams_and_no_fabricated_players() -> None:
    snapshot = performance_snapshot()
    snapshot['match']['players'] = []
    report = analyze_performance(normalize_match_snapshot(snapshot))
    assert not report.players and set(report.teams) == set(Team)
    assert report.quality == 'insufficient' and report.summary.selected_player_slot is None


def test_low_missing_metrics_are_not_replaced_by_zero_penalties() -> None:
    snapshot = performance_snapshot()
    snapshot['match']['players'][0]['gold_per_min'] = None
    player = analyze_performance(normalize_match_snapshot(snapshot), positions=confirmed_positions()).players[0]
    assert player.observed_metrics['gpm'] is None and player.axes['economy'] is None
    assert 'gpm' in player.missing_metrics and player.error_index == 0
    assert not any(s.metric == 'gpm' for s in player.negative_signals)
