from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any, TypeVar, cast

from aiogram import Bot, Dispatcher
from aiogram.client.session.base import BaseSession
from aiogram.methods import GetMe, SendMessage, TelegramMethod
from aiogram.types import Chat, Message, MessageEntity, Update, User
import pytest

from app.bot.handlers import BAD_MATCH_ID, GROUP_NOT_ALLOWED, PRIVATE_HELP, create_router
from app.bot.services import JobService
from app.integrations.opendota import OpenDotaResult, OpenDotaStatus
from auth_fixtures import AuthTestSettings

TelegramType = TypeVar("TelegramType")


class StubIngestion:
    def __init__(self) -> None:
        self.calls: list[int] = []

    async def ingest_match(self, match_id: int) -> OpenDotaResult:
        self.calls.append(match_id)
        return OpenDotaResult(OpenDotaStatus.FOUND_PARTIAL, match_id)


class StubSession(BaseSession):
    def __init__(self) -> None:
        super().__init__()
        self.sent: list[SendMessage] = []

    async def close(self) -> None:
        return None

    async def stream_content(
        self, url: str, headers: dict[str, Any] | None = None, timeout: int = 30,
        chunk_size: int = 65536, raise_for_status: bool = True,
    ) -> AsyncGenerator[bytes]:
        if False:
            yield b""

    async def make_request(
        self, bot: Bot, method: TelegramMethod[TelegramType], timeout: int | None = None,
    ) -> TelegramType:
        if isinstance(method, GetMe):
            return cast(TelegramType, User(id=999, is_bot=True, first_name="Fixture", username="FixtureBot"))
        if isinstance(method, SendMessage):
            self.sent.append(method)
            chat_id = int(method.chat_id)
            return cast(TelegramType, Message(
                message_id=1000 + len(self.sent), date=datetime.now(UTC),
                chat=Chat(id=chat_id, type="private" if chat_id > 0 else "supergroup"),
                text=method.text,
            ))
        raise AssertionError(f"Unexpected Bot API method: {type(method).__name__}")


def update(text: str, *, chat_id: int = -100123, chat_type: str = "supergroup", user_id: int = 42, update_id: int = 1) -> Update:
    command = text.split(maxsplit=1)[0]
    message = Message(
        message_id=update_id, date=datetime.now(UTC), chat=Chat(id=chat_id, type=chat_type),
        from_user=User(id=user_id, is_bot=False, first_name="Fixture"), text=text,
        entities=[MessageEntity(type="bot_command", offset=0, length=len(command))],
    )
    return Update(update_id=update_id, message=message)


def configured(*, allowed: list[int]) -> AuthTestSettings:
    return AuthTestSettings(telegram_allowed_chat_ids=allowed, telegram_match_cooldown_seconds=10)


async def dispatch(updates: list[Update], *, allowed: list[int]) -> list[SendMessage]:
    session = StubSession()
    bot = Bot("123456:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi", session=session)
    dispatcher = Dispatcher()
    jobs = JobService(10, StubIngestion(), lambda: 100.0)
    dispatcher.include_router(create_router(configured(allowed=allowed), jobs))
    for item in updates:
        await dispatcher.feed_update(bot, item)
    await jobs.wait_pending()
    await bot.session.close()
    return session.sent


async def test_group_match_and_addressed_command_ingest_in_background() -> None:
    sent = await dispatch([
        update("/match 123456789", update_id=1),
        update("/match@FixtureBot 987654321", user_id=43, update_id=2),
    ], allowed=[-100123])
    assert [message.chat_id for message in sent] == [-100123] * 4
    assert "Match ID 123456789 принят" in sent[0].text
    assert "Match ID 987654321 принят" in sent[1].text
    assert "получены частично" in sent[2].text
    assert "получены частично" in sent[3].text
    assert all(message.parse_mode is None for message in sent)


async def test_command_for_another_bot_is_ignored() -> None:
    sent = await dispatch([update("/match@AnotherBot 123", update_id=3)], allowed=[-100123])
    assert sent == []


@pytest.mark.parametrize("text", [
    "/match", "/match ", "/match 0", "/match -1", "/match 123 extra", "/match https://example.org/123",
    "/match@FixtureBot", "/match 9223372036854775808", "/match <b>123</b>",
])
async def test_invalid_match_id_has_friendly_error(text: str) -> None:
    sent = await dispatch([update(text)], allowed=[-100123])
    assert len(sent) == 1 and sent[0].text == BAD_MATCH_ID


async def test_allowlist_is_fail_closed() -> None:
    assert (await dispatch([update("/match 123")], allowed=[]))[0].text == GROUP_NOT_ALLOWED
    assert (await dispatch([update("/match 123")], allowed=[-999]))[0].text == GROUP_NOT_ALLOWED


async def test_cooldown_only_blocks_same_user_in_same_chat() -> None:
    sent = await dispatch([
        update("/match 100", user_id=1, update_id=10),
        update("/match 101", user_id=1, update_id=11),
        update("/match 102", user_id=2, update_id=12),
    ], allowed=[-100123])
    assert "Match ID 100 принят" in sent[0].text
    assert "Повторите через 10 сек." in sent[1].text
    assert "Match ID 102 принят" in sent[2].text
    assert len(sent) == 5


async def test_private_chat_explains_group_usage() -> None:
    for text in ("/start", "/help", "/match 123"):
        sent = await dispatch([update(text, chat_id=42, chat_type="private")], allowed=[-100123])
        assert len(sent) == 1 and sent[0].text == PRIVATE_HELP


async def test_group_help_is_available_without_allowlist() -> None:
    sent = await dispatch([update("/help")], allowed=[])
    assert len(sent) == 1 and "/match <match_id>" in sent[0].text


async def test_duplicate_update_does_not_trigger_external_calls() -> None:
    repeated = update("/match 123", update_id=50)
    sent = await dispatch([repeated, repeated], allowed=[-100123])
    assert len(sent) == 3
    assert "Match ID 123 принят" in sent[0].text
    assert "Слишком частые запросы" in sent[1].text
