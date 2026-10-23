from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import JsonValue
from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

type FetchStatus = Literal["pending", "ready", "unavailable", "failed"]
type AnalysisStatus = Literal["pending", "ready", "failed"]
type Completeness = Literal["full", "partial", "missing"]
type JsonObject = dict[str, JsonValue]


class Timestamps:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
    )


class TelegramUser(Timestamps, Base):
    __tablename__ = "telegram_users"
    __table_args__ = (CheckConstraint("telegram_user_id > 0", name="positive_id"),)

    telegram_user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    username: Mapped[str | None] = mapped_column(String(64))
    display_name: Mapped[str | None] = mapped_column(String(256))


class Match(Timestamps, Base):
    __tablename__ = "matches"
    __table_args__ = (
        CheckConstraint("match_id > 0", name="positive_id"),
        CheckConstraint("fetch_status IN ('pending','ready','unavailable','failed')", name="fetch_status"),
    )

    match_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    fetch_status: Mapped[FetchStatus] = mapped_column(String(16), server_default="pending")
    raw_payload: Mapped[JsonObject | None] = mapped_column(JSONB(none_as_null=True))
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MatchAnalysis(Base):
    __tablename__ = "match_analyses"
    __table_args__ = (
        UniqueConstraint("match_id", "algorithm_version", name="uq_match_analyses_match_version"),
        CheckConstraint("status IN ('pending','ready','failed')", name="status"),
        CheckConstraint("completeness IN ('full','partial','missing')", name="completeness"),
        CheckConstraint("length(trim(algorithm_version)) > 0", name="algorithm_version"),
        Index("ix_match_analyses_match_id", "match_id"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    match_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("matches.match_id", ondelete="RESTRICT"))
    algorithm_version: Mapped[str] = mapped_column(String(64))
    status: Mapped[AnalysisStatus] = mapped_column(String(16), server_default="pending")
    report_payload: Mapped[JsonObject | None] = mapped_column(JSONB(none_as_null=True))
    completeness: Mapped[Completeness | None] = mapped_column(String(16))
    computed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UserMatchHistory(Base):
    __tablename__ = "user_match_history"
    __table_args__ = (
        UniqueConstraint("telegram_user_id", "match_id", name="uq_user_match_history_user_match"),
        Index("ix_user_match_history_match_id", "match_id"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    telegram_user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("telegram_users.telegram_user_id", ondelete="RESTRICT"),
    )
    match_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("matches.match_id", ondelete="RESTRICT"))
    last_viewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


Index("ix_user_match_history_user_recent", UserMatchHistory.telegram_user_id, UserMatchHistory.last_viewed_at.desc())
