"""Authenticated, read-only stored match reports. GET never schedules analysis."""
import json
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import current_user, session_database
from app.bot.services import InvalidMatchId, parse_match_id
from app.core.errors import PublicError
from app.db.models import Match
from app.models.draft import DraftReport
from app.models.match_api import (
    SECTIONS,
    AnalysisState,
    MatchEnvelope,
    MatchError,
    OverviewReport,
    PlayersReport,
    Section,
)
from app.models.matches import StrictDTO, Team
from app.models.performance import RuinerReport
from app.models.timeline import TimelineReport
from app.services.match_analysis import (
    ERRORS,
    FLOW_VERSION,
    SECTION_VERSIONS,
    get_analysis,
)
from app.services.timeline import EVENT_TYPES, filter_timeline_events
from app.services.performance_preliminary import project_preliminary

router = APIRouter(prefix='/api/v1/matches', tags=['matches'], dependencies=[Depends(current_user)], responses={
    code: {'model': MatchEnvelope[AnalysisState]} for code in (202, 401, 403, 404, 422, 429, 502, 503)
})
DB = Annotated[AsyncSession, Depends(session_database)]


def match_id_value(match_id: str) -> int:
    try:
        return parse_match_id(match_id)
    except InvalidMatchId:
        raise PublicError(422, 'INVALID_MATCH_ID', 'Укажите положительный целочисленный Match ID') from None


def response(body: MatchEnvelope[Any], code: int = 200) -> JSONResponse:
    headers = {'Cache-Control': 'no-store'}
    if body.retry_after_seconds is not None:
        headers['Retry-After'] = str(body.retry_after_seconds)
    return JSONResponse(status_code=code, content=body.model_dump(mode='json'), headers=headers)


async def stored(match_id: str, section: Section | None, dto: type[StrictDTO], session: AsyncSession,
                 event_type: str | None = None, side: Team | None = None) -> JSONResponse:
    number = match_id_value(match_id)
    try:
        match = await session.get(Match, number)
        if match is None:
            raise PublicError(404, 'MATCH_NOT_FOUND', 'Матч пока не запрашивали через /match')
        row = await get_analysis(session, number, FLOW_VERSION)
        state: dict[str, Any] = dict(row.report_payload) if row and row.report_payload else {}
        status = state.get('state', 'failed')
        if status not in ('queued', 'running', 'ready', 'failed'):
            raise PublicError(503, 'REPORT_UNAVAILABLE', 'Сохранённый анализ недоступен')
        available = tuple(s for s in SECTIONS if s in state.get('available_sections', []))
        error_code = state.get('error_code')
        if row is None:
            # An older snapshot is not a queued job: GET must not imply an active worker.
            error_code = 'ANALYSIS_FAILED'
        error = None
        if status == 'failed':
            error_code = error_code if isinstance(error_code, str) and error_code in ERRORS else 'ANALYSIS_FAILED'
            http_status, message, retryable = ERRORS[error_code]
            error = MatchError(code=error_code, message=message, retryable=retryable)
        else:
            http_status = 202 if status in ('queued', 'running') else 200
        base: dict[str, Any] = {'match_id': match_id, 'status': status, 'available_sections': available,
                               'error': error, 'limitations': (error.message,) if error else ()}
        if section is None:
            return response(MatchEnvelope[AnalysisState](**base, data=AnalysisState(
                status=status, available_sections=available, error_code=error_code), analyzed_at=row.computed_at if row else None))
        if status in ('queued', 'running'):
            return response(MatchEnvelope[Any](**base, retry_after_seconds=2), 202)
        if section not in available:
            retry = state.get('retry_after_seconds')
            if isinstance(retry, bool) or not isinstance(retry, int) or retry < 1:
                retry = None
            if error is None:
                raise PublicError(503, 'REPORT_UNAVAILABLE', 'Раздел анализа недоступен')
            return response(MatchEnvelope[Any](**base, retry_after_seconds=retry), http_status)
        report = await get_analysis(session, number, SECTION_VERSIONS[section])
        payload: dict[str, Any] | None = dict(report.report_payload) if report and report.status == 'ready' and report.report_payload else None
        if not payload or payload.get('source_digest') != state.get('source_digest'):
            raise PublicError(503, 'REPORT_UNAVAILABLE', 'Сохранённый анализ недоступен')
        data = dto.model_validate_json(json.dumps(payload['data']))
        if isinstance(data, RuinerReport):
            data = project_preliminary(data)
        if getattr(data, 'match_id', None) != match_id:
            raise PublicError(503, 'REPORT_UNAVAILABLE', 'Сохранённый анализ недоступен')
        if isinstance(data, TimelineReport) and (event_type is not None or side is not None):
            data = data.model_copy(update={'events': filter_timeline_events(data, event_type=event_type, team=side)})
        return response(MatchEnvelope[Any](**{**base, 'status': 'ready',
                                             'limitations': tuple(payload.get('limitations', [])) + base['limitations']}, data=data,
            model_version=payload.get('model_version'), config_version=payload.get('config_version'),
            analyzed_at=report.computed_at if report else None, completeness=report.completeness if report else None))
    except (SQLAlchemyError, OSError, TimeoutError):
        raise PublicError(503, 'DATABASE_UNAVAILABLE', 'База данных недоступна') from None
    except (ValidationError, KeyError, TypeError, ValueError):
        raise PublicError(503, 'REPORT_UNAVAILABLE', 'Сохранённый анализ недоступен') from None


@router.get('/{match_id}/overview', response_model=MatchEnvelope[OverviewReport])
async def overview(match_id: str, session: DB) -> JSONResponse:
    return await stored(match_id, 'overview', OverviewReport, session)


@router.get('/{match_id}/players', response_model=MatchEnvelope[PlayersReport])
async def players(match_id: str, session: DB) -> JSONResponse:
    return await stored(match_id, 'players', PlayersReport, session)


@router.get('/{match_id}/draft', response_model=MatchEnvelope[DraftReport])
async def draft(match_id: str, session: DB) -> JSONResponse:
    return await stored(match_id, 'draft', DraftReport, session)


@router.get('/{match_id}/ruiner', response_model=MatchEnvelope[RuinerReport])
async def ruiner(match_id: str, session: DB) -> JSONResponse:
    return await stored(match_id, 'ruiner', RuinerReport, session)


@router.get('/{match_id}/timeline', response_model=MatchEnvelope[TimelineReport])
async def timeline(match_id: str, session: DB, event_type: Annotated[str | None, Query(alias='type')] = None,
                   side: Team | None = None) -> JSONResponse:
    if event_type is not None and event_type not in EVENT_TYPES:
        raise PublicError(422, 'INVALID_EVENT_TYPE', 'Неизвестный тип события')
    return await stored(match_id, 'timeline', TimelineReport, session, event_type, side)


@router.get('/{match_id}/analysis/status', response_model=MatchEnvelope[AnalysisState])
async def analysis_status(match_id: str, session: DB) -> JSONResponse:
    return await stored(match_id, None, AnalysisState, session)
