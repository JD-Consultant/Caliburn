"""JD 所需來源資格與展開；實作借用來源 owner 的公開查讀。"""

from typing import Literal, Protocol

from caliburn.modules.job_description.domain.models.citation import SourceReference
from caliburn.shared.application.base_dto import BaseDTO


class CitationSourceView(BaseDTO):
    source: SourceReference
    availability: Literal["available", "unavailable"]
    title: str | None = None
    text: str | None = None
    changed_version: int | None = None
    item_kind: Literal["situation", "understanding"] | None = None


class CitationSourceQueries(Protocol):
    def read(self, *, source: SourceReference) -> CitationSourceView:
        """撤回回 unavailable；缺失/損毀/查詢錯誤必須拋出。"""
        ...


class CitationSources(CitationSourceQueries, Protocol):
    def require_available(self, *, source: SourceReference) -> None:
        """在 JD 寫入交易中查資格；有效訪談持鎖至提交。"""
        ...
