from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException

from app.api.v1.auth import router as auth_router
from app.api.v1.health import router as health_router
from app.api.v1.matches import router as matches_router
from app.api.v1.local_alpha import router as local_alpha_router
from app.core.config import Settings
from app.core.errors import error_handler
from app.db.session import Database
from app.integrations.opendota import OpenDotaClient
from app.integrations.opendota_matchups import OpenDotaMatchups
from app.services.match_ingestion import MatchIngestionService
from app.services.match_analysis import MatchAnalysisService


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings if settings is not None else Settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        database = Database(config.database_url.get_secret_value()) if config.database_url else None
        application.state.database = database
        application.state.settings = config
        local_client = None
        if config.local_alpha and database is not None:
            local_client = OpenDotaClient(
                base_url=config.open_dota_base_url,
                api_key=config.open_dota_api_key.get_secret_value() if config.open_dota_api_key else None,
                timeout_seconds=config.open_dota_timeout_seconds,
                max_retries=config.open_dota_max_retries,
                backoff_seconds=config.open_dota_retry_backoff_seconds,
            )
            ingestion = MatchIngestionService(
                database.sessions, local_client,
                success_ttl_seconds=config.open_dota_cache_ttl_seconds,
                error_ttl_seconds=config.open_dota_error_cache_ttl_seconds,
                not_found_ttl_seconds=config.open_dota_not_found_cache_ttl_seconds,
            )
            application.state.local_analysis = MatchAnalysisService(database.sessions, ingestion, OpenDotaMatchups(local_client))
        try:
            yield
        finally:
            if local_client is not None:
                await local_client.close()
            if database is not None:
                await database.close()

    application = FastAPI(
        title="Dota Hub API",
        version="0.1.0",
        debug=False,
        lifespan=lifespan,
        docs_url="/docs" if config.docs_enabled else None,
        redoc_url=None,
        openapi_url="/openapi.json" if config.docs_enabled else None,
    )
    application.add_exception_handler(HTTPException, error_handler)
    application.add_exception_handler(RequestValidationError, error_handler)
    application.add_exception_handler(Exception, error_handler)
    application.add_middleware(
        CORSMiddleware, allow_origins=config.cors_origins, allow_credentials=False,
        allow_methods=["GET", "POST"], allow_headers=["Authorization", "Content-Type"],
    )
    application.include_router(health_router)
    application.include_router(auth_router)
    application.include_router(matches_router)
    if config.local_alpha:
        application.include_router(local_alpha_router)
    return application


app = create_app()
