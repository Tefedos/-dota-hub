from typing import Literal

from pydantic import BaseModel, ConfigDict


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    status: Literal["ok"] = "ok"
    service: Literal["dota-hub-api"] = "dota-hub-api"


class DatabaseHealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    database: Literal["available"] = "available"
