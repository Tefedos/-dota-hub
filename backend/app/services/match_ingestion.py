import asyncio
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol, cast

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import FetchStatus, JsonObject
from app.db.repositories import get_match, upsert_match
from app.integrations.opendota import OpenDotaResult, OpenDotaStatus, PLAYER_PUBLIC_DATA_VERSION


class MatchProvider(Protocol):
    async def fetch_match(self, match_id: int) -> OpenDotaResult: ...


class MatchIngestionService:
    """Persistent TTL cache plus one-process single-flight fetches for a match ID."""

    def __init__(
        self, sessions: async_sessionmaker[AsyncSession], provider: MatchProvider, *, success_ttl_seconds: int,
        error_ttl_seconds: int, not_found_ttl_seconds: int,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._sessions = sessions
        self._provider = provider
        self._success_ttl = success_ttl_seconds
        self._error_ttl = error_ttl_seconds
        self._not_found_ttl = not_found_ttl_seconds
        self._clock = clock
        self._locks: dict[int, asyncio.Lock] = {}

    async def ingest_match(self, match_id: int) -> OpenDotaResult:
        lock = self._locks.setdefault(match_id, asyncio.Lock())
        async with lock:
            cached = await self._read_cache(match_id)
            if cached is not None:
                return cached
            await self._mark_pending(match_id)
            result = await self._provider.fetch_match(match_id)
            await self._save_result(result)
            return result

    async def _read_cache(self, match_id: int) -> OpenDotaResult | None:
        async with self._sessions() as session:
            match = await get_match(session, match_id)
            payload = match.raw_payload if match is not None else None
            if match is None or match.fetch_status == "pending" or not isinstance(payload, dict):
                return None
            status_value = payload.get("status")
            cache_until = payload.get("cache_until")
            try:
                if not isinstance(status_value, str) or not isinstance(cache_until, str):
                    return None
                status = OpenDotaStatus(status_value)
                valid_until = datetime.fromisoformat(cache_until)
            except (ValueError, TypeError):
                return None
            if status in {OpenDotaStatus.FOUND_FULL, OpenDotaStatus.FOUND_PARTIAL} and payload.get("player_public_data_version") != PLAYER_PUBLIC_DATA_VERSION:
                return None
            if valid_until.tzinfo is None or self._clock().astimezone(UTC) >= valid_until.astimezone(UTC):
                return None
            retry = payload.get("retry_after_seconds")
            retry_after = retry if isinstance(retry, int) and not isinstance(retry, bool) else None
            return OpenDotaResult(
                status, match_id, snapshot=dict(payload) if status in {
                    OpenDotaStatus.FOUND_FULL, OpenDotaStatus.FOUND_PARTIAL,
                } else None,
                retry_after_seconds=retry_after, from_cache=True,
            )

    async def _mark_pending(self, match_id: int) -> None:
        now = self._clock().astimezone(UTC)
        payload: JsonObject = {"schema_version": 1, "source": "opendota", "status": "PENDING"}
        async with self._sessions() as session, session.begin():
            await upsert_match(session, match_id, fetch_status="pending", raw_payload=payload, fetched_at=now)

    def _ttl(self, result: OpenDotaResult) -> int:
        if result.status in {OpenDotaStatus.FOUND_FULL, OpenDotaStatus.FOUND_PARTIAL}:
            return self._success_ttl
        if result.status == OpenDotaStatus.NOT_FOUND:
            return self._not_found_ttl
        if result.status == OpenDotaStatus.RATE_LIMITED and result.retry_after_seconds is not None:
            return min(max(result.retry_after_seconds, 1), 3600)
        return self._error_ttl

    async def _save_result(self, result: OpenDotaResult) -> None:
        now = self._clock().astimezone(UTC)
        payload: dict[str, Any] = dict(result.snapshot or {
            "schema_version": 1, "source": "opendota", "status": result.status.value,
        })
        payload["cache_until"] = (now + timedelta(seconds=self._ttl(result))).isoformat()
        if result.retry_after_seconds is not None:
            payload["retry_after_seconds"] = result.retry_after_seconds
        if result.status in {OpenDotaStatus.FOUND_FULL, OpenDotaStatus.FOUND_PARTIAL}:
            fetch_status: FetchStatus = "ready"
        elif result.status == OpenDotaStatus.NOT_FOUND:
            fetch_status = "unavailable"
        else:
            fetch_status = "failed"
        async with self._sessions() as session, session.begin():
            await upsert_match(
                session, result.match_id, fetch_status=fetch_status,
                raw_payload=cast(JsonObject, payload), fetched_at=now,
            )
