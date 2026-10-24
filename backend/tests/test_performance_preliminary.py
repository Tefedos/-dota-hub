from copy import deepcopy
import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from app.models.matches import EvidenceStatus, FarmPositionEvidence, Team
from app.models.performance import PerformanceSignal, PlayerPerformance, PreliminarySelection, RuinerReport
from app.services.match_normalization import normalize_match_snapshot
from app.services.performance import analyze_performance, select_team
from app.services.performance_config import PerformanceConfig
from app.services.performance_preliminary import project_preliminary, select_preliminary
from test_performance import performance_snapshot, confirmed_positions, poor_core

FIXTURE = Path(__file__).parent / 'fixtures/performance/9057722463_ruiner_legacy.json'
SIGNAL = PerformanceSignal(code='relative_high:deaths_per_min', metric='deaths_per_min', value=1., reference=.5,
                           magnitude=1., text='Тестовое отклонение от медианы союзников.')


def members(scores: tuple[int | None, ...] = (50, 35, 10, 0, 0), team: Team = Team.RADIANT) -> tuple[PlayerPerformance, ...]:
    baseline = analyze_performance(normalize_match_snapshot(performance_snapshot()))
    return tuple(p.model_copy(update={'error_index': score, 'negative_signals': (SIGNAL,) if score else ()})
                 for p, score in zip((p for p in baseline.players if p.team == team), scores))


@pytest.mark.parametrize('scores,status,slots', [
    ((70, 50, 20, 0, 0), 'single', (0,)),  # RI-QA-01
    ((50, 35, 10, 0, 0), 'single', (0,)),  # RI-QA-02
    ((50, 36, 10, 0, 0), 'group', (0, 1)),  # RI-QA-03
    ((50, 45, 40, 20, 0), 'group', (0, 1, 2)),  # RI-QA-04
    ((50, 50, 10, 0, 0), 'group', (0, 1)),  # RI-QA-05
    ((0, 0, 0, 0, 0), 'none', ()),  # RI-QA-06
    ((50, 40, None, 0, 0), 'none', ()),  # RI-QA-07
    ((50, 36, 35, 0, 0), 'group', (0, 1)),  # RI-QA-09
    ((50, 36, 36, 0, 0), 'group', (0, 1, 2)),  # RI-QA-10
    ((50, 34, 10, 0, 0), 'single', (0,)),  # margin 16
    ((5, 4, 3, 2, 1), 'group', (0, 1, 2, 3, 4)),
    ((5, 4, 3, 2, 0), 'group', (0, 1, 2, 3)),
])
def test_selection_table(scores: tuple[int | None, ...], status: str, slots: tuple[int, ...]) -> None:
    players = members(scores)
    result = select_preliminary(players, Team.RADIANT)
    assert (result.status, result.player_slots) == (status, slots)
    assert result.confidence == 'low'
    assert 'leaver_context_unknown' in result.reason_codes
    assert 'roles_unknown' in result.reason_codes
    assert result == select_preliminary(tuple(reversed(players)), Team.RADIANT)
    assert result == PreliminarySelection.model_validate_json(result.model_dump_json())
    if status != 'none':
        assert scores[0] is not None and scores[1] is not None
        assert result.highest_index == scores[0] and result.margin == scores[0] - scores[1]
        assert result.leader_slot == (0 if status == 'single' else None)


@pytest.mark.parametrize('scores', [(50, 20, 10, 0, 0), (50, 50, 10, 0, 0)])
def test_missing_top_signal_refuses_including_ties(scores: tuple[int, ...]) -> None:
    players = list(members(scores))
    players[0] = players[0].model_copy(update={'negative_signals': ()})
    result = select_preliminary(tuple(players), Team.RADIANT)
    assert result.status == 'none' and result.reason_codes[0] == 'leader_signals_missing'  # RI-QA-08


def test_group_member_below_signal_display_threshold_is_included() -> None:
    players = list(members((50, 40, 0, 0, 0)))
    players[1] = players[1].model_copy(update={'negative_signals': ()})
    assert select_preliminary(tuple(players), Team.RADIANT).player_slots == (0, 1)


@pytest.mark.parametrize('change,reason', [
    ({'player_slot': 1}, 'invalid_roster'), ({'player_slot': 6}, 'invalid_roster'),
    ({'team': Team.DIRE}, 'invalid_roster'), ({'hero_id': None}, 'invalid_roster'),
    ({'hero_id': 2}, 'invalid_roster'), ({'error_index': None}, 'incomplete_player_scores'),
    ({'error_index': -1}, 'invalid_player_scores'), ({'error_index': 101}, 'invalid_player_scores'),
    ({'error_index': float('nan')}, 'invalid_player_scores'), ({'error_index': True}, 'invalid_player_scores'),
    ({'reason_codes': ('unsupported_game_mode',)}, 'blocking_player_context'),
])
def test_invalid_input_refusal(change: dict[str, Any], reason: str) -> None:
    players = list(members())
    players[0] = players[0].model_copy(update=change)
    assert select_preliminary(tuple(players), Team.RADIANT).reason_codes[0] == reason


