"""JD 用例拒絕、保存技術失敗及可辨識的提交事實。"""

from typing import Literal

type CommitStatus = Literal["not_committed", "unknown", "committed"]
type ConcurrencyReason = Literal[
    "version", "serialization", "deadlock", "lock_timeout", "order"
]


class JobDescriptionWorkspaceNotFoundError(Exception):
    """建立 JD 指定的 Workspace 不存在。"""


class CitationNotFoundError(Exception):
    """指定引用不存在於目前 JD 或目標。"""


class InvalidCitationSourceError(Exception):
    """新引用來源不存在、已撤回或不屬指定 Workspace。"""


class CitationSourceDataError(Exception):
    """固定來源遺失或不完整；不可當成已撤回。"""


class JobDescriptionAlreadyExistsError(Exception):
    """Workspace 已有目前 JD，不能把建立當成成功重播。"""


class JobDescriptionNotFoundError(Exception):
    """內容操作指定的 JD 不存在。"""


class TaskNotFoundError(Exception):
    """指定 Task 不存在或不屬於指定 JD。"""


class KnowledgeNotFoundError(Exception):
    """指定 Knowledge 不存在或不屬於指定 JD。"""


class InvalidTaskReferenceError(Exception):
    """Task 的分類或引用不存在、種類錯誤，或不屬指定 JD。"""


class JobDescriptionNameConflictError(Exception):
    """同 JD 同種類已有相同 Domain 名稱比較鍵。"""


class InvalidJobDescriptionInputError(Exception):
    """輸入文字無法表示為 PostgreSQL UTF-8 Text，未靜默改寫。"""


class JobDescriptionConcurrencyError(Exception):
    """前置版本不符或資料庫確定拒絕並行寫入；整筆未提交。"""

    def __init__(self, message: str, *, reason: ConcurrencyReason = "version") -> None:
        super().__init__(message)
        self.reason = reason


class JobDescriptionRetryableTransactionError(JobDescriptionConcurrencyError):
    """資料庫明確以序列化失敗拒絕且未提交；可有限重試完整用例。"""

    def __init__(self, message: str) -> None:
        super().__init__(message, reason="serialization")


class JobDescriptionPersistenceError(Exception):
    """由持久適配器轉譯並鏈結原因；失敗不等於確定未保存。"""

    def __init__(self, *, commit_status: CommitStatus) -> None:
        super().__init__("JD 保存或交易清理失敗")
        self.commit_status = commit_status


class JobDescriptionQueryError(Exception):
    """JD 查詢或讀取資源釋放失敗，不等於資料不存在。"""


class SkillNotFoundError(Exception):
    """指定 Skill 不存在或不屬於指定 JD。"""


class DutyNotFoundError(Exception):
    """指定 Duty 不存在或不屬於指定 JD。"""


class JobDescriptionHistoryNotFoundError(Exception):
    """歷史版本不存在、不是有效保存，或不屬指定 JD。"""


class InvalidHistoryPaginationError(Exception):
    """歷史分頁大小或續頁條件不合法。"""


class JobDescriptionHistoryDataError(Exception):
    """歷史資料無法重建完整有效 JD；不得省略缺件或冒充空內容。"""
