"""公開錯誤 envelope，供 OpenAPI 與消費端共用格式。"""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class ValidationIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    loc: list[str | Annotated[int, Field(ge=0, le=9007199254740991)]]
    code: str


class ErrorDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    errors: list[ValidationIssue] | None = None


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    detail: ErrorDetail
