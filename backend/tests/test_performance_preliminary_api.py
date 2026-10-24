from copy import deepcopy
import json
from typing import Any, cast
from app.db.session import Database
from app.services.match_analysis import MatchAnalysisService

import pytest

from app.services.match_analysis import SECTION_VERSIONS, get_analysis
from app.services.performance_preliminary import project_preliminary
from app.models.performance import RuinerReport
from test_group_flow import MATCH_ID, Provider, client, flow  # shared isolated test-DB / stub-provider fixture


@pytest.mark.postgres
@pytest.mark.parametrize('legacy', [False, True])
async def test_preliminary_storage_cached_read_api_and_legacy_projection(
    flow: tuple[Database, Provider, MatchAnalysisService], pg_url: str, legacy: bool,
) -> None:
    db, provider, analysis = flow
    await analysis.process(MATCH_ID)
    async with db.sessions() as session, session.begin():
        stored = await get_analysis(session, MATCH_ID, SECTION_VERSIONS['ruiner'])
        assert stored is not None and stored.report_payload is not None
        payload = deepcopy(cast(dict[str, Any], stored.report_payload))
        assert all(row['preliminary_selection'] for row in payload['data']['teams'].values())
        if legacy:
            for row in payload['data']['teams'].values():
                row.pop('preliminary_selection')
            stored.report_payload = payload
        baseline = deepcopy(payload)
        computed_at = stored.computed_at
    expected = project_preliminary(RuinerReport.model_validate_json(json.dumps(baseline['data'])))
    # Cached job does not need to fetch or rewrite old analyses to make RI-04 visible.
    calls = provider.calls
    await analysis.process(MATCH_ID)
    async with client(pg_url) as http:
        for _ in range(2):
            result = await http.get(f'/api/v1/matches/{MATCH_ID}/ruiner')
            assert result.status_code == 200
            data = result.json()['data']
            assert data == expected.model_dump(mode='json')
            assert data['players'] == baseline['data']['players']
            assert data['summary'] == baseline['data']['summary']
            for team in data['teams']:
                assert data['teams'][team]['selection'] == baseline['data']['teams'][team]['selection']
        for section in ('players', 'overview', 'draft', 'timeline'):
            result = await http.get(f'/api/v1/matches/{MATCH_ID}/{section}')
            assert result.status_code == 200
            assert 'preliminary_selection' not in result.text
    assert provider.calls == calls
    async with db.sessions() as session:
        stored = await get_analysis(session, MATCH_ID, SECTION_VERSIONS['ruiner'])
        assert stored is not None
        assert stored.report_payload == baseline and stored.computed_at == computed_at