def test_incomplete_team_and_leaver_evidence() -> None:
    players = members()
    assert select_preliminary(players[:4], Team.RADIANT).reason_codes[0] == 'incomplete_team'
    assert select_preliminary((), Team.RADIANT).status == 'none'
    assert select_preliminary(players, Team.RADIANT, leaver_context={4: True}).reason_codes[0] == 'confirmed_leaver'
    known = select_preliminary(players, Team.RADIANT, leaver_context=dict.fromkeys(range(5), False))
    assert known.status == 'single' and 'leaver_context_unknown' not in known.reason_codes
    invalid_contexts: list[dict[int, Any]] = [{128: True}, {0: 1}]
    for invalid in invalid_contexts:
        assert select_preliminary(players, Team.RADIANT, leaver_context=invalid).reason_codes[0] == 'invalid_leaver_context'


def test_roles_confidence_and_strict_selection_unchanged() -> None:
    players = members()
    assert select_team(players, Team.RADIANT, PerformanceConfig()).selection_status == 'no_confident_selection'
    estimated = tuple(p.model_copy(update={'position': FarmPositionEvidence(
        position=i+1, evidence=EvidenceStatus.ESTIMATED, source_field='position_est')}) for i, p in enumerate(players))
    assert 'roles_unconfirmed' in select_preliminary(estimated, Team.RADIANT).reason_codes
    snapshot = performance_snapshot()
    poor_core(snapshot)
    report = analyze_performance(normalize_match_snapshot(snapshot), positions=confirmed_positions(), selected_team=Team.RADIANT)
    assert report.summary.selection_status == 'selected'
    assert report.teams[Team.RADIANT].selection == select_team(tuple(p for p in report.players if p.team == Team.RADIANT), Team.RADIANT, PerformanceConfig())
    preliminary = report.teams[Team.RADIANT].preliminary_selection
    assert preliminary is not None and preliminary.confidence == 'medium'
    assert report.players[0].error_index == 98


def test_real_saved_report_projection_is_compatible_and_does_not_mutate() -> None:
    raw = json.loads(FIXTURE.read_text())
    before = deepcopy(raw)
    old = RuinerReport.model_validate_json(json.dumps(raw))
    assert all(t.preliminary_selection is None for t in old.teams.values())
    result = project_preliminary(old)
    radiant, dire = (result.teams[t].preliminary_selection for t in Team)
    assert radiant is not None and dire is not None
    assert (radiant.status, radiant.player_slots, radiant.highest_index, radiant.margin) == ('group', (0, 4), 50, 8)
    assert (dire.status, dire.player_slots, dire.leader_slot, dire.highest_index, dire.margin) == ('single', (131,), 131, 31, 25)
    assert raw == before
    dump = result.model_dump(mode='json')
    for row in dump['teams'].values():
        row.pop('preliminary_selection')
    assert dump == raw  # Every old field, including scores, signals, selections and config digest.
    assert project_preliminary(result) == result
    assert RuinerReport.model_validate_json(result.model_dump_json()) == result
    # Stored confirmed leaver refusal must not be replaced by an unknown-context projection.
    blocked = result.teams[Team.RADIANT].model_copy(update={'preliminary_selection': select_preliminary(
        tuple(p for p in result.players if p.team == Team.RADIANT), Team.RADIANT, leaver_context={0: True})})
    saved = result.model_copy(update={'teams': {**result.teams, Team.RADIANT: blocked}})
    assert project_preliminary(saved) == saved


def test_winner_opponents_and_match_id_do_not_change_selection() -> None:
    snapshot = performance_snapshot()
    poor_core(snapshot)
    first = analyze_performance(normalize_match_snapshot(snapshot))
    snapshot['match'].update(radiant_win=False, match_id=99999)
    for p in snapshot['match']['players'][5:]:
        p.update(kills=0, assists=0, deaths=50)
    second = analyze_performance(normalize_match_snapshot(snapshot))
    assert first.teams[Team.RADIANT] == second.teams[Team.RADIANT]
    assert first.players[:5] == second.players[:5]


def test_9051271323_all_existing_fields_remain_identical() -> None:
    root = Path(__file__).resolve().parents[2]
    evidence = json.loads((Path(__file__).parent / 'fixtures/draft/9051271323/evidence.json').read_text())
    report = analyze_performance(normalize_match_snapshot(evidence['snapshot']))
    baseline = json.loads((root / 'docs/audits/9051271323-ruiner-v1.json').read_text())
    output = report.model_dump(mode='json')
    for row in output['teams'].values():
        row.pop('preliminary_selection')
    # RI-02-FIX-01 changes diagnostics only: preserve the previously hidden
    # arithmetic ratio and identify why it cannot enter the participation axis.
    oracle = next(p for p in output['players'] if p['player_slot'] == 1)
    assert oracle['observed_metrics'].pop('kill_participation_counter_ratio') == 1.2
    oracle['reason_codes'] = [
        'team_kills_missing_small_or_inconsistent' if code == 'kill_participation_over_team_score_unverified' else code
        for code in oracle['reason_codes']
    ]
    assert output == baseline


@pytest.mark.parametrize('change', [
    {'status': 'single'}, {'reason_codes': ('not_a_reason',)},
    {'status': 'group', 'player_slots': (0, 128), 'highest_index': 50, 'margin': 0},
    {'status': 'single', 'player_slots': (0,), 'leader_slot': 0, 'highest_index': 50, 'margin': 14},
    {'highest_index': 0}, {'player_slots': (0,)}, {'reason_codes': ()},
])
def test_strict_dto_rejects_incoherent_states(change: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        PreliminarySelection(**{'reason_codes': ('incomplete_team',), **change})
