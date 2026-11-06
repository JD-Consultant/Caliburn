"""純文字編修拒絕；訊息與定位資料不攜帶正文。"""

from dataclasses import dataclass
from typing import Literal

type TextEditErrorCode = Literal[
    "invalid_patch",
    "patch_context_not_found",
    "ambiguous_patch_context",
    "patch_limit_exceeded",
]


@dataclass(frozen=True, slots=True)
class TextMatch:
    start_line: int
    end_line: int


class TextEditError(ValueError):
    """Patch 拒絕與有界候選位置；不洩漏來源或輸入文字。"""

    def __init__(
        self,
        code: TextEditErrorCode,
        message: str,
        *,
        hunk_number: int | None = None,
        candidates: tuple[TextMatch, ...] = (),
    ) -> None:
        super().__init__(message)
        self.code = code
        self.hunk_number = hunk_number
        self.candidates = candidates


class InvalidTextError(ValueError):
    """文字含 PostgreSQL UTF-8 無法保存的字元。"""
