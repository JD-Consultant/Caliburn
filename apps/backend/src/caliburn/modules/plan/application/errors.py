"""Plan 的不存在、版本拒絕與保存證據；不包含正文。"""

from typing import Literal

type CommitStatus = Literal["not_committed", "committed", "unknown"]
type ConcurrencyReason = Literal["version", "serialization", "deadlock", "lock_timeout"]


class WorkspaceNotFoundError(Exception):
    """指定 Workspace 不存在，不可自動重建。"""


class PlanNotInitializedError(Exception):
    """Workspace 尚無 Plan，呼叫者須先明示初始化。"""


class PlanVersionNotFoundError(Exception):
    """指定 Workspace 沒有此已保存版本。"""


class PlanConcurrencyError(Exception):
    """目前版本不符，或資料庫明確拒絕競爭交易；未自動重試。"""

    def __init__(self, *, reason: ConcurrencyReason = "version") -> None:
        super().__init__("Plan 並行修改遭拒絕")
        self.reason = reason


class PlanPersistenceError(Exception):
    """保存或清理失敗；commit_status 只表達已觀察的提交證據。"""

    def __init__(self, *, commit_status: CommitStatus) -> None:
        super().__init__("Plan 保存或交易清理失敗")
        self.commit_status = commit_status


class PlanQueryError(Exception):
    """查詢或釋放讀取資源失敗，不等於無內容。"""


class PlanDataError(Exception):
    """目前內容或快照損壞，不能投影為正常 Plan。"""
