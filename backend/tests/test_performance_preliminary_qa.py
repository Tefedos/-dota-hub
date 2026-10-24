"""Independent RI-04 QA checks. No production data, OpenDota request or migration."""
import asyncio
from copy import deepcopy
import json
from pathlib import Path
from typing import Any, cast

import pytest
from pydantic import ValidationError
from pydantic import SecretStr
from httpx import ASGITransport, AsyncClient

from app.models.matches import Team
from app.models.performance import PreliminarySelection, RuinerReport
from app.db.session import Database
from app.core.config import Settings
from app.main import create_app
from app.services.match_analysis import MatchAnalysisService, SECTION_VERSIONS, get_analysis
from app.services.performance_preliminary import project_preliminary, select_preliminary
from test_group_flow import MATCH_ID, Provider, client, flow
from test_performance_preliminary import members

LIVE_FIXTURE = Path(__file__).parent / 'fixtures/performance/9051271323_live_ri04_envelope.json'


@pytest.mark.parametrize('case,scores,status,slots,margin,reason', [
    ('RI-QA-01', (70, 50, 20, 0, 0), 'single', (0,), 20, 'highest_relative_index'),
    ('RI-QA-02', (50, 35, 10, 0, 0), 'single', (0,), 15, 'highest_relative_index'),
    ('RI-QA-03', (50, 36, 10, 0, 0), 'group', (0, 1), 14, 'close_scores'),
    ('RI-QA-04', (50, 45, 40, 20, 0), 'group', (0, 1, 2), 5, 'close_scores'),
    ('RI-QA-05', (50, 50, 10, 0, 0), 'group', (0, 1), 0, 'close_scores'),
    ('RI-QA-06', (0, 0, 0, 0, 0), 'none', (), None, 'all_indices_zero'),
    ('RI-QA-07', (50, 40, None, 0, 0), 'none', (), None, 'incomplete_player_scores'),
    ('RI-QA-09', (50, 36, 35, 0, 0), 'group', (0, 1), 14, 'close_scores'),
    ('RI-QA-10', (50, 36, 36, 0, 0), 'group', (0, 1, 2), 14, 'close_scores'),
    ('RI-QA-11', (50, 34, 10, 0, 0), 'single', (0,), 16, 'highest_relative_index'),
    ('RI-QA-12', (50, 49, 48, 47, 46), 'group', (0, 1, 2, 3, 4), 1, 'close_scores'),
])
def test_qa_decision_table(
    case: str, scores: tuple[int | None, ...], status: str, slots: tuple[int, ...],
    margin: int | None, reason: str,
) -> None:
    players = members(scores)
    original = tuple(player.model_dump_json() for player in players)
    result = select_preliminary(players, Team.RADIANT)
    assert (result.status, result.player_slots, result.margin, result.reason_codes[0]) == (status, slots, margin, reason), case
    assert result.highest_index == (None if status == 'none' else scores[0]), case
    assert result.leader_slot == (0 if status == 'single' else None), case
    assert result.confidence == 'low' and 'roles_unknown' in result.reason_codes and 'leaver_context_unknown' in result.reason_codes
    assert tuple(player.model_dump_json() for player in players) == original
    assert select_preliminary(tuple(reversed(players)), Team.RADIANT) == result


def test_qa_08_missing_top_signal_is_none() -> None:
    players = list(members((50, 20, 10, 0, 0)))
    players[0] = players[0].model_copy(update={'negative_signals': ()})
    result = select_preliminary(tuple(players), Team.RADIANT)
    assert (result.status, result.player_slots, result.leader_slot, result.highest_index, result.margin) == ('none', (), None, None, None)
    assert result.reason_codes[0] == 'leader_signals_missing'


