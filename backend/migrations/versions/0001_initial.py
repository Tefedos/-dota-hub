"""Initial PostgreSQL schema. No existing tables or data are modified."""
from collections.abc import Sequence

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "telegram_users",
        sa.Column("telegram_user_id", sa.BigInteger(), autoincrement=False, nullable=False),
        sa.Column("username", sa.String(64), nullable=True),
        sa.Column("display_name", sa.String(256), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("telegram_user_id > 0", name=op.f("ck_telegram_users_positive_id")),
        sa.PrimaryKeyConstraint("telegram_user_id", name=op.f("pk_telegram_users")),
    )
    op.create_table(
        "matches",
        sa.Column("match_id", sa.BigInteger(), autoincrement=False, nullable=False),
        sa.Column("fetch_status", sa.String(16), server_default="pending", nullable=False),
        sa.Column("raw_payload", postgresql.JSONB(none_as_null=True), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("match_id > 0", name=op.f("ck_matches_positive_id")),
        sa.CheckConstraint("fetch_status IN ('pending','ready','unavailable','failed')", name=op.f("ck_matches_fetch_status")),
        sa.PrimaryKeyConstraint("match_id", name=op.f("pk_matches")),
    )
    op.create_table(
        "match_analyses",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("match_id", sa.BigInteger(), nullable=False),
        sa.Column("algorithm_version", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), server_default="pending", nullable=False),
        sa.Column("report_payload", postgresql.JSONB(none_as_null=True), nullable=True),
        sa.Column("completeness", sa.String(16), nullable=True),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("status IN ('pending','ready','failed')", name=op.f("ck_match_analyses_status")),
        sa.CheckConstraint("completeness IN ('full','partial','missing')", name=op.f("ck_match_analyses_completeness")),
        sa.CheckConstraint("length(trim(algorithm_version)) > 0", name=op.f("ck_match_analyses_algorithm_version")),
        sa.ForeignKeyConstraint(["match_id"], ["matches.match_id"], name=op.f("fk_match_analyses_match_id_matches"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_match_analyses")),
        sa.UniqueConstraint("match_id", "algorithm_version", name="uq_match_analyses_match_version"),
    )
    op.create_index("ix_match_analyses_match_id", "match_analyses", ["match_id"])
    op.create_table(
        "user_match_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("match_id", sa.BigInteger(), nullable=False),
        sa.Column("last_viewed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["telegram_user_id"], ["telegram_users.telegram_user_id"], name=op.f("fk_user_match_history_telegram_user_id_telegram_users"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["match_id"], ["matches.match_id"], name=op.f("fk_user_match_history_match_id_matches"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_match_history")),
        sa.UniqueConstraint("telegram_user_id", "match_id", name="uq_user_match_history_user_match"),
    )
    op.create_index("ix_user_match_history_match_id", "user_match_history", ["match_id"])
    op.create_index("ix_user_match_history_user_recent", "user_match_history", ["telegram_user_id", sa.text("last_viewed_at DESC")])


def downgrade() -> None:
    # This initial downgrade is only for an explicitly selected EMPTY local migration-test DB.
    # It must never silently drop application data or run against dev/production.
    if context.is_offline_mode():
        raise RuntimeError("Offline downgrade is not supported")
    if context.get_x_argument(as_dictionary=True).get("allow_empty_test_downgrade") != "true":
        raise RuntimeError("Downgrade requires explicit empty migration-test database approval")
    bind = op.get_bind()
    database = bind.scalar(sa.text("SELECT current_database()"))
    host = bind.engine.url.host
    if database != "dota_hub_migration_test" or host not in {"127.0.0.1", "localhost", "::1"}:
        raise RuntimeError("Downgrade is restricted to the local dota_hub_migration_test database")
    for table in ("telegram_users", "matches", "match_analyses", "user_match_history"):
        if bind.scalar(sa.text(f'SELECT EXISTS (SELECT 1 FROM "{table}" LIMIT 1)')):
            raise RuntimeError("Downgrade refused: the migration-test tables must be empty")
    op.drop_table("user_match_history")
    op.drop_table("match_analyses")
    op.drop_table("matches")
    op.drop_table("telegram_users")
