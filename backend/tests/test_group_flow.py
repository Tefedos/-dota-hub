import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from aiogram import Bot, Dispatcher
from aiogram.types import InlineKeyboardMarkup
from app.bot.handlers import create_router
from app.bot.services import JobService, RequestStatus
from app.db.models import Match, MatchAnalysis, TelegramUser
from app.db.session import Database
from app.integrations.opendota import (
    OpenDotaClient,
    OpenDotaResult,
    OpenDotaStatus,
    parse_match_response,
)
from app.integrations.opendota_matchups import OpenDotaMatchups
import httpx
from app.main import create_app
from app.models.draft import DraftReport
from app.models.match_api import (
    SECTIONS,
    AnalysisState,
    MatchEnvelope,
    OverviewReport,
    PlayersReport,
)
from app.models.matches import StrictDTO
from app.models.performance import RuinerReport
from app.models.timeline import TimelineReport
from app.services.match_analysis import (
    SECTION_VERSIONS,
    MatchAnalysisService,
    get_analysis,
)
from app.services.match_ingestion import MatchIngestionService
from app.services.sessions import auth_secrets, create_session
from auth_fixtures import auth_settings, fields, signed
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
from sqlalchemy import delete, select
from test_bot_handlers import StubSession, configured, update

MATCH_ID = 8888765469
USER_ID = 9007199254741987
FIXTURE = Path(__file__).parent / 'fixtures/group_flow/8888765469.json'


class Provider:
    def __init__(self) -> None:
        self.payload: Any = json.loads(FIXTURE.read_text())
        self.status: OpenDotaStatus | None = None
        self.calls = 0

    async def fetch_match(self, match_id: int) -> OpenDotaResult:
        self.calls += 1
        await asyncio.sleep(0.01)
        if self.status is not None:
            return OpenDotaResult(self.status, match_id, retry_after_seconds=5)
        raw = deepcopy(self.payload)
        if isinstance(raw, dict):
            raw['match_id'] = match_id
        return parse_match_response(match_id, raw, datetime.now(UTC))


def pipeline(db: Database, provider: Provider) -> MatchAnalysisService:
    ingestion = MatchIngestionService(db.sessions, provider, success_ttl_seconds=3600,
                                     error_ttl_seconds=60, not_found_ttl_seconds=300)
    return MatchAnalysisService(db.sessions, ingestion)


@pytest.fixture
async def flow(pg_url: str, prepared_pg: None) -> AsyncIterator[tuple[Database, Provider, MatchAnalysisService]]:
    database = Database(pg_url)
    provider = Provider()
    try:
        yield database, provider, pipeline(database, provider)
    finally:
        async with database.sessions() as session, session.begin():
            await session.execute(delete(MatchAnalysis).where(MatchAnalysis.match_id.between(MATCH_ID, MATCH_ID + 20)))
            await session.execute(delete(Match).where(Match.match_id.between(MATCH_ID, MATCH_ID + 20)))
            await session.execute(delete(TelegramUser).where(TelegramUser.telegram_user_id.in_((USER_ID, USER_ID + 1))))
        await database.close()


@asynccontextmanager
async def client(pg_url: str) -> AsyncIterator[AsyncClient]:
    settings = auth_settings()
    settings.database_url = SecretStr(pg_url)
    bot, _ = auth_secrets(settings)
    application = create_app(settings)
    async with application.router.lifespan_context(application), AsyncClient(transport=ASGITransport(app=application), base_url='http://test') as http:
        raw = signed(fields(user=json.dumps({'id': USER_ID, 'first_name': 'Contract'}), start_param=f'match_{MATCH_ID}'), bot)
        login = await http.post('/api/v1/auth/telegram', json={'init_data': raw})
        assert login.status_code == 200
        http.headers['Authorization'] = 'Bearer ' + login.json()['access_token']
        yield http


