from argparse import Namespace

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import Connection, inspect, text

from app.db.session import Database
from conftest import BACKEND, TestDatabaseSettings, checked_test_url

TABLES = {"telegram_users", "matches", "match_analyses", "user_match_history"}


def migration_cycle(connection: Connection) -> None:
    existing = set(inspect(connection).get_table_names())
    if existing - TABLES - {"alembic_version"}:
        pytest.fail("Migration-test database has unexpected tables; refusing to modify it")
    for table in existing & TABLES:
        if connection.scalar(text(f'SELECT EXISTS (SELECT 1 FROM "{table}" LIMIT 1)')):
            pytest.fail("Migration-test database contains rows; refusing to modify it")
    config = Config(str(BACKEND / "alembic.ini"))
    config.attributes["connection"] = connection
    command.upgrade(config, "head")
    command.upgrade(config, "head")
    command.check(config)
    inspector = inspect(connection)
    assert set(inspector.get_table_names()) == TABLES | {"alembic_version"}
    assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0001_initial"
    types = {column["name"]: str(column["type"]) for column in inspector.get_columns("match_analyses")}
    assert types["id"] == "UUID" and types["match_id"] == "BIGINT" and types["report_payload"] == "JSONB"
    assert {index["name"] for index in inspector.get_indexes("user_match_history")} >= {"ix_user_match_history_user_recent", "ix_user_match_history_match_id"}
    assert len(inspector.get_foreign_keys("user_match_history")) == 2
    assert any(constraint["column_names"] == ["match_id", "algorithm_version"] for constraint in inspector.get_unique_constraints("match_analyses"))
    with pytest.raises(RuntimeError, match="explicit"):
        command.downgrade(config, "base")
    config.cmd_opts = Namespace(x=["allow_empty_test_downgrade=true"])
    savepoint = connection.begin_nested()
    connection.execute(text("INSERT INTO matches (match_id) VALUES (1)"))
    with pytest.raises(RuntimeError, match="empty"):
        command.downgrade(config, "base")
    savepoint.rollback()
    command.downgrade(config, "base")
    assert set(inspect(connection).get_table_names()) == {"alembic_version"}
    command.upgrade(config, "head")
    command.check(config)
    assert set(inspect(connection).get_table_names()) == TABLES | {"alembic_version"}


@pytest.mark.postgres
async def test_migrations_on_separate_empty_postgresql() -> None:
    url = checked_test_url(TestDatabaseSettings().migration_test_database_url, "dota_hub_migration_test")
    database = Database(url)
    try:
        async with database.engine.begin() as connection:
            await connection.run_sync(migration_cycle)
    finally:
        await database.close()
