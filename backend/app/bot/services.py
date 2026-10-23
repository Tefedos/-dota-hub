import asyncio
import logging
import re
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol
from urllib.parse import urlencode

from app.integrations.opendota import OpenDotaResult, OpenDotaStatus
from app.services.match_normalization import normalize_match_snapshot
from app.services.performance import analyze_performance, format_performance_summary

logger = logging.getLogger(__name__)


class Ingestion(Protocol):
    async def ingest_match(self, match_id: int) -> OpenDotaResult: ...


class AnalysisProcessor(Protocol):
    async def process(self, match_id: int) -> str: ...

MAX_BIGINT = 2**63 - 1


class InvalidMatchId(ValueError):
    pass


def parse_match_id(value: str | None) -> int:
    """Accept a canonical positive signed-BIGINT decimal only."""
    if value is None or not re.fullmatch(r"[1-9][0-9]{0,18}", value):
        raise InvalidMatchId()
    match_id = int(value)
    if match_id > MAX_BIGINT:
        raise InvalidMatchId()
    return match_id


def mini_app_deep_link(bot_username: str, match_id: int) -> str:
    username = bot_username.removeprefix("@")
    if not re.fullmatch(r"[A-Za-z0-9_]{5,32}", username):
        raise ValueError("Invalid bot username")
    validated_id = parse_match_id(str(match_id))
    payload = f"match_{validated_id}"
    if len(payload) > 64 or not re.fullmatch(r"[A-Za-z0-9_-]+", payload):
        raise ValueError("Invalid Mini App payload")
    return f"https://t.me/{username}?{urlencode({'startapp': payload})}"


class RequestStatus(StrEnum):
    ACCEPTED = "ACCEPTED"
    COOLDOWN = "COOLDOWN"


@dataclass(frozen=True)
class MatchRequestResult:
    status: RequestStatus
    match_id: int
    retry_after_seconds: int | None = None


class JobService:
    """Acknowledge quickly, then retain in-process ingestion tasks until shutdown."""

    def __init__(
        self, cooldown_seconds: int, ingestion: Ingestion,
        clock: Callable[[], float] = time.monotonic,
        *, analysis: AnalysisProcessor | None = None,
    ) -> None:
        self._cooldown = cooldown_seconds
        self._ingestion = ingestion
        self._clock = clock
        self._analysis = analysis
        self._group_requests: dict[int, list[float]] = {}
        self._last_requests: dict[tuple[int, int], float] = {}
        self._tasks: set[asyncio.Task[None]] = set()

    def reserve_request(self, match_id: int, requested_by: int, chat_id: int) -> MatchRequestResult:
        parse_match_id(str(match_id))
        if requested_by <= 0 or chat_id >= 0:
            raise ValueError("Invalid Telegram request context")
        now = self._clock()
        self._group_requests = {chat: [t for t in times if now - t < 60] for chat, times in self._group_requests.items() if any(now - t < 60 for t in times)}
        recent = self._group_requests.get(chat_id, [])
        if len(recent) >= 10 or len(self._tasks) >= 32:
            return MatchRequestResult(RequestStatus.COOLDOWN, match_id, retry_after_seconds=60)
        key = (chat_id, requested_by)
        self._last_requests = {
            request_key: requested_at for request_key, requested_at in self._last_requests.items()
            if now - requested_at < self._cooldown
        }
        previous = self._last_requests.get(key)
        if previous is not None and now - previous < self._cooldown:
            remaining = max(1, int(self._cooldown - (now - previous) + 0.999))
            return MatchRequestResult(RequestStatus.COOLDOWN, match_id, retry_after_seconds=remaining)
        self._last_requests[key] = now
        self._group_requests.setdefault(chat_id, []).append(now)
        return MatchRequestResult(RequestStatus.ACCEPTED, match_id)

    def start_request(self, match_id: int, notify: Callable[[str], Awaitable[None]]) -> None:
        task = asyncio.create_task(self._run(match_id, notify), name=f"match-ingestion-{match_id}")
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _run(self, match_id: int, notify: Callable[[str], Awaitable[None]]) -> None:
        if self._analysis is not None:
            try:
                message = await self._analysis.process(match_id)
            except Exception as error:  # noqa: BLE001 - isolate external failures without leaking exception text
                logger.error('Group flow failed match_id=%s error_type=%s', match_id, type(error).__name__)
                message = 'Анализ временно недоступен. Повторите /match позже.'
            try:
                await notify(message)
            except Exception as error:  # noqa: BLE001 - isolate external failures without leaking exception text
                logger.error('Telegram result delivery failed match_id=%s error_type=%s', match_id, type(error).__name__)
            return
        try:
            result = await self._ingestion.ingest_match(match_id)
        except Exception as error:  # noqa: BLE001 - isolate external failures without leaking exception text
            logger.error("Match ingestion failed match_id=%s error_type=%s", match_id, type(error).__name__)
            result = OpenDotaResult(OpenDotaStatus.API_UNAVAILABLE, match_id)
        message = result_message(result)
        if result.status in {OpenDotaStatus.FOUND_FULL, OpenDotaStatus.FOUND_PARTIAL} and result.snapshot is not None:
            try:
                normalized = normalize_match_snapshot(result.snapshot)
                if normalized.summary.match_id != str(match_id):
                    raise ValueError('analysis match identity mismatch')
                report = analyze_performance(normalized)
                message += '\n\n' + format_performance_summary(report)
            except Exception as error:  # noqa: BLE001 - isolate external failures without leaking exception text
                logger.error("Performance analysis failed match_id=%s error_type=%s", match_id, type(error).__name__)
                message += '\nАнализ исполнения сейчас недоступен; данные матча сохранены.'
        try:
            await notify(message)
        except Exception as error:  # noqa: BLE001 - isolate external failures without leaking exception text
            logger.error("Telegram result delivery failed match_id=%s error_type=%s", match_id, type(error).__name__)

    async def wait_pending(self) -> None:
        if self._tasks:
            await asyncio.gather(*tuple(self._tasks))

    async def close(self) -> None:
        for task in tuple(self._tasks):
            task.cancel()
        if self._tasks:
            await asyncio.gather(*tuple(self._tasks), return_exceptions=True)


def result_message(result: OpenDotaResult) -> str:
    cached = " (из локального кэша)" if result.from_cache else ""
    if result.status == OpenDotaStatus.FOUND_FULL:
        return f"Данные матча {result.match_id} получены и сохранены{cached}."
    if result.status == OpenDotaStatus.FOUND_PARTIAL:
        return f"Данные матча {result.match_id} получены частично и сохранены{cached}."
    if result.status == OpenDotaStatus.NOT_FOUND:
        return f"Матч {result.match_id} не найден в OpenDota{cached}."
    if result.status == OpenDotaStatus.RATE_LIMITED:
        suffix = f" Повторите примерно через {result.retry_after_seconds} сек." if result.retry_after_seconds else " Повторите позже."
        return "OpenDota временно ограничила частоту запросов." + suffix
    if result.status == OpenDotaStatus.MALFORMED_RESPONSE:
        return "OpenDota вернула некорректные данные матча. Повторите позже."
    return "OpenDota временно недоступна. Повторите позже."
