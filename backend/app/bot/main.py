import asyncio
import logging

from aiogram import Bot, Dispatcher
from sqlalchemy import text

from app.bot.handlers import create_router
from app.bot.services import JobService
from app.core.config import Settings
from app.db.session import Database
from app.integrations.opendota import OpenDotaClient
from app.integrations.opendota_matchups import OpenDotaMatchups
from app.services.match_analysis import MatchAnalysisService
from app.services.match_ingestion import MatchIngestionService


class MissingBotToken(RuntimeError):
    pass


class MissingDatabaseUrl(RuntimeError):
    pass


async def run_polling() -> None:
    settings = Settings()
    if settings.bot_token is None:
        raise MissingBotToken("BOT_TOKEN is required to run the Telegram bot")
    token = settings.bot_token.get_secret_value()
    if not token:
        raise MissingBotToken("BOT_TOKEN is required to run the Telegram bot")
    if settings.database_url is None:
        raise MissingDatabaseUrl("DATABASE_URL is required to run the Telegram bot")

    bot = Bot(token=token)
    database = Database(settings.database_url.get_secret_value())
    api_key = settings.open_dota_api_key.get_secret_value() if settings.open_dota_api_key else None
    open_dota = OpenDotaClient(
        base_url=settings.open_dota_base_url, api_key=api_key,
        timeout_seconds=settings.open_dota_timeout_seconds, max_retries=settings.open_dota_max_retries,
        backoff_seconds=settings.open_dota_retry_backoff_seconds,
    )
    ingestion = MatchIngestionService(
        database.sessions, open_dota, success_ttl_seconds=settings.open_dota_cache_ttl_seconds,
        error_ttl_seconds=settings.open_dota_error_cache_ttl_seconds,
        not_found_ttl_seconds=settings.open_dota_not_found_cache_ttl_seconds,
    )
    dispatcher = Dispatcher()
    analysis = MatchAnalysisService(database.sessions, ingestion, OpenDotaMatchups(open_dota))
    jobs = JobService(settings.telegram_match_cooldown_seconds, ingestion, analysis=analysis)
    try:
        # A session-level DB lock also prevents a second local worker from recovering live jobs.
        async with database.engine.connect() as worker:
            locked = await worker.scalar(text('SELECT pg_try_advisory_lock(-71009001)'))
            if not locked:
                raise RuntimeError('A Dota Hub polling worker is already running')
            try:
                identity = await bot.me()
                if not identity.username or (settings.bot_username and settings.bot_username.lower() != identity.username.lower()):
                    raise RuntimeError('BOT_USERNAME does not match the configured bot')
                settings.bot_username = identity.username
                await analysis.recover_interrupted()
                dispatcher.include_router(create_router(settings, jobs))
                # Polling and webhook must never run simultaneously on the same token.
                await bot.delete_webhook(drop_pending_updates=False)
                await dispatcher.start_polling(bot, allowed_updates=dispatcher.resolve_used_update_types())
            finally:
                await jobs.close()
                await worker.execute(text('SELECT pg_advisory_unlock(-71009001)'))
    finally:
        await jobs.close()
        await open_dota.close()
        await database.close()
        await bot.session.close()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("aiogram.event").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    try:
        asyncio.run(run_polling())
    except (MissingBotToken, MissingDatabaseUrl) as error:
        raise SystemExit(str(error)) from None
    except Exception as error:  # noqa: BLE001 - isolate external failures without leaking exception text
        logging.getLogger(__name__).error('Bot stopped error_type=%s', type(error).__name__)
        raise SystemExit('Bot stopped; check startup configuration and database availability') from None


if __name__ == "__main__":
    main()
