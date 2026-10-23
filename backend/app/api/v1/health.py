import asyncio
from typing import Annotated, cast

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.session import get_db_session
from app.models.error import ErrorResponse
from app.models.health import DatabaseHealthResponse, HealthResponse

router = APIRouter(prefix="/api/v1", tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health(response: Response) -> HealthResponse:
    response.headers["Cache-Control"] = "no-store"
    return HealthResponse()


@router.get("/health/db", response_model=DatabaseHealthResponse, responses={503: {"model": ErrorResponse}})
async def database_health(
    request: Request, response: Response,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DatabaseHealthResponse:
    config = cast(Settings, request.app.state.settings)
    try:
        async with asyncio.timeout(config.db_health_timeout_seconds):
            await session.execute(text("SELECT 1"))
    except Exception:
        # Never expose URLs, driver exceptions or SQL diagnostics in a public probe.
        raise HTTPException(status_code=503) from None
    response.headers["Cache-Control"] = "no-store"
    return DatabaseHealthResponse()
