"""Memory 領域拒絕，錯誤訊息不包含記憶正文。"""

from caliburn.shared.domain.domain_error import DomainError


class MemoryDomainError(DomainError):
    """Memory 規則拒絕的共同類別。"""


class InvalidMemoryContentError(MemoryDomainError):
    """內容不是可保存的非空白文字。"""


class DuplicateMemoryTitleError(MemoryDomainError):
    """同一層已經有相同標題。"""


class MemoryItemNotFoundError(MemoryDomainError):
    """此層找不到指定的記憶項目。"""


class InvalidMemorySourceError(MemoryDomainError):
    """來源重複、缺失或超出允許範圍。"""


class InvalidMemorySnapshotError(MemoryDomainError):
    """保存圖不完整，或不是目前根適用的發布基準。"""


class MemoryVersionExhaustedError(MemoryDomainError):
    """下一個版本超出可精確表示的範圍。"""


class MemoryAnalysisConflictError(MemoryDomainError):
    """操作與目前整理資格不相容。"""


class InvalidMemoryPhaseError(MemoryDomainError):
    """操作與目前整理階段不相容。"""
