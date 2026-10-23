import asyncio
from collections.abc import Awaitable, Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, TypeGuard

import httpx


class OpenDotaStatus(StrEnum):
    FOUND_FULL = "FOUND_FULL"
    FOUND_PARTIAL = "FOUND_PARTIAL"
    NOT_FOUND = "NOT_FOUND"
    API_UNAVAILABLE = "API_UNAVAILABLE"
    RATE_LIMITED = "RATE_LIMITED"
    MALFORMED_RESPONSE = "MALFORMED_RESPONSE"


@dataclass(frozen=True)
class OpenDotaResult:
    status: OpenDotaStatus
    match_id: int
    snapshot: dict[str, Any] | None = None
    retry_after_seconds: int | None = None
    from_cache: bool = False


FULL_FIELDS = (
    "match_id", "duration", "start_time", "patch", "game_mode", "lobby_type", "radiant_win",
    "radiant_score", "dire_score", "players", "picks_bans", "objectives", "teamfights",
    "radiant_gold_adv", "radiant_xp_adv",
)
PLAYER_PRIVATE_FIELDS = {
    "account_id", "name", "avatar", "avatarmedium", "avatarfull", "profileurl",
    "last_login", "loccountrycode", "steamid",
}
PLAYER_PUBLIC_DATA_VERSION = 1


def _is_int(value: object) -> TypeGuard[int]:
    return isinstance(value, int) and not isinstance(value, bool)


def _presence(payload: Mapping[str, Any]) -> dict[str, dict[str, int | bool | None]]:
    result: dict[str, dict[str, int | bool | None]] = {}
    for field in FULL_FIELDS:
        value = payload.get(field)
        result[field] = {
            "present": field in payload,
            "non_null": field in payload and value is not None,
            "item_count": len(value) if isinstance(value, (list, dict)) else None,
        }
    return result


def _sanitize(payload: Mapping[str, Any]) -> dict[str, Any]:
    result = deepcopy(dict(payload))
    players = result.get("players")
    if isinstance(players, list):
        for player in players:
            if isinstance(player, dict):
                for field in PLAYER_PRIVATE_FIELDS:
                    player.pop(field, None)
                nickname = player.get("personaname")
                if isinstance(nickname, str):
                    nickname = " ".join(nickname.split())[:80]
                if nickname:
                    player["personaname"] = nickname
                else:
                    player.pop("personaname", None)
    # Game chat can contain personal text and is not needed for ingestion/analysis.
    result.pop("chat", None)
    return result


def parse_match_response(match_id: int, payload: object, fetched_at: datetime) -> OpenDotaResult:
    if not isinstance(payload, dict):
        return OpenDotaResult(OpenDotaStatus.MALFORMED_RESPONSE, match_id)
    response_id = payload.get("match_id")
    duration = payload.get("duration")
    players = payload.get("players")
    if response_id != match_id or not _is_int(response_id) or not _is_int(duration) or duration <= 0:
        return OpenDotaResult(OpenDotaStatus.MALFORMED_RESPONSE, match_id)
    typed_core = ("start_time", "patch", "game_mode", "lobby_type", "radiant_score", "dire_score")
    if any(field in payload and payload[field] is not None and not _is_int(payload[field]) for field in typed_core):
        return OpenDotaResult(OpenDotaStatus.MALFORMED_RESPONSE, match_id)
    if "radiant_win" in payload and payload["radiant_win"] is not None and not isinstance(payload["radiant_win"], bool):
        return OpenDotaResult(OpenDotaStatus.MALFORMED_RESPONSE, match_id)
    list_fields = ("picks_bans", "objectives", "teamfights", "radiant_gold_adv", "radiant_xp_adv")
    if any(field in payload and payload[field] is not None and not isinstance(payload[field], list) for field in list_fields):
        return OpenDotaResult(OpenDotaStatus.MALFORMED_RESPONSE, match_id)
    if not isinstance(players, list) or not players:
        return OpenDotaResult(OpenDotaStatus.MALFORMED_RESPONSE, match_id)
    slots = [player.get("player_slot") for player in players if isinstance(player, dict)]
    valid_slots = [slot for slot in slots if _is_int(slot) and 0 <= slot <= 255]
    if not any(slot < 128 for slot in valid_slots) or not any(slot >= 128 for slot in valid_slots):
        return OpenDotaResult(OpenDotaStatus.MALFORMED_RESPONSE, match_id)
    presence = _presence(payload)
    status = (
        OpenDotaStatus.FOUND_FULL
        if all(item["present"] and item["non_null"] for item in presence.values())
        else OpenDotaStatus.FOUND_PARTIAL
    )
    snapshot = {
        "schema_version": 1,
        "player_public_data_version": PLAYER_PUBLIC_DATA_VERSION,
        "source": "opendota",
        "source_fetched_at": fetched_at.astimezone(UTC).isoformat(),
        "status": status.value,
        "presence": presence,
        "match": _sanitize(payload),
    }
    return OpenDotaResult(status, match_id, snapshot=snapshot)


def parse_retry_after(value: str | None) -> int | None:
    if value is None or not value.isdecimal():
        return None
    return min(max(int(value), 1), 3600)


class OpenDotaClient:
    def __init__(
        self, *, base_url: str, api_key: str | None, timeout_seconds: float, max_retries: int,
        backoff_seconds: float, transport: httpx.AsyncBaseTransport | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        headers = {"Accept": "application/json", "User-Agent": "DotaHub/0.1 (match ingestion)"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"), headers=headers, timeout=timeout_seconds, transport=transport,
        )
        self._max_retries = max_retries
        self._backoff = backoff_seconds
        self._sleep = sleep

    async def close(self) -> None:
        await self._client.aclose()

    async def get_json(self, path: str) -> tuple[int, object, int | None]:
        """Same bounded HTTP policy for match snapshots and optional hero matchups."""
        for attempt in range(self._max_retries + 1):
            try:
                response = await self._client.get(path)
            except httpx.RequestError:
                if attempt < self._max_retries:
                    await self._sleep(self._backoff * (2**attempt))
                    continue
                return 503, None, None
            if response.status_code == 429:
                return 429, None, parse_retry_after(response.headers.get("Retry-After"))
            if 500 <= response.status_code < 600 and attempt < self._max_retries:
                await self._sleep(self._backoff * (2**attempt))
                continue
            if response.status_code != 200:
                return response.status_code, None, None
            try:
                return 200, response.json(), None
            except ValueError:
                return 200, None, None
        raise AssertionError("retry loop exhausted")

    async def fetch_match(self, match_id: int) -> OpenDotaResult:
        status, payload, retry = await self.get_json(f"/matches/{match_id}")
        if status == 404:
            return OpenDotaResult(OpenDotaStatus.NOT_FOUND, match_id)
        if status == 429:
            return OpenDotaResult(OpenDotaStatus.RATE_LIMITED, match_id, retry_after_seconds=retry)
        if status != 200:
            return OpenDotaResult(OpenDotaStatus.API_UNAVAILABLE, match_id)
        return parse_match_response(match_id, payload, datetime.now(UTC))
