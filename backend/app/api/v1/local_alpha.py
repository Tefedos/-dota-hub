"""Explicitly enabled, loopback-only browser QA path. Never registered in normal runs."""
import asyncio
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.matches import match_id_value, stored
from app.core.errors import PublicError
from app.db.session import get_db_session
from app.models.draft import DraftReport
from app.models.match_api import OverviewReport, PlayersReport, Section
from app.models.performance import RuinerReport
from app.models.timeline import TimelineReport
from app.models.matches import StrictDTO
from app.services.match_analysis import MatchAnalysisService

router = APIRouter(prefix="/api/v1/local-alpha", tags=["local-alpha"])
_processing = asyncio.Lock()
_models: dict[Section, type[StrictDTO]] = {"overview": OverviewReport, "players": PlayersReport, "draft": DraftReport,
                                          "ruiner": RuinerReport, "timeline": TimelineReport}


def loopback_only(request: Request) -> None:
    if request.client is None or request.client.host not in {"127.0.0.1", "::1"}:
        raise PublicError(404, "NOT_FOUND", "Ресурс не найден")
    if request.url.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise PublicError(404, "NOT_FOUND", "Ресурс не найден")
    origin = request.headers.get("origin")
    if origin is not None and origin not in {"http://127.0.0.1:5173", "http://localhost:5173"}:
        raise PublicError(403, "ORIGIN_DENIED", "Недопустимый источник запроса")


LocalRequest = Annotated[None, Depends(loopback_only)]
DB = Annotated[AsyncSession, Depends(get_db_session)]


@router.post("/matches/{match_id}/analyze")
async def analyze(match_id: str, request: Request, _local: LocalRequest) -> JSONResponse:
    number = match_id_value(match_id)
    if _processing.locked():
        raise PublicError(429, "ANALYSIS_BUSY", "Локальный анализ уже выполняется")
    service = cast(MatchAnalysisService, request.app.state.local_analysis)
    async with _processing:
        message = await service.process(number)
    return JSONResponse({"match_id": match_id, "message": message}, headers={"Cache-Control": "no-store"})


@router.get("/matches/{match_id}/{section}")
async def section(match_id: str, section: Section, _local: LocalRequest, session: DB) -> JSONResponse:
    return await stored(match_id, section, _models[section], session)
