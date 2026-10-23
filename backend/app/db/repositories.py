from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AnalysisStatus, Completeness, FetchStatus, JsonObject, Match, MatchAnalysis, TelegramUser, UserMatchHistory


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Timestamp must have a timezone")
    return value.astimezone(UTC)


@dataclass(frozen=True)
class VerifiedTelegramUser:
    """Internal identity, constructed ONLY after server initData validation.

    This type does not validate signatures and must never be deserialized from a client request.
    """

    telegram_user_id: int
    username: str | None = None
    display_name: str | None = None


async def get_telegram_user(session: AsyncSession, telegram_user_id: int) -> TelegramUser | None:
    return await session.get(TelegramUser, telegram_user_id)


async def upsert_verified_user(session: AsyncSession, user: VerifiedTelegramUser) -> TelegramUser:
    statement = insert(TelegramUser).values(
        telegram_user_id=user.telegram_user_id, username=user.username, display_name=user.display_name,
    )
    upsert = statement.on_conflict_do_update(
        index_elements=[TelegramUser.telegram_user_id],
        set_={"username": statement.excluded.username, "display_name": statement.excluded.display_name, "updated_at": func.now()},
    ).returning(TelegramUser)
    return (await session.scalars(upsert, execution_options={"populate_existing": True})).one()


async def upsert_match(
    session: AsyncSession, match_id: int, *, fetch_status: FetchStatus = "pending",
    raw_payload: JsonObject | None = None, fetched_at: datetime | None = None,
) -> Match:
    """Replace the current cache state; omitted payload/time explicitly mean NULL."""
    statement = insert(Match).values(
        match_id=match_id, fetch_status=fetch_status, raw_payload=raw_payload, fetched_at=_utc(fetched_at),
    )
    upsert = statement.on_conflict_do_update(
        index_elements=[Match.match_id],
        set_={"fetch_status": statement.excluded.fetch_status, "raw_payload": statement.excluded.raw_payload,
              "fetched_at": statement.excluded.fetched_at, "updated_at": func.now()},
    ).returning(Match)
    return (await session.scalars(upsert, execution_options={"populate_existing": True})).one()


async def get_match(session: AsyncSession, match_id: int) -> Match | None:
    return await session.get(Match, match_id)


async def save_analysis(
    session: AsyncSession, match_id: int, algorithm_version: str, *, status: AnalysisStatus = "pending",
    report_payload: JsonObject | None = None, completeness: Completeness | None = None,
    computed_at: datetime | None = None,
) -> MatchAnalysis:
    statement = insert(MatchAnalysis).values(
        match_id=match_id, algorithm_version=algorithm_version, status=status,
        report_payload=report_payload, completeness=completeness, computed_at=_utc(computed_at),
    )
    upsert = statement.on_conflict_do_update(
        constraint="uq_match_analyses_match_version",
        set_={"status": statement.excluded.status, "report_payload": statement.excluded.report_payload,
              "completeness": statement.excluded.completeness, "computed_at": statement.excluded.computed_at},
    ).returning(MatchAnalysis)
    return (await session.scalars(upsert, execution_options={"populate_existing": True})).one()


async def record_view(
    session: AsyncSession, user: VerifiedTelegramUser, match_id: int, *, viewed_at: datetime | None = None,
) -> UserMatchHistory:
    viewed_at = _utc(viewed_at) if viewed_at is not None else datetime.now(UTC)
    statement = insert(UserMatchHistory).values(
        telegram_user_id=user.telegram_user_id, match_id=match_id, last_viewed_at=viewed_at,
    )
    upsert = statement.on_conflict_do_update(
        constraint="uq_user_match_history_user_match",
        set_={"last_viewed_at": func.greatest(UserMatchHistory.last_viewed_at, statement.excluded.last_viewed_at)},
    ).returning(UserMatchHistory)
    return (await session.scalars(upsert, execution_options={"populate_existing": True})).one()


async def recent_matches(
    session: AsyncSession, user: VerifiedTelegramUser, *, limit: int = 20,
) -> list[UserMatchHistory]:
    if not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")
    statement = select(UserMatchHistory).where(
        UserMatchHistory.telegram_user_id == user.telegram_user_id,
    ).order_by(UserMatchHistory.last_viewed_at.desc(), UserMatchHistory.match_id.desc()).limit(limit)
    return list(await session.scalars(statement))
