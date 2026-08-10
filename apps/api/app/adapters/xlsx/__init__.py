"""XLSX render-time adapter:OpenPyXL 只存在這裡(ADR 0058)。"""

from .renderer import SHEET_NAME, XLSX_MEDIA_TYPE, render_xlsx

__all__ = ["SHEET_NAME", "XLSX_MEDIA_TYPE", "render_xlsx"]
