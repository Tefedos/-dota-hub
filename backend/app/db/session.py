from collections.abc import AsyncGenerator
from typing import cast

from fastapi import HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


class Database:
    """One lazy engine and pool per application lifespan, not per request."""

    def __init__(self, url: str) -> None:
        self.engine = create_async_engine(
            url, echo=False, hide_parameters=True, pool_pre_ping=True,
            pool_size=5, max_overflow=5, pool_timeout=2,
            connect_args={"timeout": 2, "command_timeout": 3, "server_settings": {"timezone": "UTC"}},
        )
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)

    async def close(self) -> None:
        await self.engine.dispose()


async def get_db_session(request: Request) -> AsyncGenerator[AsyncSession]:
    database = cast(Database | None, request.app.state.database)
    if database is None:
        raise HTTPException(status_code=503)
    async with database.sessions() as session:
        # Callers own the transaction: use `async with session.begin()` for writes.
        # Closing the session rolls back any uncommitted work, including on failure.
        yield session
