import time
from typing import Annotated

from fastapi import Depends
from fastapi.testclient import TestClient
from pydantic import SecretStr
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.session import get_db_session
from app.main import create_app


def test_liveness_without_database_and_safe_unavailable_response() -> None:
    config = Settings(database_url=None)
    with TestClient(create_app(config)) as client:
        assert client.get("/api/v1/health").json() == {"status": "ok", "service": "dota-hub-api"}
        response = client.get("/api/v1/health/db")
    assert response.status_code == 503
    assert response.json() == {"error": {"code": "DATABASE_UNAVAILABLE", "message": "База данных недоступна", "details": []}}
    assert response.headers["cache-control"] == "no-store"


def test_unreachable_database_does_not_break_liveness_or_leak_errors() -> None:
    config = Settings(database_url=SecretStr("postgresql+asyncpg://unused@127.0.0.1:1/unavailable"), db_health_timeout_seconds=0.2)
    with TestClient(create_app(config)) as client:
        started = time.monotonic()
        response = client.get("/api/v1/health/db")
        assert time.monotonic() - started < 5
        assert client.get("/api/v1/health").status_code == 200
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "DATABASE_UNAVAILABLE"
    assert all(value not in response.text for value in ("127.0.0.1", "postgresql", "SELECT", "unused", "Traceback"))


@pytest.mark.postgres
def test_live_database_and_one_session_per_request(pg_url: str) -> None:
    application = create_app(Settings(database_url=SecretStr(pg_url)))

    @application.get("/test-session")
    async def same_session(
        first: Annotated[AsyncSession, Depends(get_db_session)],
        second: Annotated[AsyncSession, Depends(get_db_session)],
    ) -> dict[str, bool]:
        await first.execute(text("SELECT 1"))
        return {"same": first is second}

    with TestClient(application) as client:
        response = client.get("/api/v1/health/db")
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "database": "available"}
        assert response.headers["cache-control"] == "no-store"
        for _ in range(12):
            assert client.get("/test-session").json() == {"same": True}


@pytest.mark.postgres
async def test_request_failure_rolls_back_pending_writes(pg_url: str, db_session: AsyncSession) -> None:
    application = create_app(Settings(database_url=SecretStr(pg_url)))

    @application.post("/test-rollback")
    async def fail(session: Annotated[AsyncSession, Depends(get_db_session)]) -> None:
        await session.execute(text("INSERT INTO matches (match_id) VALUES (9223372036854775001)"))
        raise RuntimeError("fixture failure")

    with TestClient(application, raise_server_exceptions=False) as client:
        assert client.post("/test-rollback").status_code == 500
    assert await db_session.scalar(text("SELECT count(*) FROM matches WHERE match_id = 9223372036854775001")) == 0
