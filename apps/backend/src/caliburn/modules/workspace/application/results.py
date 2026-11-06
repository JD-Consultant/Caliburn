"""Workspace 用例的不可變結果資料，與領域及 HTTP 模型分開。"""

from typing import Self
from uuid import UUID

from caliburn.modules.workspace.domain.workspace import Workspace
from caliburn.shared.application.base_dto import BaseDTO


class WorkspaceResult(BaseDTO):
    workspace_id: UUID
    interviewee_name: str

    @classmethod
    def from_workspace(cls, workspace: Workspace) -> Self:
        """將聚合映射為結果，保留呼叫端的具體型別。"""
        return cls(
            workspace_id=workspace.id,
            interviewee_name=workspace.interviewee_name.value,
        )


class CreateWorkspaceResult(WorkspaceResult):
    """建立 Workspace 的結果。"""


class WorkspacePage(BaseDTO):
    items: tuple[WorkspaceResult, ...]
    next_cursor: UUID | None
