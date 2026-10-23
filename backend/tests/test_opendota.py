from collections.abc import Awaitable, Callable, Coroutine
import logging
from typing import Any

import httpx
import pytest

from app.integrations.opendota import OpenDotaClient, OpenDotaStatus

MATCH_ID = 9223372036854775807


def complete_match() -> dict[str, Any]:
    return {
        "match_id": MATCH_ID, "duration": 2400, "start_time": 1_700_000_000, "patch": 55,
        "game_mode": 22, "lobby_type": 7, "radiant_win": True, "radiant_score": 42, "dire_score": 30,
        "players": [
            {"player_slot": 0, "hero_id": 1, "account_id": 123, "personaname": "private"},
            {"player_slot": 128, "hero_id": 2, "profileurl": "private"},
        ],
        "picks_bans": [], "objectives": [], "teamfights": [], "radiant_gold_adv": [0, 10],
        "radiant_xp_adv": [0, 20], "chat": [{"key": "private chat"}], "engine": 1,
    }


async def client_for(
    handler: Callable[[httpx.Request], Coroutine[None, None, httpx.Response]], *, retries: int = 0,
    sleep: Callable[[float], Awaitable[None]] | None = None, api_key: str | None = None,
) -> OpenDotaClient:
    kwargs: dict[str, Any] = {}
    if sleep is not None:
        kwargs["sleep"] = sleep
    return OpenDotaClient(
        base_url="https://api.opendota.test/api", api_key=api_key, timeout_seconds=1,
        max_retries=retries, backoff_seconds=0.1, transport=httpx.MockTransport(handler), **kwargs,
    )


async def test_full_match_keeps_public_nickname_and_removes_private_identifiers() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == f"/api/matches/{MATCH_ID}"
        assert request.headers["User-Agent"].startswith("DotaHub/")
        return httpx.Response(200, json=complete_match())

    client = await client_for(handler)
    try:
        result = await client.fetch_match(MATCH_ID)
    finally:
        await client.close()
    assert result.status == OpenDotaStatus.FOUND_FULL
    assert result.snapshot is not None and result.snapshot["schema_version"] == 1
    assert result.snapshot["player_public_data_version"] == 1
    stored = result.snapshot["match"]
    assert stored["match_id"] == MATCH_ID and stored["engine"] == 1
    assert "account_id" not in stored["players"][0] and stored["players"][0]["personaname"] == "private"
    assert "profileurl" not in stored["players"][1] and "chat" not in stored


@pytest.mark.parametrize("field", ["picks_bans", "objectives", "teamfights", "radiant_gold_adv", "patch"])
async def test_missing_or_null_extended_fields_are_partial(field: str) -> None:
    payload = complete_match()
    if field == "objectives":
        payload[field] = None
    else:
        payload.pop(field)

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    client = await client_for(handler)
    try:
        result = await client.fetch_match(MATCH_ID)
    finally:
        await client.close()
    assert result.status == OpenDotaStatus.FOUND_PARTIAL
    assert result.snapshot is not None
    assert result.snapshot["presence"][field]["non_null"] is False


@pytest.mark.parametrize("payload", [
    [], {"match_id": MATCH_ID + 1, "duration": 1, "players": [{"player_slot": 0}, {"player_slot": 128}]},
    {"match_id": MATCH_ID, "duration": 0, "players": [{"player_slot": 0}, {"player_slot": 128}]},
    {"match_id": MATCH_ID, "duration": 1, "players": [{"player_slot": 0}]},
    {**complete_match(), "objectives": "wrong-type"},
])
async def test_malformed_and_wrong_match_are_rejected(payload: object) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    client = await client_for(handler)
    try:
        assert (await client.fetch_match(MATCH_ID)).status == OpenDotaStatus.MALFORMED_RESPONSE
    finally:
        await client.close()


@pytest.mark.parametrize("code,status", [
    (404, OpenDotaStatus.NOT_FOUND), (401, OpenDotaStatus.API_UNAVAILABLE),
])
async def test_http_status_mapping(code: int, status: OpenDotaStatus) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(code)

    client = await client_for(handler)
    try:
        assert (await client.fetch_match(MATCH_ID)).status == status
    finally:
        await client.close()


async def test_rate_limit_respects_retry_after_without_retry() -> None:
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(429, headers={"Retry-After": "45"})

    client = await client_for(handler, retries=3)
    try:
        result = await client.fetch_match(MATCH_ID)
    finally:
        await client.close()
    assert result.status == OpenDotaStatus.RATE_LIMITED and result.retry_after_seconds == 45
    assert calls == 1


@pytest.mark.parametrize("failure", ["500", "timeout"])
async def test_transient_failures_have_bounded_backoff(failure: str) -> None:
    calls = 0
    delays: list[float] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if failure == "timeout":
            raise httpx.ReadTimeout("fixture", request=request)
        return httpx.Response(500)

    async def sleep(delay: float) -> None:
        delays.append(delay)

    client = await client_for(handler, retries=2, sleep=sleep)
    try:
        result = await client.fetch_match(MATCH_ID)
    finally:
        await client.close()
    assert result.status == OpenDotaStatus.API_UNAVAILABLE
    assert calls == 3 and delays == [0.1, 0.2]


async def test_malformed_json_and_api_key_do_not_leak(caplog: pytest.LogCaptureFixture) -> None:
    secret = "fixture-secret-never-log"

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == f"Bearer {secret}"
        assert "api_key" not in request.url.params
        return httpx.Response(200, content=b"not-json")

    caplog.set_level(logging.DEBUG)
    client = await client_for(handler, api_key=secret)
    try:
        result = await client.fetch_match(MATCH_ID)
    finally:
        await client.close()
    assert result.status == OpenDotaStatus.MALFORMED_RESPONSE
    assert secret not in caplog.text
