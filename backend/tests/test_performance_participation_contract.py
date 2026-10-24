"""RI-02-FIX-01: counter ratio is preserved; unverified excess is not scored."""
from copy import deepcopy
import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import SecretStr
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.db.session import Database
from app.main import create_app
from app.models.matches import MetricStatus, Team
from app.models.performance import RuinerReport
from app.services.match_analysis import MatchAnalysisService, SECTION_VERSIONS, get_analysis
from app.services.match_normalization import normalize_match_snapshot
from app.services.performance import analyze_performance, observed, participation_assessment
from app.services.performance_config import PerformanceConfig
from app.services.performance_preliminary import project_preliminary, select_preliminary
from test_performance import performance_snapshot
from test_group_flow import MATCH_ID, Provider, client, flow


def two_support_snapshot() -> dict[str, Any]:
    snapshot = performance_snapshot()
    for player in snapshot['match']['players']:
        player['position_est'] = player['player_slot'] % 128 + 1
        if player['player_slot'] < 128:
            player.update(kills=2, assists=4)
    snapshot['match']['radiant_score'] = 10
    snapshot['match']['players'][3].update(assists=6, deaths=12)  # 8/10
    snapshot['match']['players'][4].update(assists=8)  # 10/10
    return snapshot


@pytest.mark.parametrize('case,assists,score,expected_raw,expected_eligible,reason', [
    ('KP-QA-01', 4, 10, .6, .6, None),
    ('KP-QA-02', 8, 10, 1., 1., None),
    ('KP-QA-03', 9, 10, 1.1, None, 'kill_participation_over_team_score_unverified'),
    ('KP-QA-04', 10, 10, 1.2, None, 'kill_participation_over_team_score_unverified'),
    ('KP-QA-05', 9998, 10, 1000., None, 'kill_participation_counter_anomaly'),
    ('KP-QA-06', 8, 0, None, None, 'kill_participation_team_score_zero'),
    ('KP-QA-07', 8, 9, 10 / 9, None, 'kill_participation_team_score_small'),
    ('score_missing', 8, None, None, None, 'kill_participation_team_score_missing'),
])
def test_ratio_contract_and_refusal_reasons(case: str, assists: int, score: int | None,
                                            expected_raw: float | None, expected_eligible: float | None,
                                            reason: str | None) -> None:
    snapshot = two_support_snapshot()
    snapshot['match']['players'][4]['assists'] = assists
    snapshot['match']['radiant_score'] = score
    before = deepcopy(snapshot)
    match = normalize_match_snapshot(snapshot)
    player = next(p for p in match.players if p.player_slot == 4)
    derived = next(d.kill_participation for d in match.derived if d.player_slot == 4)
    eligible, raw, actual_reason = participation_assessment(player, match, PerformanceConfig())
    metrics = observed(player, match, PerformanceConfig())
    assert raw == pytest.approx(expected_raw) if expected_raw is not None else raw is None, case
    assert eligible == pytest.approx(expected_eligible) if expected_eligible is not None else eligible is None, case
    assert actual_reason == reason, case
    assert metrics['kill_participation'] == eligible, case
    if raw is not None:
        assert derived.status == MetricStatus.AVAILABLE and derived.value == round(raw, 4), case
    else:
        assert derived.value is None, case
    if raw is not None and eligible is None:
        assert metrics['kill_participation_counter_ratio'] == raw, case
    assert snapshot == before, case
    report = analyze_performance(match)
    result = next(p for p in report.players if p.player_slot == 4)
    assert (reason in result.reason_codes) if reason is not None else not any(
        r.startswith('kill_participation_') for r in result.reason_codes), case
    assert report.model_version == 'ruiner_v1'
    assert RuinerReport.model_validate_json(report.model_dump_json()) == report


@pytest.mark.parametrize('field', ['kills', 'assists'])
def test_missing_counter_has_distinct_reason(field: str) -> None:
    snapshot = two_support_snapshot()
    snapshot['match']['players'][4].pop(field)
    match = normalize_match_snapshot(snapshot)
    player = next(p for p in analyze_performance(match).players if p.player_slot == 4)
    derived = next(d.kill_participation for d in match.derived if d.player_slot == 4)
    assert derived.status == MetricStatus.INPUTS_MISSING and derived.value is None
    assert player.observed_metrics['kill_participation'] is None
    assert f'kill_participation_{field}_missing' in player.reason_codes


def test_player_kills_exceeding_team_score_is_anomalous() -> None:
    snapshot = two_support_snapshot()
    snapshot['match']['players'][4].update(kills=11, assists=0)
    match = normalize_match_snapshot(snapshot)
    oracle = next(p for p in analyze_performance(match).players if p.player_slot == 4)
    assert oracle.observed_metrics['kill_participation_counter_ratio'] == 1.1
    assert oracle.observed_metrics['kill_participation'] is None
    assert 'kill_participation_counter_anomaly' in oracle.reason_codes


