from pathlib import Path
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DOTA_",
        env_file=Path(__file__).resolve().parents[2] / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
        populate_by_name=True,
    )

    docs_enabled: bool = True
    local_alpha: bool = False
    database_url: SecretStr | None = Field(default=None, validation_alias="DATABASE_URL")
    db_health_timeout_seconds: float = Field(default=3, gt=0, le=10)
    bot_token: SecretStr | None = Field(default=None, validation_alias="BOT_TOKEN")
    bot_username: str | None = Field(default=None, validation_alias="BOT_USERNAME")
    telegram_allowed_chat_ids: list[int] = Field(default_factory=list, validation_alias="TELEGRAM_ALLOWED_CHAT_IDS")
    telegram_match_cooldown_seconds: int = Field(default=10, ge=1, le=300)
    open_dota_api_key: SecretStr | None = Field(default=None, validation_alias="OPEN_DOTA_API_KEY")
    open_dota_base_url: str = "https://api.opendota.com/api"
    open_dota_timeout_seconds: float = Field(default=15, gt=0, le=60)
    open_dota_max_retries: int = Field(default=2, ge=0, le=4)
    open_dota_retry_backoff_seconds: float = Field(default=0.25, ge=0, le=5)
    open_dota_cache_ttl_seconds: int = Field(default=3600, ge=30, le=86400)
    open_dota_error_cache_ttl_seconds: int = Field(default=60, ge=1, le=600)
    open_dota_not_found_cache_ttl_seconds: int = Field(default=300, ge=1, le=3600)
    session_secret: SecretStr | None = Field(default=None, validation_alias="SESSION_SECRET")
    telegram_init_data_max_age_seconds: int = Field(default=86400, ge=1, le=86400)
    telegram_clock_skew_seconds: int = Field(default=30, ge=0, le=60)
    session_ttl_seconds: int = Field(default=900, ge=60, le=3600)
    cors_origins: list[str] = ["http://127.0.0.1:5173", "http://localhost:5173"]

    @model_validator(mode="after")
    def validate_local_alpha(self) -> "Settings":
        if self.local_alpha:
            if self.database_url is None or make_url(self.database_url.get_secret_value()).host not in {"127.0.0.1", "localhost", "::1"}:
                raise ValueError("DOTA_LOCAL_ALPHA requires a loopback PostgreSQL database")
            if any(urlsplit(origin).hostname not in {"127.0.0.1", "localhost", "::1"} for origin in self.cors_origins):
                raise ValueError("DOTA_LOCAL_ALPHA requires loopback CORS origins")
        return self

    @field_validator("bot_username")
    @classmethod
    def validate_bot_username(cls, value: str | None) -> str | None:
        if value is None:
            return value
        username = value.removeprefix("@")
        if not 5 <= len(username) <= 32 or not username.replace("_", "a").isalnum() or not username.isascii():
            raise ValueError("BOT_USERNAME must contain 5-32 ASCII letters, digits or underscores")
        return username

    @field_validator("telegram_allowed_chat_ids")
    @classmethod
    def validate_allowed_chat_ids(cls, values: list[int]) -> list[int]:
        if len(values) != len(set(values)) or any(value >= 0 or value < -(2**63) for value in values):
            raise ValueError("TELEGRAM_ALLOWED_CHAT_IDS must contain unique negative group chat IDs")
        return values

    @field_validator("cors_origins")
    @classmethod
    def validate_cors_origins(cls, values: list[str]) -> list[str]:
        for value in values:
            try:
                url = urlsplit(value)
                valid = bool(url.hostname) and url.scheme in {"http", "https"}
                valid = valid and not any((url.username, url.password, url.path, url.query, url.fragment))
                valid = valid and "*" not in value and value == f"{url.scheme}://{url.netloc}"
                valid = valid and (url.scheme == "https" or url.hostname in {"localhost", "127.0.0.1", "::1"})
                _ = url.port
            except ValueError:
                valid = False
            if not valid:
                raise ValueError("CORS requires exact HTTPS origins or local HTTP origins")
        return values

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: SecretStr | None) -> SecretStr | None:
        if value is None:
            return value
        try:
            url = make_url(value.get_secret_value())
            valid = url.drivername == "postgresql+asyncpg" and bool(url.host and url.database)
        except Exception:
            valid = False
        if not valid:
            raise ValueError("DATABASE_URL must be a PostgreSQL asyncpg URL with a host and database")
        return value