def test_live_saved_9051271323_matches_api_and_new_projection() -> None:
    envelope = json.loads(LIVE_FIXTURE.read_text())
    assert envelope['status'] == 'ready' and envelope['match_id'] == '9051271323'
    original = deepcopy(envelope)
    data = envelope['data']
    report = RuinerReport.model_validate_json(json.dumps(data))
    expected = {
        Team.RADIANT: ([None, None, 12, 6, 15], 'none', [], None, None, None,
                       ('incomplete_player_scores', 'roles_unconfirmed', 'leaver_context_unknown')),
        Team.DIRE: ([12, 15, 0, 9, 35], 'single', [132], 132, 35, 20,
                    ('highest_relative_index', 'roles_unconfirmed', 'leaver_context_unknown')),
    }
    for side, (scores, status, slots, leader, highest, margin, reasons) in expected.items():
        players = tuple(p for p in report.players if p.team == side)
        assert [p.error_index for p in players] == scores
        actual = report.teams[side].preliminary_selection
        assert actual is not None
        assert (actual.status, list(actual.player_slots), actual.leader_slot, actual.highest_index, actual.margin,
                actual.reason_codes) == (status, slots, leader, highest, margin, reasons)
        assert actual.confidence == 'low' and actual.projection_version == 'ri_preliminary_v1'
        assert select_preliminary(players, side) == actual
        assert report.teams[side].selection.selection_status == 'no_confident_selection'
        assert all(p.position.evidence.value == 'estimated' for p in players)
    assert project_preliminary(report) == report
    assert RuinerReport.model_validate_json(report.model_dump_json()) == report
    assert envelope == original


async def test_two_team_projections_are_pure_under_concurrency() -> None:
    left = members((50, 35, 10, 0, 0))
    right = members((31, 6, 0, 0, 0), Team.DIRE)
    jobs = [asyncio.to_thread(select_preliminary, left if i % 2 == 0 else right,
                              Team.RADIANT if i % 2 == 0 else Team.DIRE) for i in range(32)]
    results = await asyncio.gather(*jobs)
    assert all(result == results[i % 2] for i, result in enumerate(results))
    assert results[0].player_slots == (0,) and results[1].player_slots == (128,)


def test_existing_projection_rejects_semantically_inconsistent_confidence_and_reason() -> None:
    legacy = Path(__file__).parent / 'fixtures/performance/9057722463_ruiner_legacy.json'
    report = project_preliminary(RuinerReport.model_validate_json(legacy.read_text()))
    row = report.teams[Team.RADIANT]
    assert row.preliminary_selection is not None
    wrong = row.preliminary_selection.model_copy(update={
        'confidence': 'medium', 'reason_codes': ('incomplete_player_scores',),
    })
    # Strict DTO currently validates shape but accepts a group claiming incomplete scores
    # and medium confidence although all five players are low confidence.
    parsed = PreliminarySelection.model_validate_json(wrong.model_dump_json())
    inconsistent = report.model_copy(update={'teams': {
        **report.teams, Team.RADIANT: row.model_copy(update={'preliminary_selection': parsed}),
    }})
    repaired = project_preliminary(inconsistent)
    result = repaired.teams[Team.RADIANT].preliminary_selection
    assert result is not None and result.status == 'none' and result.confidence == 'low'
    assert result.reason_codes[0] == 'stored_projection_inconsistent'
    assert 'leaver_context_unknown' in result.reason_codes
    assert repaired.players == inconsistent.players and repaired.teams[Team.RADIANT].selection == row.selection