def test_peer_dependency_axes_coverage_confidence_and_teams() -> None:
    snapshot = two_support_snapshot()
    complete = analyze_performance(normalize_match_snapshot(snapshot))
    hood, oracle = (next(p for p in complete.players if p.player_slot == slot) for slot in (3, 4))
    assert hood.axes['participation'] is not None and oracle.axes['participation'] is not None
    assert hood.evidence_coverage == oracle.evidence_coverage == 1
    assert hood.error_index is not None and oracle.error_index is not None
    assert hood.confidence == oracle.confidence == 'low'  # estimated 4/5 remain estimated
    snapshot['match']['players'][4]['assists'] = 10  # 12/10: raw ratio remains visible, axis does not.
    blocked = analyze_performance(normalize_match_snapshot(snapshot))
    hood_blocked, oracle_blocked = (next(p for p in blocked.players if p.player_slot == slot) for slot in (3, 4))
    assert hood_blocked.observed_metrics['kill_participation'] == .8
    assert oracle_blocked.observed_metrics['kill_participation_counter_ratio'] == 1.2
    assert hood_blocked.axes['participation'] is oracle_blocked.axes['participation'] is None
    assert hood_blocked.evidence_coverage == oracle_blocked.evidence_coverage == .5
    assert hood_blocked.error_index is oracle_blocked.error_index is None
    assert all(p.confidence == 'low' for p in (hood_blocked, oracle_blocked))
    preliminary = blocked.teams[Team.RADIANT].preliminary_selection
    assert preliminary is not None and preliminary.status == 'none'
    assert blocked.teams[Team.RADIANT].selection.selection_status == 'no_confident_selection'
    assert complete.teams[Team.RADIANT].selection.selection_status == 'no_confident_selection'
    assert complete.teams[Team.RADIANT].preliminary_selection == select_preliminary(
        tuple(p for p in complete.players if p.team == Team.RADIANT), Team.RADIANT)
    assert complete.players[5:] == blocked.players[5:]  # Dire is independent.
    assert complete.players[:3] == blocked.players[:3]  # Other Radiant cores are independent peers.


def test_existing_persisted_ruiner_report_is_read_without_rewriting() -> None:
    fixture = Path(__file__).parent / 'fixtures/performance/9051271323_live_ri04_envelope.json'
    old = json.loads(fixture.read_text())
    report = RuinerReport.model_validate_json(json.dumps(old['data']))
    assert report.players[1].observed_metrics['kill_participation'] is None
    assert report.players[1].error_index is None
    assert project_preliminary(report) == report
    assert json.loads(fixture.read_text()) == old


@pytest.mark.postgres
async def test_api_returns_safe_diagnostic_without_reanalysis_or_db_write(
    flow: tuple[Database, Provider, MatchAnalysisService], pg_url: str,
) -> None:
    db, provider, analysis = flow
    provider.payload['radiant_score'] = 10
    for p in provider.payload['players'][:5]:
        p['kills'] = 2
        p['assists'] = 5
        p['position_est'] = p['player_slot'] + 1
    provider.payload['players'][3]['assists'] = 6
    provider.payload['players'][4]['assists'] = 10
    await analysis.process(MATCH_ID)
    calls = provider.calls
    async with db.sessions() as session:
        stored = await get_analysis(session, MATCH_ID, SECTION_VERSIONS['ruiner'])
        assert stored is not None and stored.report_payload is not None
        original = deepcopy(stored.report_payload)
        computed_at = stored.computed_at
    async with client(pg_url) as http:
        response = await http.get(f'/api/v1/matches/{MATCH_ID}/ruiner')
        repeat = await http.get(f'/api/v1/matches/{MATCH_ID}/ruiner')
    assert response.status_code == repeat.status_code == 200
    assert response.json() == repeat.json()
    data = response.json()['data']
    assert data['model_version'] == 'ruiner_v1'
    hood, oracle = data['players'][3:5]
    assert hood['observed_metrics']['kill_participation'] == .8
    assert hood['axes']['participation'] is None and hood['error_index'] is None
    assert oracle['observed_metrics']['kill_participation_counter_ratio'] == 1.2
    assert oracle['observed_metrics']['kill_participation'] is None
    assert 'kill_participation_over_team_score_unverified' in oracle['reason_codes']
    assert oracle['axes']['participation'] is None and oracle['error_index'] is None
    local_app = create_app(Settings(local_alpha=True, database_url=SecretStr(pg_url)))
    async with local_app.router.lifespan_context(local_app), AsyncClient(
        transport=ASGITransport(app=local_app), base_url='http://127.0.0.1:8000',
    ) as local:
        local_response = await local.get(f'/api/v1/local-alpha/matches/{MATCH_ID}/ruiner')
    assert local_response.status_code == 200 and local_response.json()['data'] == data
    assert provider.calls == calls  # GET does not fetch OpenDota.
    async with db.sessions() as session:
        stored = await get_analysis(session, MATCH_ID, SECTION_VERSIONS['ruiner'])
        assert stored is not None and stored.report_payload == original and stored.computed_at == computed_at
