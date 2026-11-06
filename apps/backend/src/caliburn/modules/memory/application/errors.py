"""Memory 用例及交易錯誤，訊息不含正文。"""

from typing import Literal

type CommitStatus = Literal["not_committed", "committed", "unknown"]
type ConcurrencyReason = Literal["version", "serialization", "deadlock", "lock_timeout"]


class WorkspaceNotFoundError(Exception):
    """指定 Workspace 不存在。"""


class MemoryVersionNotFoundError(Exception):
    """指定 Workspace 沒有此發布版。"""


class MemoryFailureBlockedError(Exception):
    """最終失敗後，正式訪談尚未新增足夠的原話。"""


class MemoryConcurrencyError(Exception):
    def __init__(self, *, reason: ConcurrencyReason = "version") -> None:
        super().__init__("Memory 並行修改遭拒絕")
        self.reason = reason


class MemoryPersistenceError(Exception):
    def __init__(self, *, commit_status: CommitStatus) -> None:
        super().__init__("Memory 保存或交易清理失敗")
        self.commit_status = commit_status


class MemoryQueryError(Exception):
    """查詢或資源釋放失敗。"""


class MemoryDataError(Exception):
    """目前內容或快照損壞。"""
