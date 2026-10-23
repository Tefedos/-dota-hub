import secrets
import time
from base64 import urlsafe_b64encode

import jwt
import pytest
from pydantic import SecretStr, ValidationError

from app.core.errors import PublicError
from app.services.sessions import AUDIENCE, ISSUER, auth_secrets, create_session, read_session
from auth_fixtures import USER_ID, AuthTestSettings, auth_settings


def test_session_round_trip_and_unique_token() -> None:
    _, key = auth_secrets(auth_settings())
    token = create_session(USER_ID, key, 900)
    assert read_session(token, key) == USER_ID
    assert token != create_session(USER_ID, key, 900)
    assert key not in token


@pytest.mark.parametrize("case", ["expired", "wrong-key", "tampered", "garbage", "empty", "long", "alg-none", "alg-hs384", "no-exp", "bad-aud", "bad-iss", "future", "bad-sub", "bad-time", "long-ttl", "deep-header"])
def test_invalid_sessions(case: str) -> None:
    _, key = auth_secrets(auth_settings())
    now = int(time.time())
    claims: dict[str, object] = {"sub": str(USER_ID), "iss": ISSUER, "aud": AUDIENCE, "iat": now, "nbf": now, "exp": now + 900, "jti": secrets.token_urlsafe(12)}
    if case == "expired": claims.update(iat=now-1000, nbf=now-1000, exp=now-100)
    if case == "no-exp": claims.pop("exp")
    if case == "bad-aud": claims["aud"] = "foreign"
    if case == "bad-iss": claims["iss"] = "foreign"
    if case == "future": claims.update(iat=now+100, nbf=now+100)
    if case == "bad-sub": claims["sub"] = "-1"
    if case == "bad-time": claims["iat"] = str(now)
    if case == "long-ttl": claims["exp"] = now+3601
    token = jwt.encode(claims, key + "wrong" if case == "wrong-key" else key, algorithm="HS384" if case == "alg-hs384" else "HS256")
    if case == "alg-none": token = jwt.encode(claims, None, algorithm="none")
    if case == "tampered": token = token[:10] + ("a" if token[10] != "a" else "b") + token[11:]
    if case == "garbage": token = "invalid"
    if case == "empty": token = ""
    if case == "long": token = "a"*4097
    if case == "deep-header": token = urlsafe_b64encode(("["*1100 + "0" + "]"*1100).encode()).decode().rstrip("=") + ".e30.AA"
    with pytest.raises(PublicError) as error:
        read_session(token, key)
    assert error.value.status_code == 401
    assert error.value.code == ("SESSION_EXPIRED" if case == "expired" else "INVALID_SESSION")


def test_auth_missing_short_or_reused_secret_fails_closed() -> None:
    for key in (None, SecretStr("short")):
        with pytest.raises(PublicError) as error:
            auth_secrets(AuthTestSettings(bot_token=None, session_secret=key))
        assert error.value.status_code == 503
    reused = SecretStr(secrets.token_urlsafe(48))
    with pytest.raises(PublicError):
        auth_secrets(AuthTestSettings(bot_token=reused, session_secret=reused))


@pytest.mark.parametrize("origin", ["*", "https://*.example.org", "http://example.org", "https://example.org/path", "https://user:password@example.org", "null"])
def test_unsafe_cors_rejected(origin: str) -> None:
    with pytest.raises(ValidationError):
        AuthTestSettings(cors_origins=[origin])
