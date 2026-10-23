from datetime import UTC, datetime

from aiogram import Bot, Dispatcher
import pytest

from app.bot.handlers import create_router
from app.bot.services import JobService, result_message
from app.integrations.opendota import OpenDotaResult, OpenDotaStatus, parse_match_response
from app.models.matches import NormalizedMatch
from app.models.performance import RuinerReport
from app.services.match_normalization import normalize_match_snapshot
from app.services.performance import analyze_performance, format_performance_summary
from test_bot_handlers import StubSession, configured, update
from test_performance import performance_snapshot


class SnapshotIngestion:
    async def ingest_match(self, match_id: int) -> OpenDotaResult:
        payload = performance_snapshot()['match']
        payload['match_id'] = match_id
        return parse_match_response(match_id, payload, datetime(2026, 10, 22, tzinfo=UTC))


async def test_ingestion_normalization_shared_evaluator_bot_notification() -> None:
    ingestion = SnapshotIngestion()
    result = await ingestion.ingest_match(12345)
    assert result.snapshot is not None
    expected = analyze_performance(normalize_match_snapshot(result.snapshot))
    service = JobService(10, ingestion)
    messages: list[str] = []
    async def notify(text: str) -> None:
        messages.append(text)
    service.start_request(12345, notify)
    await service.wait_pending()
    assert messages == [result_message(result) + '\n\n' + format_performance_summary(expected)]
    assert len(messages[0]) < 4096
    assert 'Radiant' in messages[0] and 'Dire' in messages[0]


async def test_group_dispatcher_publishes_both_teams_through_stub_transport() -> None:
    session = StubSession()
    bot = Bot('999:fixture-token-only', session=session)
    jobs = JobService(10, SnapshotIngestion())
    dispatcher = Dispatcher()
    dispatcher.include_router(create_router(configured(allowed=[-100123]), jobs))
    try:
        await dispatcher.feed_update(bot, update('/match 12345'))
        await jobs.wait_pending()
        assert len(session.sent) == 2
        assert session.sent[0].chat_id == session.sent[1].chat_id == -100123
        assert 'принят' in session.sent[0].text
        assert 'Radiant' in session.sent[1].text and 'Dire' in session.sent[1].text
        assert session.sent[1].parse_mode is None
    finally:
        await jobs.close()
        await bot.session.close()


async def test_analysis_failure_preserves_ingestion_success_and_does_not_leak_exception(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture,
) -> None:
    def fail(match: NormalizedMatch) -> RuinerReport:
        raise RuntimeError('private-failure-marker')
    monkeypatch.setattr('app.bot.services.analyze_performance', fail)
    jobs = JobService(10, SnapshotIngestion())
    messages: list[str] = []
    async def notify(text: str) -> None:
        messages.append(text)
    jobs.start_request(12345, notify)
    await jobs.wait_pending()
    assert len(messages) == 1 and 'сохранены' in messages[0] and 'недоступен' in messages[0]
    assert 'private-failure-marker' not in messages[0] + caplog.text


async def test_unavailable_match_does_not_call_evaluator(monkeypatch: pytest.MonkeyPatch) -> None:
    called = []
    def fail(match: NormalizedMatch) -> RuinerReport:
        called.append(True)
        raise AssertionError('should not evaluate unavailable match')
    class UnavailableIngestion:
        async def ingest_match(self, match_id: int) -> OpenDotaResult:
            return OpenDotaResult(OpenDotaStatus.NOT_FOUND, match_id)
    monkeypatch.setattr('app.bot.services.analyze_performance', fail)
    jobs = JobService(10, UnavailableIngestion())
    messages: list[str] = []
    async def notify(text: str) -> None:
        messages.append(text)
    jobs.start_request(12345, notify)
    await jobs.wait_pending()
    assert not called and 'не найден' in messages[0]


async def test_mismatched_snapshot_identity_is_not_published() -> None:
    class WrongIngestion:
        async def ingest_match(self, match_id: int) -> OpenDotaResult:
            return OpenDotaResult(OpenDotaStatus.FOUND_PARTIAL, match_id, snapshot=performance_snapshot())
    jobs = JobService(10, WrongIngestion())
    messages: list[str] = []
    async def notify(text: str) -> None:
        messages.append(text)
    jobs.start_request(98765, notify)
    await jobs.wait_pending()
    assert len(messages) == 1 and '98765' in messages[0]
    assert '12345' not in messages[0] and 'Radiant' not in messages[0]
