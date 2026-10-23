import re
import secrets
import time

import jwt

from app.core.config import Settings
from app.core.errors import PublicError

ISSUER = "dota-hub-api"
AUDIENCE = "dota-hub-miniapp"


def auth_secrets(settings: Settings) -> tuple[str, str]:
    bot = settings.bot_token.get_secret_value() if settings.bot_token else ""
    session = settings.session_secret.get_secret_value() if settings.session_secret else ""
    if not bot or len(session.encode("utf-8")) < 32 or secrets.compare_digest(bot.encode(), session.encode()):
        raise PublicError(503, "AUTH_UNAVAILABLE", "Вход через Telegram пока недоступен")
    return bot, session


def create_session(user_id: int, key: str, ttl: int) -> str:
    now = int(time.time())
    return jwt.encode({
        "sub": str(user_id), "iss": ISSUER, "aud": AUDIENCE,
        "iat": now, "nbf": now, "exp": now + ttl, "jti": secrets.token_urlsafe(24),
    }, key, algorithm="HS256")


def read_session(token: str, key: str) -> int:
    try:
        if not token or len(token) > 4096:
            raise jwt.InvalidTokenError()
        claims = jwt.decode(
            token, key, algorithms=["HS256"], issuer=ISSUER, audience=AUDIENCE,
            options={"require": ["sub", "iss", "aud", "iat", "nbf", "exp", "jti"], "strict_aud": True},
        )
        subject = claims["sub"]
        if not isinstance(subject, str) or not re.fullmatch(r"[1-9][0-9]{0,18}", subject) or int(subject) > 2**63 - 1:
            raise jwt.InvalidTokenError()
        if any(type(claims[name]) is not int for name in ("iat", "nbf", "exp")):
            raise jwt.InvalidTokenError()
        if not 0 < claims["exp"] - claims["iat"] <= 3600 or claims["nbf"] != claims["iat"]:
            raise jwt.InvalidTokenError()
        return int(subject)
    except jwt.ExpiredSignatureError:
        raise PublicError(401, "SESSION_EXPIRED", "Сессия истекла. Откройте приложение через Telegram заново") from None
    except (jwt.InvalidTokenError, ValueError, TypeError, OverflowError, RecursionError):
        raise PublicError(401, "INVALID_SESSION", "Сессия недействительна") from None
