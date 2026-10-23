import asyncio
from datetime import UTC, datetime

import httpx
import pytest

from app.integrations.opendota import OpenDotaClient
from app.integrations.opendota_matchups import OpenDotaMatchups, parse_matchups
from app.services.draft.analyzer import analyze_with_matchups
from app.services.match_normalization import normalize_match_snapshot
from test_draft_analyzer import fixture_snapshot


@pytest.mark.parametrize('body', [None, {}, [{'hero_id': 2, 'games_played': 1, 'wins': 2}],
                                  [{'hero_id': 2, 'games_played': True, 'wins': 0}],
                                  [{'hero_id': 2, 'games_played': 10}],
                                  [{'hero_id': 1, 'games_played': 10, 'wins': 3}],
                                  [{'hero_id': 2, 'games_played': 10, 'wins': 3}] * 2])
def test_bad_matchup_data_rejected(body: object) -> None:
    assert parse_matchups(1, body, datetime.now(UTC)).status == 'malformed'


async def test_matchup_http_headers_cache_singleflight_and_ttl(caplog: pytest.LogCaptureFixture) -> None:
    calls: list[str] = []
    async def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        assert request.url.path == '/api/heroes/1/matchups'
        assert request.headers['Authorization'] == 'Bearer fixture-private-key'
        await asyncio.sleep(.01)
        return httpx.Response(200, json=[{'hero_id': 81, 'games_played': 200, 'wins': 110}])
    client = OpenDotaClient(base_url='https://api.opendota.test/api', api_key='fixture-private-key',
                            timeout_seconds=1, max_retries=0, backoff_seconds=0,
                            transport=httpx.MockTransport(handler))
    now = [100.]
    provider = OpenDotaMatchups(client, ttl_seconds=60, clock=lambda: now[0])
    try:
        a, b = await asyncio.gather(provider.fetch(1), provider.fetch(1))
        assert a == b and a.status == 'ok' and len(calls) == 1
        assert a.rows[0].opponent_id == 81 and a.rows[0].patch_scope == 'aggregate_unknown'
        now[0] += 61
        await provider.fetch(1)
        assert len(calls) == 2
    finally:
        await client.close()
    assert 'fixture-private-key' not in caplog.text
    assert all('fixture-private-key' not in url for url in calls)
    assert 'fixture-private-key' not in a.model_dump_json()


async def test_429_halts_batch_and_cooldown_covers_other_heroes() -> None:
    calls = 0
    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(429, headers={'Retry-After': '45'})
    client = OpenDotaClient(base_url='https://api.opendota.test/api', api_key=None, timeout_seconds=1,
                            max_retries=2, backoff_seconds=0, transport=httpx.MockTransport(handler))
    provider = OpenDotaMatchups(client)
    try:
        result = await analyze_with_matchups(normalize_match_snapshot(fixture_snapshot()), provider)
        assert len(result.pick_events) == 10 and calls == 1
        assert (await provider.fetch(999)).status == 'rate_limited' and calls == 1
    finally:
        await client.close()


@pytest.mark.parametrize('status,expected', [(404, 'not_found'), (500, 'unavailable'), (200, 'malformed')])
async def test_http_failures_are_safe_and_retry_bounded(status: int, expected: str) -> None:
    calls = 0
    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(status, text='invalid')
    client = OpenDotaClient(base_url='https://api.opendota.test/api', api_key=None, timeout_seconds=1,
                            max_retries=2, backoff_seconds=0, transport=httpx.MockTransport(handler))
    try:
        result = await OpenDotaMatchups(client).fetch(1)
        assert result.status == expected
        assert calls == (3 if status == 500 else 1)
    finally:
        await client.close()


async def test_timeout_is_unavailable_without_raw_exception() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout('fixture sensitive exception', request=request)
    client = OpenDotaClient(base_url='https://api.opendota.test/api', api_key=None, timeout_seconds=1,
                            max_retries=1, backoff_seconds=0, transport=httpx.MockTransport(handler))
    try:
        result = await OpenDotaMatchups(client).fetch(1)
        assert result.status == 'unavailable'
        assert 'sensitive' not in result.model_dump_json()
    finally:
        await client.close()


async def test_unknown_out_of_range_heroes_do_not_crash_or_make_http_calls() -> None:
    snapshot = fixture_snapshot()
    for player in snapshot['match']['players']:
        player['hero_id'] += 100000
    async def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError('invalid hero IDs must not reach HTTP')
    client = OpenDotaClient(base_url='https://api.opendota.test/api', api_key=None, timeout_seconds=1,
                            max_retries=0, backoff_seconds=0, transport=httpx.MockTransport(handler))
    try:
        report = await analyze_with_matchups(normalize_match_snapshot(snapshot), OpenDotaMatchups(client))
        assert report.mode == 'FINAL_ONLY' and len(report.pick_events) == 10
        assert all(p.final_score is None for p in report.pick_events)
    finally:
        await client.close()
