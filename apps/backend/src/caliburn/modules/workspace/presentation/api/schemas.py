"""Workspace HTTP 格式；姓名有效性由領域值物件判定。"""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

from caliburn.modules.workspace.application.errors import WorkspaceConflictReason
from caliburn.modules.workspace.domain.interviewee_name import (
    IntervieweeName,
)
from caliburn.shared.presentation.api.values import PYTHON_WHITESPACE_ESCAPES

PUBLIC_VALIDATION_FIELDS = frozenset(
    {"interviewee_name", "workspace_id", "limit", "after"}
)

_UNSTORABLE_TEXT_ESCAPES = r"\u0000\uD800-\uDFFF"
# JSON Schema 2020-12 的 ECMAScript Unicode 模式將 emoji 視為完整碼點。
# 前綴只接受空白，接著至少一個非空白，再接受任意可儲存字元。
_INTERVIEWEE_NAME_PATTERN = (
    f"^[{PYTHON_WHITESPACE_ESCAPES}]*"
    f"[^{_UNSTORABLE_TEXT_ESCAPES}{PYTHON_WHITESPACE_ESCAPES}]"
    f"[^{_UNSTORABLE_TEXT_ESCAPES}]*$"
)


def _validate_interviewee_name(value: str) -> str:
    """在輸入階段重用領域規則，保留合法原文。"""
    return IntervieweeName(value=value).value


def _validate_storable_text(value: str) -> str:
    """HTTP 輸入須能保存為 UTF-8 Text；這不是 Domain 的姓名規則。"""
    if "\x00" in value:
        raise ValueError("姓名不可包含 NUL 字元")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as error:
        raise ValueError("姓名必須能編碼為 UTF-8") from error
    return value


IntervieweeNameInput = Annotated[
    str,
    AfterValidator(_validate_storable_text),
    AfterValidator(_validate_interviewee_name),
    Field(json_schema_extra={"pattern": _INTERVIEWEE_NAME_PATTERN}),
]


class CreateWorkspaceRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    interviewee_name: IntervieweeNameInput


class RenameWorkspaceRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    interviewee_name: IntervieweeNameInput


class WorkspaceResponse(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    workspace_id: UUID
    interviewee_name: str


class WorkspacePageResponse(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    items: list[WorkspaceResponse]
    next_cursor: UUID | None


class WorkspaceConflictDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: Literal["workspace_concurrency_conflict"] = "workspace_concurrency_conflict"
    reason: WorkspaceConflictReason


class WorkspaceConflictResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    detail: WorkspaceConflictDetail
