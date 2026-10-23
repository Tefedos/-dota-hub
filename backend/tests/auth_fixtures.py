"""Synthetic data generated in memory; no credentials or full initData fixtures on disk."""
import hashlib
import hmac
import json
import secrets
import time
from urllib.parse import urlencode

from pydantic import SecretStr
from pydantic_settings import SettingsConfigDict

from app.core.config import Settings

USER_ID = 9007199254740993


class AuthTestSettings(Settings):
    __test__ = False
    model_config = SettingsConfigDict(env_file=None)


def auth_settings() -> Settings:
    return AuthTestSettings(
        database_url=None,
        bot_token=SecretStr(secrets.token_urlsafe(40)), session_secret=SecretStr(secrets.token_urlsafe(48)),
    )


def fields(**changes: str) -> dict[str, str]:
    return {"auth_date": str(int(time.time())), "user": json.dumps({"id": USER_ID, "first_name": "Fixture"}), **changes}


def signed(data: dict[str, str], key: str) -> str:
    # Independent reference implementation, deliberately not using the validator.
    check = "\n".join(key + "=" + data[key] for key in sorted(data) if key != "hash")
    secret = hmac.new(b"WebAppData", key.encode(), hashlib.sha256).digest()
    digest = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode({**data, "hash": digest})
