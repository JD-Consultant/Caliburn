"""Detached-table counterexamples for layout and source coverage."""

from pathlib import Path

import pytest

from jd_pdf_to_json.core.models import VersionInfo
from jd_pdf_to_json.parsers.models import PDFDocument, PDFPage, PDFTable
from jd_pdf_to_json.transformers.sections.content_extractor import extract_content
from jd_pdf_to_json.transformers.sections.notes_extractor import extract_notes
from jd_pdf_to_json.transformers.sections.profile_extractor import extract_profile
from jd_pdf_to_json.transformers.support.tables import find_ocu_header_row
from jd_pdf_to_json.utils.exceptions import TransformationError


def source_table(rows, page_number=1):
    return PDFTable(
        rows,
        [
            [(i * 50, j * 30, (i + 1) * 50, (j + 1) * 30) for i in range(len(row))]
            for j, row in enumerate(rows)
        ],
        (0, 0, len(rows[0]) * 50, len(rows) * 30),
        page_number,
        1,
    )


def test_coded_body_row_cannot_complete_an_unknown_header():
    rows = [
        ["主要職責", "工作任務", "工作產出", "行為指標", "職能級別", "知識", "實作能力"],
        ["T1第一職責", "T1.1第一任務", "O1.1產出", "P1.1.1指標", "3", "K01知識", "S01技能"],
        ["T2第二職責", "T2.1第二任務", "O2.1產出", "P2.1.1指標", "3", "K02知識", "S02技能"],
    ]
    index, mapping, span = find_ocu_header_row(rows)
    assert span == 1
    assert "skills" not in mapping
    source = PDFDocument(
        Path("memory.pdf"), "test", [PDFPage(1, "", [source_table(rows)], [], 400, 800)]
    )
    with pytest.raises(TransformationError, match="Unsupported content header"):
        extract_content(source)


def test_headerless_geometry_aligned_knowledge_continues_previous_task():
    header = ["主要職責", "工作任務", "工作產出", "行為指標", "職能級別", "知識", "技能"]
    first = source_table(
        [header, ["T1職責", "T1.1任務", "O1產出", "P1.1.1指標", "3", "K01第一", "S01第一"]]
    )
    second = source_table([[None, None, None, None, None, "K99後續知識", "S99後續技能"]], 2)
    source = PDFDocument(
        Path("memory.pdf"),
        "test",
        [
            PDFPage(1, "", [first], [], 400, 800),
            PDFPage(2, "", [second], [], 400, 800),
        ],
    )
    block = extract_content(source).ocu_units[0].tasks[0].competency_blocks[0]
    assert [item.code for item in block.knowledge] == ["K01", "K99"]
    assert [item.code for item in block.skills] == ["S01", "S99"]


@pytest.mark.parametrize("body", ["-20°C 至 0°C。", "其他補充說明：同行正文必須保留。"])
def test_notes_keep_negative_number_and_inline_body(body):
    source = PDFDocument(
        Path("memory.pdf"),
        "test",
        [
            PDFPage(
                1,
                f"說明與補充事項\n{body}",
                [],
                [],
                400,
                800,
            )
        ],
    )
    expected = body.split("：", 1)[-1] if "：" in body else body
    assert extract_notes(source).supplements == [expected]


@pytest.mark.parametrize("level", ["7", "3/4", "未知"])
def test_explicit_invalid_profile_level_is_rejected(level):
    source = PDFDocument(
        Path("memory.pdf"),
        "test",
        [
            PDFPage(
                1,
                "職能基準代碼 TEST1234",
                [source_table([["基準級別", level]])],
                [],
                400,
                800,
            )
        ],
    )
    with pytest.raises(TransformationError, match="Invalid competency level"):
        extract_profile(source, VersionInfo())
