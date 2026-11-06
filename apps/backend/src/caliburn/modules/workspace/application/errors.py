"""Workspace 用例可辨認的失敗，不包含傳輸或儲存機制。"""

from typing import Literal
from uuid import UUID

type WorkspaceConflictReason = Literal["lock_timeout", "deadlock"]


class WorkspaceConcurrencyError(Exception):
    """刪除遭並行衝突拒絕；UoW 完成回滾後才交還呼叫端。"""

    def __init__(self, *, reason: WorkspaceConflictReason) -> None:
        self.reason = reason
        super().__init__("Workspace 正在使用中，請稍後再試")


class WorkspaceNotFoundError(Exception):
    def __init__(self, workspace_id: UUID) -> None:
        self.workspace_id = workspace_id
        super().__init__("Workspace 不存在")


class InvalidWorkspacePaginationError(ValueError):
    """分頁輸入不符合用例契約。"""
