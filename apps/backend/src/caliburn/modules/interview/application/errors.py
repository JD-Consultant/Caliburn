"""訪談應用與持久層的具名失敗。"""

from typing import Literal


class WorkspaceNotFoundError(LookupError):
    """指定 Workspace 不存在，不可自動重建。"""


class InterviewTurnNotFoundError(LookupError):
    """指定 Workspace 內沒有此輪訪談。"""


class InterviewMessageNotFoundError(LookupError):
    """指定 Workspace 內沒有此有效訊息。"""


class InterviewDataError(RuntimeError):
    """保存資料不符合訪談契約。"""


class InterviewQueryError(RuntimeError):
    """訪談查詢失敗，不能解讀成沒有資料。"""


class InterviewPersistenceError(RuntimeError):
    def __init__(
        self,
        message: str = "Interview persistence failed",
        *,
        commit_status: Literal["not_committed", "committed", "unknown"] = "unknown",
    ) -> None:
        super().__init__(message)
        self.commit_status = commit_status


class InterviewConcurrencyError(RuntimeError):
    def __init__(
        self, *, reason: Literal["serialization", "deadlock", "lock_timeout"]
    ) -> None:
        super().__init__("Interview concurrent operation failed")
        self.reason = reason
