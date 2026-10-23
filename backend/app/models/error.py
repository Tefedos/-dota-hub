from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    field: str
    message: str


class ApiError(BaseModel):
    code: str
    message: str
    details: list[ErrorDetail] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    error: ApiError
