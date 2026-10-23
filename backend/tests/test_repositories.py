from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Match, MatchAnalysis
from app.db.repositories import VerifiedTelegramUser, recent_matches, record_view, save_analysis, upsert_match, upsert_verified_user

pytestmark = pytest.mark.postgres
USER = VerifiedTelegramUser(9007199254740993)
MATCH_ID = 9007199254740995


async def test_user_upsert_preserves_bigint_and_creation(db_session: AsyncSession) -> None:
    first = await upsert_verified_user(db_session, USER)
    created = first.created_at
    updated = await upsert_verified_user(db_session, VerifiedTelegramUser(USER.telegram_user_id, "fixture_user", "Test fixture"))
    assert updated.telegram_user_id == USER.telegram_user_id
    assert updated.username == "fixture_user"
    assert updated.display_name == "Test fixture"
    assert updated.created_at == created
    assert updated.updated_at.utcoffset() == timedelta(0)
    assert updated.updated_at >= created
    count = await db_session.scalar(text("SELECT count(*) FROM telegram_users WHERE telegram_user_id = :id"), {"id": USER.telegram_user_id})
    assert count == 1


async def test_match_upsert_jsonb_and_null(db_session: AsyncSession) -> None:
    first = await upsert_match(db_session, MATCH_ID)
    assert first.fetch_status == "pending" and first.raw_payload is None
    assert await db_session.scalar(text("SELECT raw_payload IS NULL FROM matches WHERE match_id = :id"), {"id": MATCH_ID})
    now = datetime.now(UTC)
    updated = await upsert_match(db_session, MATCH_ID, fetch_status="ready", raw_payload={"test_fixture": True, "nested": {"values": [1, None]}}, fetched_at=now)
    assert updated.match_id == MATCH_ID
    assert updated.raw_payload == {"test_fixture": True, "nested": {"values": [1, None]}}
    assert updated.fetched_at == now
    assert updated.created_at.utcoffset() == timedelta(0)
    assert len(list(await db_session.scalars(select(Match).where(Match.match_id == MATCH_ID)))) == 1


async def test_analysis_versions_are_unique_and_keep_uuid(db_session: AsyncSession) -> None:
    await upsert_match(db_session, MATCH_ID)
    first = await save_analysis(db_session, MATCH_ID, "fixture-v1")
    first_id = first.id
    assert isinstance(first_id, UUID)
    updated = await save_analysis(db_session, MATCH_ID, "fixture-v1", status="ready", report_payload={"test_fixture": True}, completeness="partial", computed_at=datetime.now(UTC))
    second = await save_analysis(db_session, MATCH_ID, "fixture-v2")
    assert updated.id == first_id and second.id != first_id
    assert updated.status == "ready" and updated.report_payload == {"test_fixture": True}
    assert updated.computed_at is not None and updated.computed_at.utcoffset() == timedelta(0)
    assert len(list(await db_session.scalars(select(MatchAnalysis).where(MatchAnalysis.match_id == MATCH_ID)))) == 2


async def test_history_upsert_order_isolation_and_late_events(db_session: AsyncSession) -> None:
    await upsert_verified_user(db_session, USER)
    other = VerifiedTelegramUser(USER.telegram_user_id + 1)
    await upsert_verified_user(db_session, other)
    start = datetime(2026, 1, 1, tzinfo=UTC)
    for offset in range(3):
        await upsert_match(db_session, MATCH_ID + offset)
        await record_view(db_session, USER, MATCH_ID + offset, viewed_at=start + timedelta(hours=offset))
    original = await record_view(db_session, USER, MATCH_ID, viewed_at=start + timedelta(hours=4))
    old_id = original.id
    late = await record_view(db_session, USER, MATCH_ID, viewed_at=start)
    await record_view(db_session, other, MATCH_ID + 2)
    assert late.id == old_id
    assert late.last_viewed_at == start + timedelta(hours=4)
    history = await recent_matches(db_session, USER, limit=2)
    assert [entry.match_id for entry in history] == [MATCH_ID, MATCH_ID + 2]
    assert all(entry.telegram_user_id == USER.telegram_user_id for entry in history)
    assert len(await recent_matches(db_session, USER)) == 3
    assert len(await recent_matches(db_session, other)) == 1


@pytest.mark.parametrize("statement", [
    "INSERT INTO telegram_users (telegram_user_id) VALUES (9007199254740993)",
    "INSERT INTO matches (match_id) VALUES (9007199254740995)",
    "INSERT INTO match_analyses (match_id, algorithm_version) VALUES (9007199254740995, 'fixture-v1')",
    "INSERT INTO user_match_history (telegram_user_id, match_id) VALUES (9007199254740993, 9007199254740995)",
    "INSERT INTO match_analyses (match_id, algorithm_version) VALUES (77777, 'fixture-v1')",
    "INSERT INTO user_match_history (telegram_user_id, match_id) VALUES (77777, 9007199254740995)",
    "INSERT INTO user_match_history (telegram_user_id, match_id) VALUES (9007199254740993, 77777)",
    "UPDATE matches SET fetch_status = 'invented' WHERE match_id = 9007199254740995",
    "UPDATE match_analyses SET status = 'invented' WHERE match_id = 9007199254740995",
    "UPDATE match_analyses SET completeness = 'invented' WHERE match_id = 9007199254740995",
    "UPDATE match_analyses SET algorithm_version = '' WHERE match_id = 9007199254740995",
    "INSERT INTO matches (match_id) VALUES (0)",
    "INSERT INTO telegram_users (telegram_user_id) VALUES (-1)",
    "DELETE FROM matches WHERE match_id = 9007199254740995",
    "DELETE FROM telegram_users WHERE telegram_user_id = 9007199254740993",
])
async def test_database_constraints(db_session: AsyncSession, statement: str) -> None:
    await upsert_verified_user(db_session, USER)
    await upsert_match(db_session, MATCH_ID)
    await save_analysis(db_session, MATCH_ID, "fixture-v1")
    await record_view(db_session, USER, MATCH_ID)
    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            await db_session.execute(text(statement))


async def test_repository_input_boundaries(db_session: AsyncSession) -> None:
    with pytest.raises(ValueError, match="timezone"):
        await record_view(db_session, USER, MATCH_ID, viewed_at=datetime(2026, 1, 1))
    with pytest.raises(ValueError, match="timezone"):
        await upsert_match(db_session, MATCH_ID, fetched_at=datetime(2026, 1, 1))
    with pytest.raises(ValueError, match="timezone"):
        await save_analysis(db_session, MATCH_ID, "fixture-v1", computed_at=datetime(2026, 1, 1))
    for limit in (0, 101):
        with pytest.raises(ValueError, match="limit"):
            await recent_matches(db_session, USER, limit=limit)


async def test_transaction_rollback(db_session: AsyncSession) -> None:
    with pytest.raises(RuntimeError):
        async with db_session.begin_nested():
            await upsert_match(db_session, MATCH_ID)
            raise RuntimeError("fixture transaction rollback")
    assert await db_session.get(Match, MATCH_ID) is None