@pytest.mark.postgres
async def test_dispatcher_storage_authenticated_api_and_public_contract(flow: tuple[Database, Provider, MatchAnalysisService], pg_url: str) -> None:
    db, provider, analysis = flow
    provider.payload['players'][0]['account_id'] = 1234567
    provider.payload['players'][0]['steam_id'] = '76561190000000000'
    provider.payload['players'][0]['personaname'] = '<b>private-player</b>'
    provider.payload['radiant_name'] = '<b>' + 'x' * 8000 + '</b>'
    transport = StubSession()
    bot = Bot('999:synthetic-only', session=transport)
    jobs = JobService(10, analysis.ingestion, analysis=analysis)
    dispatcher = Dispatcher()
    dispatcher.include_router(create_router(configured(allowed=[-100123]), jobs))
    try:
        await dispatcher.feed_update(bot, update(f'/match@FixtureBot {MATCH_ID}'))
        await jobs.wait_pending()
        assert len(transport.sent) == 2
        message = transport.sent[1]
        assert message.chat_id == -100123 and message.parse_mode is None and len(message.text) < 4096
        assert 'Radiant / Dire' in message.text and 'недостаточно уверенных' in message.text
        assert '<b>' not in message.text and 'private-player' not in message.text
        assert isinstance(message.reply_markup, InlineKeyboardMarkup)
        button = message.reply_markup.inline_keyboard[0][0]
        assert button.url == f'https://t.me/FixtureBot?startapp=match_{MATCH_ID}' and button.web_app is None
        async with db.sessions() as session:
            rows = (await session.scalars(select(MatchAnalysis).where(MatchAnalysis.match_id == MATCH_ID))).all()
            assert len(rows) == 6 and all(r.computed_at for r in rows)
            raw = await session.get(Match, MATCH_ID)
            assert raw is not None and raw.raw_payload is not None
        models: dict[str, type[StrictDTO]] = {'overview': OverviewReport, 'players': PlayersReport, 'draft': DraftReport, 'ruiner': RuinerReport, 'timeline': TimelineReport}
        async with client(pg_url) as http:
            for section in SECTIONS:
                result = await http.get(f'/api/v1/matches/{MATCH_ID}/{section}')
                assert result.status_code == 200, result.text
                body = result.json()
                assert body['schema_version'] == 1 and body['status'] == 'ready' and body['match_id'] == str(MATCH_ID)
                assert body['model_version'] and body['config_version'] and body['analyzed_at']
                assert result.headers['cache-control'] == 'no-store'
                models[section].model_validate_json(json.dumps(body['data']))
                assert 'account_id' not in result.text and 'steam_id' not in result.text
                if section not in ('players', 'overview'):
                    assert 'private-player' not in result.text
                if section == 'overview':
                    assert len(body['data']['radiant']['players']) == 5
                    assert len(body['data']['dire']['players']) == 5
                    first = body['data']['radiant']['players'][0]
                    assert first['display_name'] == '<b>private-player</b>'
                    assert first['hero_name'] == 'Anti-Mage'
                    assert first['hero_image_url'].endswith('/antimage.png')
                    assert body['data']['radiant']['players'][1]['display_name'] is None
                    assert body['data']['game_mode_name'] == 'All Draft'
                    assert body['data']['patch_name'] is None  # Fixture deliberately uses unknown patch 999.
                    assert body['data']['team_stats']['radiant'] == {
                        'kills': 30, 'towers_destroyed': None, 'roshan_kills': None,
                    }
                    assert body['data']['team_stats']['dire']['kills'] == 20
                    assert body['data']['limitations'] == body['limitations']
                if section == 'draft':
                    assert body['data']['mode'] == 'FINAL_ONLY'
                    assert all(p['at_pick_score'] is None for p in body['data']['pick_events'])
                if section == 'players':
                    assert len(body['data']['players']) == 10
                    first = body['data']['players'][0]
                    assert first['display_name'] == '<b>private-player</b>'
                    assert first['name_source'] == 'opendota' and first['is_anonymous'] is False
                    assert body['data']['players'][1]['display_name'] == 'Анонимный игрок'
                    assert body['data']['players'][1]['is_anonymous'] is True
                    assert first['hero_name'] == 'Anti-Mage'
                    assert first['hero_image_url'].endswith('/antimage.png')
                    assert first['items'] == [1, 2, 3, 4, 5, 6]
                    assert first['item_details'][0]['name'] == 'Blink Dagger'
                    assert first['item_details'][0]['status'] == 'known'
                    assert first['neutral_item_details']['name'] == 'Observer Ward'
                    assert first['level'] is None and first['stun_duration_seconds'] is None
                    assert first['performance_position']['evidence'] == 'unknown'
                    assert body['completeness'] == 'full'
                    assert body['data']['completeness_scope'] == 'core_player_stats'
                    assert body['limitations']
            status = await http.get(f'/api/v1/matches/{MATCH_ID}/analysis/status')
            MatchEnvelope[AnalysisState].model_validate_json(status.text)
            assert set(status.json()['available_sections']) == set(SECTIONS)
            assert (await http.get(f'/api/v1/matches/{MATCH_ID}/raw')).status_code == 404
            assert (await http.post(f'/api/v1/matches/{MATCH_ID}/overview')).status_code == 405
    finally:
        await jobs.close()
        await bot.session.close()


