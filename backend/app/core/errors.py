from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from app.models.error import ApiError, ErrorDetail, ErrorResponse
from app.models.match_api import MatchEnvelope, MatchError


class PublicError(HTTPException):
    """Only fixed application-owned messages belong here, never exception/input text."""

    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(status, headers={"WWW-Authenticate": "Bearer"} if status == 401 else None)
        self.code = code
        self.message = message


async def error_handler(request: Request, exc: Exception) -> JSONResponse:
    status = 500
    code, message = "INTERNAL_ERROR", "Внутренняя ошибка сервера"
    details: list[ErrorDetail] = []
    headers: dict[str, str] = {}
    if isinstance(exc, PublicError):
        status, code, message = exc.status_code, exc.code, exc.message
        headers = dict(exc.headers or {})
    elif isinstance(exc, HTTPException):
        status = exc.status_code
        headers = dict(exc.headers or {})
        code, message = {
            404: ("NOT_FOUND", "Ресурс не найден"),
            405: ("METHOD_NOT_ALLOWED", "Метод не поддерживается"),
            503: ("DATABASE_UNAVAILABLE", "База данных недоступна"),
        }.get(status, ("HTTP_ERROR", "Запрос не выполнен"))
    elif isinstance(exc, RequestValidationError):
        status = 422
        code, message = "VALIDATION_ERROR", "Проверьте параметры запроса"
        # Do not echo input values or arbitrary exception messages.
        details = [] if request.url.path.startswith("/api/v1/auth/") else [
            ErrorDetail(
                field=".".join(str(part) for part in error["loc"]),
                message="Некорректное значение",
            )
            for error in exc.errors()
        ]
    headers["Cache-Control"] = "no-store"
    if request.url.path.startswith('/api/v1/matches/') and request.scope.get('route') is not None:
        envelope = MatchEnvelope[dict[str, str]](
            status='failed', error=MatchError(code=code, message=message, retryable=status in (429, 500, 502, 503)),
            limitations=(message,),
        )
        return JSONResponse(status_code=status, content=envelope.model_dump(mode='json'), headers=headers)
    body = ErrorResponse(error=ApiError(code=code, message=message, details=details))
    return JSONResponse(status_code=status, content=body.model_dump(), headers=headers)
