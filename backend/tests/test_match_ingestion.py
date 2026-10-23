import asyncio
from datetime import UTC, datetime, timedelta
from typing import cast

import pytest
from sqlalchemy import delete

from app.db.models import JsonObject, Match
from app.db.repositories import upsert_match
from app.db.session import Database
from app.integrations.opendota import OpenDotaResult, OpenDotaStatus
from app.services.match_ingestion import MatchIngestionService

pytestmark = pytest.mark.postgres
MATCH_ID = 9_000_000_000_000_111


class FakeProvider:
    def __init__(self, result: OpenDotaResult, *, pause: bool = False) -> None:
        self.result = result
        self.calls = 0
        self.pause = pause

    async def fetch_match(self, match_id: int) -> OpenDotaResult:
        self.calls += 1
        if self.pause:
            await asyncio.sleep(0.01)
        return self.result


def snapshot(status: OpenDotaStatus) -> dict[str, object]:
    return {
        "schema_version": 1, "player_public_data_version": 1, "source": "opendota", "source_fetched_at": datetime.now(UTC).isoformat(),
        "status": status.value, "presence": {}, "match": {"match_id": MATCH_ID},
    }


def service(database: Database, provider: FakeProvider, now: list[datetime]) -> MatchIngestionService:
    return MatchIngestionService(
        database.sessions, provider, success_ttl_seconds=60, error_ttl_seconds=10,
        not_found_ttl_seconds=20, clock=lambda: now[0],
    )


async def cleanup(database: Database) -> None:
    async with database.sessions() as session, session.begin():
        await session.execute(delete(Match).where(Match.match_id.between(MATCH_ID, MATCH_ID + 20)))


async def test_concurrent_requests_cache_restart_and_ttl(pg_url: str, prepared_pg: None) -> None:
    database = Database(pg_url)
    now = [datetime(2026, 1, 1, tzinfo=UTC)]
    result = OpenDotaResult(OpenDotaStatus.FOUND_FULL, MATCH_ID, snapshot(OpenDotaStatus.FOUND_FULL))
    provider = FakeProvider(result, pause=True)
    ingestion = service(database, provider, now)
    try:
        first, second = await asyncio.gather(ingestion.ingest_match(MATCH_ID), ingestion.ingest_match(MATCH_ID))
        assert provider.calls == 1 and {first.from_cache, second.from_cache} == {False, True}
        restart_provider = FakeProvider(result)
        restarted = service(database, restart_provider, now)
        assert (await restarted.ingest_match(MATCH_ID)).from_cache is True
        assert restart_provider.calls == 0
        now[0] += timedelta(seconds=61)
        assert (await restarted.ingest_match(MATCH_ID)).from_cache is False
        assert restart_provider.calls == 1
        async with database.sessions() as session:
            row = await session.get(Match, MATCH_ID)
            assert row is not None and row.fetch_status == "ready"
            assert row.raw_payload is not None and row.raw_payload["cache_until"]
    finally:
        await cleanup(database)
        await database.close()


async def test_old_cached_snapshot_without_public_player_version_is_refetched(pg_url: str, prepared_pg: None) -> None:
    database = Database(pg_url)
    now = [datetime(2026, 1, 1, tzinfo=UTC)]
    provider = FakeProvider(OpenDotaResult(OpenDotaStatus.FOUND_FULL, MATCH_ID, snapshot(OpenDotaStatus.FOUND_FULL)))
    try:
        old = snapshot(OpenDotaStatus.FOUND_FULL)
        old.pop("player_public_data_version")
        old["cache_until"] = (now[0] + timedelta(seconds=60)).isoformat()
        async with database.sessions() as session, session.begin():
            await upsert_match(session, MATCH_ID, fetch_status="ready", raw_payload=cast(JsonObject, old), fetched_at=now[0])
        result = await service(database, provider, now).ingest_match(MATCH_ID)
        assert result.from_cache is False and provider.calls == 1
        assert result.snapshot is not None and result.snapshot["player_public_data_version"] == 1
    finally:
        await cleanup(database)
        await database.close()


async def test_pending_row_is_recovered_after_restart(pg_url: str, prepared_pg: None) -> None:
    database = Database(pg_url)
    now = [datetime(2026, 1, 1, tzinfo=UTC)]
    provider = FakeProvider(OpenDotaResult(OpenDotaStatus.NOT_FOUND, MATCH_ID + 1))
    try:
        async with database.sessions() as session, session.begin():
            await upsert_match(
                session, MATCH_ID + 1, fetch_status="pending",
                raw_payload={"schema_version": 1, "source": "opendota", "status": "PENDING"},
                fetched_at=now[0],
            )
        result = await service(database, provider, now).ingest_match(MATCH_ID + 1)
        assert result.status == OpenDotaStatus.NOT_FOUND and provider.calls == 1
        async with database.sessions() as session:
            row = await session.get(Match, MATCH_ID + 1)
            assert row is not None and row.fetch_status == "unavailable"
    finally:
        await cleanup(database)
        await database.close()


@pytest.mark.parametrize("status,db_status", [
    (OpenDotaStatus.RATE_LIMITED, "failed"),
    (OpenDotaStatus.API_UNAVAILABLE, "failed"),
    (OpenDotaStatus.MALFORMED_RESPONSE, "failed"),
])
async def test_error_statuses_are_cached_without_response_body(
    pg_url: str, prepared_pg: None, status: OpenDotaStatus, db_status: str,
) -> None:
    database = Database(pg_url)
    offset = list(OpenDotaStatus).index(status) + 2
    match_id = MATCH_ID + offset
    now = [datetime(2026, 1, 1, tzinfo=UTC)]
    provider = FakeProvider(OpenDotaResult(status, match_id, retry_after_seconds=5))
    try:
        await service(database, provider, now).ingest_match(match_id)
        async with database.sessions() as session:
            row = await session.get(Match, match_id)
            assert row is not None and row.fetch_status == db_status
            assert row.raw_payload is not None and "match" not in row.raw_payload
    finally:
        await cleanup(database)
        await database.close()
