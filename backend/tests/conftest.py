from collections.abc import AsyncIterator
from pathlib import Path

from alembic import command
from alembic.config import Config
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
import pytest
import pytest_asyncio
from sqlalchemy import Connection
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.session import Database

BACKEND = Path(__file__).resolve().parents[1]


class TestDatabaseSettings(BaseSettings):
    __test__ = False
    model_config = SettingsConfigDict(env_file=BACKEND / ".env", extra="ignore", hide_input_in_errors=True)
    test_database_url: SecretStr | None = Field(default=None, validation_alias="TEST_DATABASE_URL")
    migration_test_database_url: SecretStr | None = Field(default=None, validation_alias="MIGRATION_TEST_DATABASE_URL")


def checked_test_url(secret: SecretStr | None, expected_name: str) -> str:
    if secret is None:
        pytest.skip(f"Separate local {expected_name} PostgreSQL is not configured")
    url = make_url(secret.get_secret_value())
    if url.drivername != "postgresql+asyncpg" or url.host not in {"127.0.0.1", "localhost", "::1"} or url.database != expected_name:
        pytest.fail("Tests require the explicitly named local PostgreSQL test database; URL is not displayed")
    dev = Settings().database_url
    if dev is not None and make_url(dev.get_secret_value()).database == expected_name:
        pytest.fail("Test database must be distinct from the development database")
    return secret.get_secret_value()


@pytest.fixture(scope="session")
def pg_url() -> str:
    return checked_test_url(TestDatabaseSettings().test_database_url, "dota_hub_test")


def migrate(connection: Connection) -> None:
    config = Config(str(BACKEND / "alembic.ini"))
    config.attributes["connection"] = connection
    command.upgrade(config, "head")


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def prepared_pg(pg_url: str) -> None:
    database = Database(pg_url)
    try:
        async with database.engine.begin() as connection:
            await connection.run_sync(migrate)
    finally:
        await database.close()


@pytest_asyncio.fixture
async def db_session(pg_url: str, prepared_pg: None) -> AsyncIterator[AsyncSession]:
    database = Database(pg_url)
    try:
        async with database.engine.connect() as connection:
            transaction = await connection.begin()
            try:
                async with AsyncSession(
                    bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint",
                ) as session:
                    yield session
            finally:
                await transaction.rollback()
    finally:
        await database.close()