@pytest.mark.parametrize('case,projection_change,player_change', [
    ('FIX-QA-02', {'reason_codes': ('incomplete_player_scores',)}, None),
    ('FIX-QA-03', {'status': 'single', 'player_slots': (0,), 'leader_slot': 0, 'margin': 15,
                   'reason_codes': ('highest_relative_index', 'roles_unknown', 'leaver_context_unknown')}, None),
    ('FIX-QA-04', {}, (4, 20)),
    ('FIX-QA-05', {'status': 'single', 'player_slots': (128,), 'leader_slot': 128, 'margin': 15,
                   'reason_codes': ('highest_relative_index', 'roles_unknown', 'leaver_context_unknown')}, None),
    ('FIX-QA-07', {'status': 'single', 'player_slots': (0,), 'leader_slot': 0, 'margin': 15,
                   'reason_codes': ('highest_relative_index', 'roles_unknown', 'leaver_context_unknown')}, (4, None)),
    ('FIX-QA-extra-highest', {'highest_index': 60}, None),
])
def test_fix_qa_semantic_corruptions(
    case: str, projection_change: dict[str, Any], player_change: tuple[int, int | None] | None,
) -> None:
    legacy = Path(__file__).parent / 'fixtures/performance/9057722463_ruiner_legacy.json'
    original = project_preliminary(RuinerReport.model_validate_json(legacy.read_text()))
    row = original.teams[Team.RADIANT]
    assert row.preliminary_selection is not None
    bad = row.preliminary_selection.model_copy(update=projection_change)
    players = tuple(p.model_copy(update={'error_index': player_change[1]})
                    if player_change is not None and p.player_slot == player_change[0] else p
                    for p in original.players)
    report = original.model_copy(update={'players': players, 'teams': {
        **original.teams, Team.RADIANT: row.model_copy(update={'preliminary_selection': bad}),
    }})
    # All cases here remain DTO-valid: the defect is in cross-object semantics.
    parsed = RuinerReport.model_validate_json(report.model_dump_json())
    fixed = project_preliminary(parsed)
    result = fixed.teams[Team.RADIANT].preliminary_selection
    assert result is not None and result.status == 'none', case
    assert result.player_slots == () and result.leader_slot is None, case
    assert result.highest_index is None and result.margin is None, case
    assert result.confidence == 'low' and result.reason_codes[0] == 'stored_projection_inconsistent', case
    assert fixed.players == parsed.players and fixed.teams[Team.DIRE] == parsed.teams[Team.DIRE], case
    assert project_preliminary(fixed) == fixed, case


def test_fix_qa_valid_legacy_leaver_and_lost_context() -> None:
    legacy = Path(__file__).parent / 'fixtures/performance/9057722463_ruiner_legacy.json'
    old = RuinerReport.model_validate_json(legacy.read_text())
    projected = project_preliminary(old)
    assert project_preliminary(projected) == projected  # FIX-QA-08/09/10
    assert projected.teams[Team.RADIANT].preliminary_selection is not None
    assert projected.teams[Team.DIRE].preliminary_selection is not None
    players = tuple(p for p in projected.players if p.team == Team.RADIANT)
    known_leaver = select_preliminary(players, Team.RADIANT, leaver_context={0: True})
    assert known_leaver.status == 'none' and known_leaver.reason_codes[0] == 'confirmed_leaver'
    row = projected.teams[Team.RADIANT]
    blocked = projected.model_copy(update={'teams': {**projected.teams, Team.RADIANT:
        row.model_copy(update={'preliminary_selection': known_leaver})}})
    assert project_preliminary(blocked) == blocked  # FIX-QA-12: no leader resurrected
    fully_known_leaver = select_preliminary(players, Team.RADIANT,
        leaver_context={p.player_slot: p.player_slot == 0 for p in players})
    fully_known = projected.model_copy(update={'teams': {**projected.teams, Team.RADIANT:
        row.model_copy(update={'preliminary_selection': fully_known_leaver})}})
    assert project_preliminary(fully_known) == fully_known
    known_clear = select_preliminary(players, Team.RADIANT, leaver_context=dict.fromkeys(range(5), False))
    assert known_clear.status == 'group' and 'leaver_context_unknown' not in known_clear.reason_codes
    stale = projected.model_copy(update={'teams': {**projected.teams, Team.RADIANT:
        row.model_copy(update={'preliminary_selection': known_clear})}})
    refusal = project_preliminary(stale).teams[Team.RADIANT].preliminary_selection
    assert refusal is not None and refusal.status == 'none'  # FIX-QA-13: lost trusted context
    assert refusal.reason_codes[0] == 'stored_projection_inconsistent'
    assert 'leaver_context_unknown' in refusal.reason_codes


