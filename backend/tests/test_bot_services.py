from collections.abc import Callable, Iterator

import pytest

from app.bot.services import InvalidMatchId, JobService, RequestStatus, mini_app_deep_link, parse_match_id
from app.integrations.opendota import OpenDotaResult, OpenDotaStatus


class StubIngestion:
    async def ingest_match(self, match_id: int) -> OpenDotaResult:
        return OpenDotaResult(OpenDotaStatus.FOUND_PARTIAL, match_id)


@pytest.mark.parametrize("value", ["1", "123456789", "9223372036854775807"])
def test_match_id_accepts_canonical_positive_bigint(value: str) -> None:
    assert parse_match_id(value) == int(value)


@pytest.mark.parametrize("value", [
    None, "", " ", "0", "-1", "+1", "01", "1.0", "1e3", "1 2", "123\n", "https://example.org/123",
    "9223372036854775808", "9" * 100, "１２３", "123_456", "<b>123</b>",
])
def test_match_id_rejects_ambiguous_or_unsafe_input(value: str | None) -> None:
    with pytest.raises(InvalidMatchId):
        parse_match_id(value)


def test_main_mini_app_link_has_validated_payload() -> None:
    assert mini_app_deep_link("@FixtureBot", 123456789) == "https://t.me/FixtureBot?startapp=match_123456789"
    for username in ("bad", "bad-name", "https://t.me/bot", "x" * 33):
        with pytest.raises(ValueError):
            mini_app_deep_link(username, 123)
    with pytest.raises(InvalidMatchId):
        mini_app_deep_link("FixtureBot", 0)


def clock(values: list[float]) -> tuple[Iterator[float], Callable[[], float]]:
    iterator = iter(values)
    return iterator, lambda: next(iterator)


async def test_job_service_cooldown_is_per_chat_and_user() -> None:
    _, now = clock([100, 101, 102, 111])
    service = JobService(10, StubIngestion(), now)
    first = service.reserve_request(100, requested_by=1, chat_id=-100)
    same_user = service.reserve_request(101, requested_by=1, chat_id=-100)
    another_user = service.reserve_request(102, requested_by=2, chat_id=-100)
    after_cooldown = service.reserve_request(103, requested_by=1, chat_id=-100)
    assert first.status == RequestStatus.ACCEPTED
    assert same_user.status == RequestStatus.COOLDOWN and same_user.retry_after_seconds == 9
    assert another_user.status == RequestStatus.ACCEPTED
    assert after_cooldown.status == RequestStatus.ACCEPTED


async def test_job_service_runs_ingestion_and_notifies() -> None:
    service = JobService(10, StubIngestion())
    messages: list[str] = []

    async def notify(text: str) -> None:
        messages.append(text)

    service.start_request(123, notify)
    await service.wait_pending()
    assert messages == ["Данные матча 123 получены частично и сохранены."]
    with pytest.raises(ValueError):
        service.reserve_request(123, requested_by=0, chat_id=-100)
