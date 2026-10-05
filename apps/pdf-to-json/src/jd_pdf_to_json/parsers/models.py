"""Detached PDF extraction data; only the parser owns PDF file I/O."""

from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict

BBox = tuple[float, float, float, float]


class PDFWord(TypedDict):
    text: str
    x0: float
    x1: float
    top: float
    bottom: float


@dataclass(frozen=True)
class PDFTable:
    rows: list[list[str | None]]
    cells: list[list[BBox | None]]
    bbox: BBox
    page_number: int
    table_number: int


@dataclass(frozen=True)
class PDFPage:
    page_number: int
    text: str
    tables: list[PDFTable]
    words: list[PDFWord]
    width: float
    height: float


@dataclass(frozen=True)
class PDFDocument:
    source_path: Path
    source_sha256: str
    pages: list[PDFPage]
