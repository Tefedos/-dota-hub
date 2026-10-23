import hashlib
import hmac
import json
import re
from urllib.parse import parse_qsl

from pydantic import BaseModel, ConfigDict, Field

from app.db.repositories import VerifiedTelegramUser


class InvalidInitData(ValueError):
    def __init__(self) -> None:
        super().__init__("Invalid Telegram authentication data")


class TelegramUserData(BaseModel):
    model_config = ConfigDict(strict=True, extra="ignore", hide_input_in_errors=True)
    id: int = Field(gt=0, le=2**63 - 1)
    first_name: str = Field(min_length=1, max_length=256)
    last_name: str = Field(default="", max_length=256)
    username: str | None = Field(default=None, max_length=64)


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise InvalidInitData()
        result[key] = value
    return result


def _invalid_constant(value: str) -> object:
    raise InvalidInitData()


def validate_init_data(
    raw: str, bot_token: str, *, now: int, max_age: int = 86400, clock_skew: int = 30,
) -> VerifiedTelegramUser:
    """Validate the original query string; never deserialize an identity before HMAC.

    Telegram's bot-token HMAC excludes only hash. signature and unknown fields
    remain signed; the third-party Ed25519 algorithm has different exclusions.
    """
    try:
        if not raw or len(raw) > 16384 or re.search(r"%(?![0-9a-fA-F]{2})", raw):
            raise InvalidInitData()
        pairs = parse_qsl(raw, keep_blank_values=True, strict_parsing=True, errors="strict", max_num_fields=32)
        fields: dict[str, str] = {}
        for key, value in pairs:
            if not key or key in fields or any(c in key for c in "\r\n=\x00") or any(c in value for c in "\r\n\x00"):
                raise InvalidInitData()
            fields[key] = value
        received_hash = fields.pop("hash", "")
        if not re.fullmatch(r"[0-9a-f]{64}", received_hash) or not {"auth_date", "user"} <= fields.keys():
            raise InvalidInitData()
        check_string = "\n".join(f"{key}={value}" for key, value in sorted(fields.items()))
        secret = hmac.digest(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256)
        expected = hmac.new(secret, check_string.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, received_hash):
            raise InvalidInitData()
        if not re.fullmatch(r"[0-9]{1,12}", fields["auth_date"]):
            raise InvalidInitData()
        issued_at = int(fields["auth_date"])
        if issued_at <= 0 or issued_at < now - max_age or issued_at > now + clock_skew:
            raise InvalidInitData()
        data = json.loads(fields["user"], object_pairs_hook=_unique_object, parse_constant=_invalid_constant)
        user = TelegramUserData.model_validate(data)
        display_name = " ".join(part for part in (user.first_name, user.last_name) if part)
        if len(display_name) > 256 or any(c in display_name + (user.username or "") for c in "\x00\r\n"):
            raise InvalidInitData()
        # Reject lone Unicode surrogates before they can reach PostgreSQL or JSON responses.
        display_name.encode("utf-8")
        if user.username is not None:
            user.username.encode("utf-8")
        return VerifiedTelegramUser(user.id, user.username, display_name)
    except (ValueError, TypeError, RecursionError):
        raise InvalidInitData() from None
