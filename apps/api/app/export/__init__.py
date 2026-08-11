"""Export feature module:純 deterministic Current State → 公版表格投影(ADR 0058)。

只放不讀 DB、不碰 transport、不知道任何具體 render 格式的組裝邏輯;XLSX 等
render-time adapter 屬於 `app.adapters`,不屬於這個 feature module。
"""

from .assembly import (
    ExportDocument,
    ExportDutySection,
    ExportOpksEntry,
    ExportTaskEntry,
    assemble_export_document,
)

__all__ = [
    "ExportDocument",
    "ExportDutySection",
    "ExportOpksEntry",
    "ExportTaskEntry",
    "assemble_export_document",
]