@pytest.mark.postgres
async def test_repeated_concurrent_chats_and_restart_reuse_reports(flow: tuple[Database, Provider, MatchAnalysisService], pg_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    db, provider, analysis = flow
    calls = 0
    from app.services.draft.analyzer import analyze_draft
    def counted(*args: Any, **kwargs: Any) -> DraftReport:
        nonlocal calls
        calls += 1
        return analyze_draft(*args, **kwargs)
    monkeypatch.setattr('app.services.match_analysis.analyze_draft', counted)
    transport = StubSession()
    bot = Bot('999:synthetic-only', session=transport)
    jobs = JobService(10, analysis.ingestion, analysis=analysis)
    dispatcher = Dispatcher()
    dispatcher.include_router(create_router(configured(allowed=[-100123, -100456]), jobs))
    try:
        await asyncio.gather(dispatcher.feed_update(bot, update(f'/match {MATCH_ID}', chat_id=-100123)),
                             dispatcher.feed_update(bot, update(f'/match {MATCH_ID}', chat_id=-100456, update_id=2)))
        await jobs.wait_pending()
        assert len(transport.sent) == 4
        assert sum('Победитель' in m.text for m in transport.sent) == 2
        assert provider.calls == calls == 1
        await pipeline(db, provider).process(MATCH_ID)
        async with client(pg_url) as http:
            for _ in range(3):
                assert (await http.get(f'/api/v1/matches/{MATCH_ID}/draft')).status_code == 200
        assert provider.calls == calls == 1
    finally:
        await jobs.close()
        await bot.session.close()


@pytest.mark.postgres
@pytest.mark.parametrize('provider_status,http_code', [(OpenDotaStatus.API_UNAVAILABLE,503), (OpenDotaStatus.RATE_LIMITED,429), (OpenDotaStatus.NOT_FOUND,404), (OpenDotaStatus.MALFORMED_RESPONSE,502)])
async def test_provider_errors_and_no_fabricated_reports(flow: tuple[Database, Provider, MatchAnalysisService], pg_url: str, provider_status: OpenDotaStatus, http_code: int) -> None:
    _, provider, analysis = flow
    provider.status = provider_status
    message = await analysis.process(MATCH_ID)
    assert message and 'Победитель' not in message
    async with client(pg_url) as http:
        response = await http.get(f'/api/v1/matches/{MATCH_ID}/overview')
        assert response.status_code == http_code
        assert response.json()['error']['code'] == provider_status.value
        assert response.json()['data'] is None and response.json()['available_sections'] == []
        status = await http.get(f'/api/v1/matches/{MATCH_ID}/analysis/status')
        assert status.status_code == 200 and status.json()['status'] == 'failed'


@pytest.mark.postgres
async def test_pending_unknown_and_interrupted_worker(flow: tuple[Database, Provider, MatchAnalysisService], pg_url: str) -> None:
    _, _, analysis = flow
    async with client(pg_url) as http:
        assert (await http.get(f'/api/v1/matches/{MATCH_ID}/overview')).status_code == 404
        for state in ('queued', 'running'):
            await analysis._state(MATCH_ID, {'state': state, 'available_sections': []})
            response = await http.get(f'/api/v1/matches/{MATCH_ID}/overview')
            assert response.status_code == 202 and response.headers['retry-after'] == '2'
            assert response.json()['status'] == state and response.json()['data'] is None
        assert await analysis.recover_interrupted() == 1
        assert await analysis.recover_interrupted() == 0
        failed = await http.get(f'/api/v1/matches/{MATCH_ID}/overview')
        assert failed.status_code == 503 and failed.json()['error']['code'] == 'WORKER_RESTARTED'
        await analysis.process(MATCH_ID)
        assert (await http.get(f'/api/v1/matches/{MATCH_ID}/overview')).status_code == 200


@pytest.mark.postgres
async def test_partial_missing_arrays_and_timeline_filters(flow: tuple[Database, Provider, MatchAnalysisService], pg_url: str) -> None:
    _, provider, analysis = flow
    provider.payload.pop('picks_bans')
    provider.payload.pop('teamfights')
    provider.payload['objectives'].append(None)
    await analysis.process(MATCH_ID)
    async with client(pg_url) as http:
        result = await http.get(f'/api/v1/matches/{MATCH_ID}/timeline?type=hero_kill&side=radiant')
        assert result.status_code == 200
        assert result.json()['data']['quality'] == 'partial'
        assert all(e['type'] == 'hero_kill' and e['team'] == 'radiant' for e in result.json()['data']['events'])
        assert (await http.get(f'/api/v1/matches/{MATCH_ID}/timeline?type=invalid')).status_code == 422
        assert (await http.get('/api/v1/matches/0/overview')).status_code == 422


@pytest.mark.postgres
async def test_section_failure_isolated_and_safe(flow: tuple[Database, Provider, MatchAnalysisService], pg_url: str, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    _, _, analysis = flow
    def fail(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError('private-marker-BOT_TOKEN')
    monkeypatch.setattr('app.services.match_analysis.analyze_draft', fail)
    await analysis.process(MATCH_ID)
    async with client(pg_url) as http:
        assert (await http.get(f'/api/v1/matches/{MATCH_ID}/overview')).status_code == 200
        result = await http.get(f'/api/v1/matches/{MATCH_ID}/draft')
        assert result.status_code == 503 and 'private-marker' not in result.text + caplog.text
        status = (await http.get(f'/api/v1/matches/{MATCH_ID}/analysis/status')).json()
        assert 'draft' not in status['available_sections'] and 'timeline' in status['available_sections']


def test_unauthorized_match_routes_and_unavailable_database() -> None:
    settings = auth_settings()
    with TestClient(create_app(settings)) as http:
        for path in (*SECTIONS, 'analysis/status'):
            response = http.get(f'/api/v1/matches/{MATCH_ID}/{path}?user_id=1&chat_instance=trusted')
            assert response.status_code == 401
            assert response.json()['schema_version'] == 1 and response.json()['error']['code'] == 'AUTH_REQUIRED'
        _, key = auth_secrets(settings)
        unavailable = http.get(f'/api/v1/matches/{MATCH_ID}/overview', headers={'Authorization': 'Bearer ' + create_session(USER_ID, key, 900)})
        assert unavailable.status_code == 503 and unavailable.json()['error']['retryable'] is True


def test_public_openapi_schema_snapshot() -> None:
    expected = json.loads((FIXTURE.parent / 'contracts.json').read_text())
    spec = create_app(auth_settings()).openapi()
    actual_paths = {path: value for path, value in spec['paths'].items() if path.startswith('/api/v1/matches/')}
    assert actual_paths == expected['paths']
    for name, schema in expected['components']['schemas'].items():
        assert spec['components']['schemas'][name] == schema


@pytest.mark.postgres
async def test_malformed_array_is_502_not_an_invented_analysis(flow: tuple[Database, Provider, MatchAnalysisService], pg_url: str) -> None:
    _, provider, analysis = flow
    provider.payload['picks_bans'] = 'not-an-array'
    await analysis.process(MATCH_ID)
    async with client(pg_url) as http:
        result = await http.get(f'/api/v1/matches/{MATCH_ID}/draft')
        assert result.status_code == 502 and result.json()['data'] is None


@pytest.mark.postgres
async def test_partial_roster_keeps_available_overview_without_fabrication(
    flow: tuple[Database, Provider, MatchAnalysisService], pg_url: str,
) -> None:
    _, provider, analysis = flow
    provider.payload['players'] = [provider.payload['players'][0], provider.payload['players'][1],
                                   provider.payload['players'][5]]
    provider.payload['players'][0]['hero_id'] = 999999
    provider.payload['players'][0].pop('personaname', None)
    provider.payload['patch'] = 999
    await analysis.process(MATCH_ID)
    async with client(pg_url) as http:
        result = await http.get(f'/api/v1/matches/{MATCH_ID}/overview')
        assert result.status_code == 200
        body = result.json()
        assert body['status'] == 'ready' and body['completeness'] == 'partial'
        assert body['data']['data_quality']['summary'] == 'partial'
        assert len(body['data']['radiant']['players']) == 2
        assert len(body['data']['dire']['players']) == 1
        assert body['data']['radiant']['players'][0]['hero_name'] is None
        assert body['data']['radiant']['players'][0]['hero_image_url'] is None
        assert body['data']['radiant']['players'][0]['display_name'] is None
        assert body['data']['patch_name'] is None
        assert any('неполные' in note for note in body['limitations'])
        assert body['data']['team_stats']['radiant']['kills'] == body['data']['radiant']['score']


@pytest.mark.postgres
async def test_refreshed_source_invalidates_cached_sections(flow: tuple[Database, Provider, MatchAnalysisService], pg_url: str) -> None:
    db, provider, analysis = flow
    await analysis.process(MATCH_ID)
    async with db.sessions() as session, session.begin():
        row = await session.get(Match, MATCH_ID)
        assert row is not None
        row.fetch_status = 'pending'
    provider.payload['radiant_score'] = 44
    await analysis.process(MATCH_ID)
    async with client(pg_url) as http:
        result = await http.get(f'/api/v1/matches/{MATCH_ID}/overview')
        assert result.status_code == 200 and result.json()['data']['radiant']['score'] == 44
    assert provider.calls == 2


@pytest.mark.postgres
async def test_group_flow_fetches_matchups_and_persists_evidence(flow: tuple[Database, Provider, MatchAnalysisService], pg_url: str) -> None:
    _, provider, analysis = flow
    calls: list[str] = []
    async def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        return httpx.Response(200, json=[])
    open_dota = OpenDotaClient(base_url='https://api.opendota.test/api', api_key=None, timeout_seconds=1,
                            max_retries=0, backoff_seconds=0, transport=httpx.MockTransport(handler))
    analysis.matchups = OpenDotaMatchups(open_dota)
    try:
        await analysis.process(MATCH_ID)
        assert len(calls) == 10 and all(path.startswith('/api/heroes/') and path.endswith('/matchups') for path in calls)
        async with client(pg_url) as http:
            result = await http.get(f'/api/v1/matches/{MATCH_ID}/draft')
            assert result.status_code == 200
            assert result.json()['data']['evidence_digest']
            assert result.json()['data']['model_version'] == 'draft-heuristic-v1.1.1'
        await analysis.process(MATCH_ID)
        assert provider.calls == 1 and len(calls) == 10
    finally:
        await open_dota.close()


@pytest.mark.postgres
async def test_sequential_contract_preserves_separate_pick_and_final_fields(flow: tuple[Database, Provider, MatchAnalysisService], pg_url: str) -> None:
    from test_draft_analyzer import fixture_snapshot
    _, provider, analysis = flow
    provider.payload = fixture_snapshot()['match']
    provider.payload['patch'] = 46
    await analysis.process(MATCH_ID)
    async with client(pg_url) as http:
        result = await http.get(f'/api/v1/matches/{MATCH_ID}/draft')
        assert result.status_code == 200
        draft = result.json()['data']
        assert draft['mode'] == 'SEQUENTIAL' and len(draft['pick_events']) == 10
        for pick in draft['pick_events']:
            assert pick['stage'] is not None
            assert 'at_pick_score' in pick and 'final_score' in pick
            assert pick['at_pick_score'] == pick['at_pick']['score']
            assert pick['final_score'] == pick['final_context']['score']


@pytest.mark.postgres
async def test_corrupt_saved_dto_is_safe_503_without_reanalysis(flow: tuple[Database, Provider, MatchAnalysisService], pg_url: str) -> None:
    db, provider, analysis = flow
    await analysis.process(MATCH_ID)
    async with db.sessions() as session, session.begin():
        row = await get_analysis(session, MATCH_ID, SECTION_VERSIONS['players'])
        assert row is not None and row.report_payload is not None
        row.report_payload = {**row.report_payload, 'data': {'match_id': str(MATCH_ID)}}
    async with client(pg_url) as http:
        result = await http.get(f'/api/v1/matches/{MATCH_ID}/players')
        assert result.status_code == 503 and result.json()['error']['code'] == 'REPORT_UNAVAILABLE'
        assert provider.calls == 1


@pytest.mark.postgres
async def test_forwarded_match_link_is_public_to_other_authenticated_user(flow: tuple[Database, Provider, MatchAnalysisService], pg_url: str) -> None:
    _, _, analysis = flow
    await analysis.process(MATCH_ID)
    settings = auth_settings()
    settings.database_url = SecretStr(pg_url)
    token, _ = auth_secrets(settings)
    application = create_app(settings)
    async with application.router.lifespan_context(application), AsyncClient(transport=ASGITransport(app=application), base_url='http://test') as http:
        raw = signed(fields(user=json.dumps({'id': USER_ID + 1, 'first_name': 'Other'})), token)
        session = await http.post('/api/v1/auth/telegram', json={'init_data': raw})
        headers = {'Authorization': 'Bearer ' + session.json()['access_token']}
        assert (await http.get(f'/api/v1/matches/{MATCH_ID}/overview', headers=headers)).status_code == 200


def test_group_rate_limit_applies_across_senders() -> None:
    class Empty:
        async def ingest_match(self, match_id: int) -> OpenDotaResult:
            return OpenDotaResult(OpenDotaStatus.NOT_FOUND, match_id)
    jobs = JobService(1, Empty(), lambda: 100.)
    for user in range(1, 11):
        assert jobs.reserve_request(MATCH_ID, user, -123).status == RequestStatus.ACCEPTED
    assert jobs.reserve_request(MATCH_ID, 11, -123).status == RequestStatus.COOLDOWN
    assert jobs.reserve_request(MATCH_ID, 11, -456).status == RequestStatus.ACCEPTED