def test_fix_qa_structural_mismatch_stays_invalid() -> None:
    legacy = Path(__file__).parent / 'fixtures/performance/9057722463_ruiner_legacy.json'
    report = project_preliminary(RuinerReport.model_validate_json(legacy.read_text()))
    row = report.teams[Team.RADIANT]
    assert row.preliminary_selection is not None
    wrong = row.preliminary_selection.model_copy(update={'status': 'single', 'player_slots': (0,),
        'leader_slot': 4, 'margin': 15, 'reason_codes': ('highest_relative_index',)})
    with pytest.raises(ValidationError):  # DTO rejects leader/list mismatch before projection (FIX-QA-06).
        PreliminarySelection.model_validate_json(wrong.model_dump_json())


@pytest.mark.postgres
async def test_api_rejects_inconsistent_persisted_preliminary(
    flow: tuple[Database, Provider, MatchAnalysisService], pg_url: str,
) -> None:
    db, _, analysis = flow
    await analysis.process(MATCH_ID)
    async with db.sessions() as session, session.begin():
        row = await get_analysis(session, MATCH_ID, SECTION_VERSIONS['ruiner'])
        assert row is not None and row.report_payload is not None
        payload = deepcopy(cast(dict[str, Any], row.report_payload))
        assert all(p['confidence'] == 'low' for p in payload['data']['players'] if p['team'] == 'radiant')
        payload['data']['teams']['radiant']['preliminary_selection']['confidence'] = 'medium'
        row.report_payload = payload  # Isolated test DB only; fixture cleanup removes this match.
    async with client(pg_url) as http:
        response = await http.get(f'/api/v1/matches/{MATCH_ID}/ruiner')
        repeat = await http.get(f'/api/v1/matches/{MATCH_ID}/ruiner')
    assert response.status_code == repeat.status_code == 200
    assert response.json() == repeat.json()
    result = response.json()['data']['teams']['radiant']['preliminary_selection']
    assert result['status'] == 'none' and result['confidence'] == 'low'
    assert result['reason_codes'][0] == 'stored_projection_inconsistent'
    local_app = create_app(Settings(local_alpha=True, database_url=SecretStr(pg_url)))
    async with local_app.router.lifespan_context(local_app), AsyncClient(
        transport=ASGITransport(app=local_app), base_url='http://127.0.0.1:8000',
    ) as local:
        local_response = await local.get(f'/api/v1/local-alpha/matches/{MATCH_ID}/ruiner')
    assert local_response.status_code == 200
    assert local_response.json()['data'] == response.json()['data']
    async with db.sessions() as session:
        row = await get_analysis(session, MATCH_ID, SECTION_VERSIONS['ruiner'])
        assert row is not None and row.report_payload == payload


@pytest.mark.postgres
@pytest.mark.parametrize('change', [
    {'projection_version': 'unknown_version'},
    {'status': 'single', 'player_slots': [0], 'leader_slot': 1, 'highest_index': 50,
     'margin': 15, 'reason_codes': ['highest_relative_index']},
])
async def test_api_rejects_structurally_invalid_saved_projection(
    flow: tuple[Database, Provider, MatchAnalysisService], pg_url: str, change: dict[str, Any],
) -> None:
    db, _, analysis = flow
    await analysis.process(MATCH_ID)
    async with db.sessions() as session, session.begin():
        row = await get_analysis(session, MATCH_ID, SECTION_VERSIONS['ruiner'])
        assert row is not None and row.report_payload is not None
        payload = deepcopy(cast(dict[str, Any], row.report_payload))
        payload['data']['teams']['radiant']['preliminary_selection'].update(change)
        row.report_payload = payload
    async with client(pg_url) as http:
        response = await http.get(f'/api/v1/matches/{MATCH_ID}/ruiner')
    assert response.status_code == 503
    assert response.json()['error']['code'] == 'REPORT_UNAVAILABLE'
