"""Plan 領域拒絕；訊息與定位資料不攜帶正文。"""

from dataclasses import dataclass
from typing import Literal

type BodyEditErrorCode = Literal[
    "invalid_patch",
    "patch_context_not_found",
    "ambiguous_patch_context",
    "patch_limit_exceeded",
]


@dataclass(frozen=True, slots=True)
class BodyMatch:
    start_line: int
    end_line: int


class BodyEditError(ValueError):
    """Patch 拒絕與有界候選位置；不洩漏來源或輸入文字。"""

    def __init__(
        self,
        code: BodyEditErrorCode,
        message: str,
        *,
        hunk_number: int | None = None,
        candidates: tuple[BodyMatch, ...] = (),
    ) -> None:
        super().__init__(message)
        self.code = code
        self.hunk_number = hunk_number
        self.candidates = candidates


class InvalidPlanTextError(ValueError):
    """文字含 PostgreSQL UTF-8 TEXT 無法保存的字元。"""


class PlanVersionExhaustedError(ValueError):
    """內容變更將超出可精確投影至 HTTP 的版本範圍。"""


class InvalidPlanSnapshotError(ValueError):
    """快照不屬於目前 Plan。"""
