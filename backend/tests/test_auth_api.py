from collections.abc import AsyncIterator
import json
import time
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from fastapi import Request
from httpx import ASGITransport, AsyncClient
import jwt
import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import TelegramUser
from app.db.repositories import VerifiedTelegramUser, upsert_verified_user
from app.main import create_app
from app.services.sessions import auth_secrets, create_session
from auth_fixtures import USER_ID, AuthTestSettings, auth_settings, fields, signed


def test_public_health_missing_auth_and_config() -> None:
    settings = AuthTestSettings(database_url=None, bot_token=None, session_secret=None)
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/v1/health").status_code == 200
        missing = client.get("/api/v1/auth/me?userId=1")
        assert missing.status_code == 401 and missing.headers["www-authenticate"] == "Bearer"
        assert client.post("/api/v1/auth/telegram", json={"init_data": "placeholder"}).status_code == 503
        assert client.get("/api/v1/health/db").status_code == 503


def test_invalid_input_never_reaches_database_or_leaks(caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch) -> None:
    caplog.set_level("INFO")
    settings = auth_settings()
    bot, key = auth_secrets(settings)
    application = create_app(settings)

    async def forbidden_database(request: Request) -> AsyncIterator[AsyncSession]:
        raise AssertionError("Invalid authentication reached the database")
        yield  # pragma: no cover

    monkeypatch.setattr("app.api.v1.auth.get_db_session", forbidden_database)
    raw = signed(fields(), bot + "wrong")
    with TestClient(application) as client:
        for body in ({"init_data": raw}, {"init_data": ""}, {"init_data": raw, raw: key}, {"userId": USER_ID}, {"init_data": 123}):
            response = client.post("/api/v1/auth/telegram", json=body)
            assert response.status_code in {401, 422}
            assert response.headers["cache-control"] == "no-store"
            assert all(value not in response.text for value in (raw, bot, key))
        for token in ("invalid", create_session(USER_ID, key + "wrong", 900)):
            assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401
        assert client.get("/api/v1/auth/me", headers=[("Authorization", "Bearer a"), ("Authorization", "Bearer b")]).status_code == 401
        malformed = client.post("/api/v1/auth/telegram", content='{"init_data":', headers={"Content-Type": "application/json"})
        assert malformed.status_code == 422 and malformed.json()["error"]["details"] == []
    assert all(value not in caplog.text for value in (raw, bot, key))


def test_cors_is_explicit() -> None:
    settings = auth_settings()
    settings.cors_origins.append("https://mini.example.org")
    with TestClient(create_app(settings)) as client:
        for origin in settings.cors_origins:
            response = client.options("/api/v1/auth/telegram", headers={"Origin": origin, "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "authorization,content-type"})
            assert response.status_code == 200 and response.headers["access-control-allow-origin"] == origin
            assert "access-control-allow-credentials" not in response.headers
        response = client.options("/api/v1/auth/telegram", headers={"Origin": "https://evil.example.org", "Access-Control-Request-Method": "POST"})
        assert response.status_code == 400 and "access-control-allow-origin" not in response.headers


@pytest.mark.postgres
async def test_login_upsert_me_and_rejections(db_session: AsyncSession, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch) -> None:
    caplog.set_level("INFO")
    settings = auth_settings()
    bot, key = auth_secrets(settings)
    application = create_app(settings)

    async def test_session(request: Request) -> AsyncIterator[AsyncSession]:
        async with AsyncSession(bind=db_session.bind, expire_on_commit=False, join_transaction_mode="create_savepoint") as session:
            yield session

    monkeypatch.setattr("app.api.v1.auth.get_db_session", test_session)
    raw = signed(fields(), bot)
    async with application.router.lifespan_context(application):
        async with AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as client:
            first = await client.post("/api/v1/auth/telegram", json={"init_data": raw})
            assert first.status_code == 200
            body = first.json()
            assert body["token_type"] == "bearer" and body["expires_in"] == 900
            assert body["user"]["telegram_user_id"] == str(USER_ID)
            assert first.headers["cache-control"] == "no-store"
            token = body["access_token"]
            headers = {"Authorization": f"Bearer {token}"}
            me = await client.get("/api/v1/auth/me?userId=1", headers=headers)
            assert me.status_code == 200 and me.json() == body["user"]
            assert me.headers["cache-control"] == "no-store"
            updated_raw = signed(fields(user=json.dumps({"id": USER_ID, "first_name": "Updated fixture", "username": "fixture"})), bot)
            second = await client.post("/api/v1/auth/telegram", json={"init_data": updated_raw})
            assert second.status_code == 200
            assert second.json()["user"]["display_name"] == "Updated fixture"
            assert second.json()["user"]["created_at"] == body["user"]["created_at"]
            assert (await client.get("/api/v1/auth/me", headers=headers)).json()["display_name"] == "Updated fixture"
            assert await db_session.scalar(select(func.count()).select_from(TelegramUser).where(TelegramUser.telegram_user_id == USER_ID)) == 1
            # Invalid HMAC must not create a different user or mutate the existing one.
            rejected = await client.post("/api/v1/auth/telegram", json={"init_data": signed(fields(user=json.dumps({"id": USER_ID + 1, "first_name": "Forged fixture"})), bot + "wrong")})
            assert rejected.status_code == 401
            assert await db_session.get(TelegramUser, USER_ID + 1) is None
            absent = create_session(USER_ID + 1, key, 900)
            assert (await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {absent}"})).status_code == 401
            claims = jwt.decode(token, key, algorithms=["HS256"], audience="dota-hub-miniapp")
            claims.update(iat=int(time.time())-1000, nbf=int(time.time())-1000, exp=int(time.time())-100)
            expired = jwt.encode(claims, key, algorithm="HS256")
            expiry = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {expired}"})
            assert expiry.status_code == 401 and expiry.json()["error"]["code"] == "SESSION_EXPIRED"
            # Expected DB failures must be sanitized and cannot issue a session.
            with patch("app.api.v1.auth.upsert_verified_user", new=AsyncMock(side_effect=SQLAlchemyError(raw + bot + key))):
                failure = await client.post("/api/v1/auth/telegram", json={"init_data": raw})
            assert failure.status_code == 503 and "access_token" not in failure.json()
            async def fail_after_write(session: AsyncSession, identity: VerifiedTelegramUser) -> TelegramUser:
                await upsert_verified_user(session, identity)
                raise SQLAlchemyError("synthetic transaction failure")

            with patch("app.api.v1.auth.upsert_verified_user", new=fail_after_write):
                rollback = await client.post("/api/v1/auth/telegram", json={"init_data": raw})
            assert rollback.status_code == 503
            restored = await client.get("/api/v1/auth/me", headers=headers)
            assert restored.json()["display_name"] == "Updated fixture"
            for response in (first, second, me, rejected, expiry, failure):
                assert all(value not in response.text for value in (raw, updated_raw, bot, key))
    assert all(value not in caplog.text for value in (raw, updated_raw, bot, key, token))
