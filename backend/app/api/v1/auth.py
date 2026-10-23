import time
from collections.abc import AsyncIterator
from contextlib import aclosing
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import PublicError
from app.db.models import TelegramUser
from app.db.repositories import VerifiedTelegramUser, get_telegram_user, upsert_verified_user
from app.db.session import get_db_session
from app.models.auth import TelegramLoginRequest, TelegramLoginResponse, UserResponse
from app.models.error import ErrorResponse
from app.services.sessions import auth_secrets, create_session, read_session
from app.services.telegram_auth import InvalidInitData, validate_init_data

router = APIRouter(prefix="/api/v1/auth", tags=["auth"], responses={
    401: {"model": ErrorResponse}, 422: {"model": ErrorResponse}, 503: {"model": ErrorResponse},
})
bearer = HTTPBearer(auto_error=False)


def get_settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


def verified_login(body: TelegramLoginRequest, settings: Annotated[Settings, Depends(get_settings)]) -> VerifiedTelegramUser:
    bot, _ = auth_secrets(settings)
    try:
        return validate_init_data(
            body.init_data, bot, now=int(time.time()), max_age=settings.telegram_init_data_max_age_seconds,
            clock_skew=settings.telegram_clock_skew_seconds,
        )
    except InvalidInitData:
        raise PublicError(401, "INVALID_INIT_DATA", "Не удалось подтвердить вход через Telegram") from None


def session_user_id(
    request: Request, credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> int:
    if credentials is None or len(request.headers.getlist("authorization")) != 1:
        raise PublicError(401, "AUTH_REQUIRED", "Требуется вход через Telegram")
    _, key = auth_secrets(settings)
    return read_session(credentials.credentials, key)


async def login_database(
    request: Request, identity: Annotated[VerifiedTelegramUser, Depends(verified_login)],
) -> AsyncIterator[AsyncSession]:
    # A nested dependency is skipped on invalid body/auth; an independent DB dependency is not.
    async with aclosing(get_db_session(request)) as sessions:
        async for session in sessions:
            yield session


async def session_database(
    request: Request, user_id: Annotated[int, Depends(session_user_id)],
) -> AsyncIterator[AsyncSession]:
    async with aclosing(get_db_session(request)) as sessions:
        async for session in sessions:
            yield session


async def current_user(
    user_id: Annotated[int, Depends(session_user_id)], session: Annotated[AsyncSession, Depends(session_database)],
) -> TelegramUser:
    try:
        user = await get_telegram_user(session, user_id)
    except (SQLAlchemyError, OSError, TimeoutError):
        raise PublicError(503, "DATABASE_UNAVAILABLE", "База данных недоступна") from None
    if user is None:
        raise PublicError(401, "INVALID_SESSION", "Сессия недействительна")
    return user


def profile(user: TelegramUser) -> UserResponse:
    return UserResponse(
        telegram_user_id=str(user.telegram_user_id), username=user.username, display_name=user.display_name,
        created_at=user.created_at, updated_at=user.updated_at,
    )


@router.post("/telegram", response_model=TelegramLoginResponse)
async def telegram_login(
    response: Response, identity: Annotated[VerifiedTelegramUser, Depends(verified_login)],
    session: Annotated[AsyncSession, Depends(login_database)], settings: Annotated[Settings, Depends(get_settings)],
) -> TelegramLoginResponse:
    _, key = auth_secrets(settings)
    try:
        async with session.begin():
            user = await upsert_verified_user(session, identity)
        # Do not issue a session until the upsert has committed successfully.
    except (SQLAlchemyError, OSError, TimeoutError):
        raise PublicError(503, "DATABASE_UNAVAILABLE", "База данных недоступна") from None
    response.headers["Cache-Control"] = "no-store"
    return TelegramLoginResponse(
        access_token=create_session(user.telegram_user_id, key, settings.session_ttl_seconds),
        expires_in=settings.session_ttl_seconds, user=profile(user),
    )


@router.get("/me", response_model=UserResponse)
async def me(response: Response, user: Annotated[TelegramUser, Depends(current_user)]) -> UserResponse:
    response.headers["Cache-Control"] = "no-store"
    return profile(user)
