from unittest.mock import patch

from pydantic import SecretStr, ValidationError
import pytest

from app.bot.main import run_polling
from auth_fixtures import AuthTestSettings


def test_bot_settings_are_safe_by_default() -> None:
    settings = AuthTestSettings()
    assert settings.telegram_allowed_chat_ids == []
    assert settings.telegram_match_cooldown_seconds == 10


def test_bot_settings_load_exact_env_names(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOT_USERNAME", "FixtureBot")
    monkeypatch.setenv("TELEGRAM_ALLOWED_CHAT_IDS", "[-100123,-100456]")
    monkeypatch.setenv("DOTA_TELEGRAM_MATCH_COOLDOWN_SECONDS", "17")
    monkeypatch.setenv("OPEN_DOTA_API_KEY", "fixture-open-dota-key")
    monkeypatch.setenv("DOTA_OPEN_DOTA_TIMEOUT_SECONDS", "12")
    settings = AuthTestSettings()
    assert settings.bot_username == "FixtureBot"
    assert settings.telegram_allowed_chat_ids == [-100123, -100456]
    assert settings.telegram_match_cooldown_seconds == 17
    assert isinstance(settings.open_dota_api_key, SecretStr)
    assert settings.open_dota_api_key.get_secret_value() == "fixture-open-dota-key"
    assert "fixture-open-dota-key" not in repr(settings)
    assert settings.open_dota_timeout_seconds == 12


@pytest.mark.parametrize("values", [[1], [0], [-100, -100], [-(2**63) - 1]])
def test_allowed_chat_ids_reject_unsafe_values(values: list[int]) -> None:
    with pytest.raises(ValidationError):
        AuthTestSettings(telegram_allowed_chat_ids=values)


@pytest.mark.parametrize("username", ["bad", "bad-name", "x" * 33, "юзербот"])
def test_bot_username_is_validated(username: str) -> None:
    with pytest.raises(ValidationError):
        AuthTestSettings(bot_username=username)
    assert AuthTestSettings(bot_username="@FixtureBot").bot_username == "FixtureBot"


async def test_bot_refuses_to_start_without_token() -> None:
    settings = AuthTestSettings(bot_token=None)
    with patch("app.bot.main.Settings", return_value=settings):
        with pytest.raises(RuntimeError, match="BOT_TOKEN is required"):
            await run_polling()
