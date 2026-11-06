"""Readable PDF text remains usable without inferring table relationships."""

from pathlib import Path

import pytest

from caliburn.modules.occupation_reference.infrastructure.pdf.parsers.models import (
    PDFDocument,
    PDFPage,
)
from caliburn.modules.occupation_reference.infrastructure.pdf.text_fallback import (
    clean_pdf_text,
    extract_text_fallback,
)


def test_text_fallback_keeps_order_unknown_levels_and_note_references() -> None:
    source = PDFDocument(
        Path("機器人工程師-職能基準.pdf"),
        "source-hash",
        [
            PDFPage(
                1,
                "V1 ROB123-001v1 舊版 2020/01/01\n"
                "工作任務 職能級別 知識\n"
                "T1.1 系統感知 4級以上 原理【註1】\n"
                "A320型飛機檢修\n"
                "【註1】感知技術限制。\n第 1 頁，共 2 頁",
                [],
                [],
                600,
                800,
            ),
            PDFPage(2, "第 2 頁，總共 2 頁", [], [], 600, 800),
        ],
    )

    assert clean_pdf_text(source) == {
        "occupation_name": "機器人工程師",
        "pages": [
            {
                "page": 1,
                "lines": [
                    "工作任務 職能級別 知識",
                    "系統感知 4級以上 原理【註1】",
                    "A320型飛機檢修",
                    "【註1】感知技術限制。",
                ],
            },
            {"page": 2, "lines": []},
        ],
    }


def test_text_fallback_rejects_pdf_without_body_text() -> None:
    source = PDFDocument(
        Path("empty.pdf"),
        "source-hash",
        [PDFPage(1, "第 1 頁，共 1 頁", [], [], 600, 800)],
    )
    with pytest.raises(ValueError, match="readable body"):
        clean_pdf_text(source)


def test_text_fallback_reads_real_pdf_categories_and_keeps_all_pages() -> None:
    path = (
        Path(__file__).parent / "fixtures/sample_pdfs/3D列印積層製造工程師-職能基準.pdf"
    )
    result = extract_text_fallback(path)
    assert result["occupation_name"] == "3D列印積層製造工程師"
    assert isinstance(result["pages"], list)
    assert len(result["pages"]) == 6
    assert "其他工程專業人員、機械工程師" in str(result)
