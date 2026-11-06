"""Retain readable PDF text when fine table mapping is unavailable."""

import re
from pathlib import Path

from pydantic import JsonValue

from ...domain.cleaning import clean_text
from .parsers import PDFPlumberParser
from .parsers.models import PDFDocument

_PAGE_FOOTER = re.compile(r"第\s*\d+\s*頁[，,\s]*(?:總)?共\s*\d+\s*頁")
_VERSION_ROW = re.compile(r"^V\d+\s+[A-Z]{2,}\d+-\d+", re.IGNORECASE)


def clean_pdf_text(source: PDFDocument) -> dict[str, JsonValue]:
    """Keep extracted page/line order and note markers, without guessing blocks.

    Horizontal table cells may already share a line in the PDF extraction. This
    fallback does not certify cell associations or a complete structured source.
    The filename supplies the display name; source identity stays in the report.
    """
    pages: list[JsonValue] = []
    has_body = False
    for page in source.pages:
        lines: list[JsonValue] = []
        for raw_line in page.text.splitlines():
            line = clean_text(raw_line)
            if not line or _PAGE_FOOTER.fullmatch(line) or _VERSION_ROW.match(line):
                continue
            lines.append(line)
        pages.append({"page": page.page_number, "lines": lines})
        has_body = has_body or bool(lines)
    if not has_body:
        raise ValueError("PDF has no readable body text")
    return {
        "occupation_name": source.source_path.stem.removesuffix("-職能基準"),
        "pages": pages,
    }


def extract_text_fallback(source_path: Path) -> dict[str, JsonValue]:
    return clean_pdf_text(PDFPlumberParser().parse(source_path))
