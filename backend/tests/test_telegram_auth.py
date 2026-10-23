import json
import time
from urllib.parse import parse_qsl, urlencode

import pytest

from app.services.telegram_auth import InvalidInitData, validate_init_data
from auth_fixtures import USER_ID, auth_settings, fields, signed


def test_hmac_optional_signature_unknown_fields_unicode_and_plus() -> None:
    settings = auth_settings()
    assert settings.bot_token
    key = settings.bot_token.get_secret_value()
    raw = signed(fields(
        user=json.dumps({"id": USER_ID, "first_name": "Тест +", "last_name": "Fixture", "username": "fixture"}, ensure_ascii=False),
        signature="future-signature", unknown_field="a+b / future=value", query_id="fixture-query",
    ), key)
    user = validate_init_data(raw, key, now=int(time.time()))
    assert user.telegram_user_id == USER_ID
    assert user.display_name == "Тест + Fixture" and user.username == "fixture"
    for field in ("signature", "unknown_field", "user", "auth_date"):
        data = dict(parse_qsl(raw))
        data[field] += "tampered"
        with pytest.raises(InvalidInitData):
            validate_init_data(urlencode(data), key, now=int(time.time()))


@pytest.mark.parametrize("case", [
    "empty", "wrong-key", "wrong-hash", "empty-hash", "short-hash", "upper-hash", "id-tamper", "time-tamper",
    "missing-user", "missing-date", "missing-hash", "old", "future", "bad-date", "zero-date",
    "bad-percent", "bad-utf8", "bad-surrogate", "duplicate-user", "duplicate-auth_date", "duplicate-hash", "duplicate-extra",
    "bad-json", "duplicate-json", "json-nan", "json-list", "negative-id", "zero-id", "float-id", "bool-id", "string-id",
    "huge-id", "missing-id", "missing-name", "null-name", "long-name", "long-username", "nul-name",
    "newline-field", "empty-key", "no-equals", "too-many-fields", "too-long",
])
def test_rejects_invalid_data(case: str) -> None:
    settings = auth_settings()
    assert settings.bot_token
    key = settings.bot_token.get_secret_value()
    now = int(time.time())
    data = fields()
    if case.startswith("missing-") and case.removeprefix("missing-") in {"user", "date"}:
        data.pop({"missing-user": "user", "missing-date": "auth_date"}[case])
    if case in {"old", "future", "bad-date", "zero-date"}:
        data["auth_date"] = {"old": str(now - 86401), "future": str(now + 31), "bad-date": "1e9", "zero-date": "0"}[case]
    bad_json = {"bad-json": "{", "duplicate-json": '{"id":1,"id":2,"first_name":"Fixture"}', "json-nan": '{"id":NaN}', "json-list": "[]"}
    if case in bad_json:
        data["user"] = bad_json[case]
    invalid_ids: dict[str, object] = {"negative-id": -1, "zero-id": 0, "float-id": 1.5, "bool-id": True, "string-id": "1", "huge-id": 2**63}
    if case in invalid_ids:
        data["user"] = json.dumps({"id": invalid_ids[case], "first_name": "Fixture"})
    if case in {"missing-id", "missing-name", "null-name", "long-name", "long-username", "nul-name", "bad-surrogate"}:
        user: dict[str, object] = {"id": USER_ID, "first_name": "Fixture"}
        if case == "missing-id": user.pop("id")
        if case == "missing-name": user.pop("first_name")
        if case == "null-name": user["first_name"] = None
        if case == "long-name": user["first_name"] = "x" * 257
        if case == "long-username": user["username"] = "x" * 65
        if case == "nul-name": user["first_name"] = "x\x00y"
        if case == "bad-surrogate": user["first_name"] = "\ud800"
        data["user"] = json.dumps(user)
    if case == "newline-field": data["extra"] = "x\ny=z"
    if case == "empty-key": data[""] = "value"
    if case == "too-many-fields": data.update({f"field{i}": "x" for i in range(40)})
    raw = signed(data, key)
    if case == "empty": raw = ""
    if case == "wrong-key": raw = signed(data, key + "wrong")
    if case in {"wrong-hash", "empty-hash", "short-hash", "upper-hash", "missing-hash", "id-tamper", "time-tamper"}:
        altered = dict(parse_qsl(raw))
        if case == "wrong-hash": altered["hash"] = "0" * 64
        if case == "empty-hash": altered["hash"] = ""
        if case == "short-hash": altered["hash"] = "ab"
        if case == "upper-hash": altered["hash"] = "A" * 64
        if case == "missing-hash": altered.pop("hash")
        if case == "id-tamper": altered["user"] = json.dumps({"id": USER_ID + 1, "first_name": "Fixture"})
        if case == "time-tamper": altered["auth_date"] = str(now + 1)
        raw = urlencode(altered)
    if case == "bad-percent": raw += "&extra=%Q0"
    if case == "bad-utf8": raw += "&extra=%FF"
    if case.startswith("duplicate-") and case != "duplicate-json":
        field = case.removeprefix("duplicate-")
        raw += f"&{field}=x" + ("&extra=y" if field == "extra" else "")
    if case == "no-equals": raw += "&broken"
    if case == "too-long": raw += "&extra=" + "x" * 16384
    with pytest.raises(InvalidInitData, match="^Invalid Telegram authentication data$"):
        validate_init_data(raw, key, now=now)


@pytest.mark.parametrize("offset", [-60, 5])
def test_configurable_age_boundaries(offset: int) -> None:
    now = int(time.time())
    key = "synthetic-key-for-pure-function-only"
    raw = signed(fields(auth_date=str(now + offset)), key)
    assert validate_init_data(raw, key, now=now, max_age=60, clock_skew=5).telegram_user_id == USER_ID
    with pytest.raises(InvalidInitData):
        validate_init_data(raw, key, now=now, max_age=59, clock_skew=4)
