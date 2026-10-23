from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class TelegramLoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)
    init_data: str = Field(min_length=1, max_length=16384, repr=False)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    # String keeps IDs lossless for JavaScript and matches the existing BIGINT schema.
    telegram_user_id: str
    username: str | None
    display_name: str | None
    created_at: datetime
    updated_at: datetime


class TelegramLoginResponse(BaseModel):
    access_token: str = Field(repr=False)
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    user: UserResponse
