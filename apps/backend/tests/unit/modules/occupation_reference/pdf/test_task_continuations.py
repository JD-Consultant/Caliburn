"""Continuation cells preserve each task name without repeating coded text."""

from pathlib import Path

import pytest

from caliburn.modules.occupation_reference.infrastructure.pdf.parsers import (
    PDFPlumberParser,
    models,
)
from caliburn.modules.occupation_reference.infrastructure.pdf.transformers import (
    ocs_transformer,
)

PDFS = Path(__file__).parent / "fixtures" / "task_pdfs"


def test_pdf_task_names_remain_separate_across_coded_continuations() -> None:
    source = PDFPlumberParser().parse(PDFS / "工具機軟體人機介面工程師-職能基準.pdf")
    document = ocs_transformer.transform_document(source)
    assert document.ocs_content is not None and document.ocs_content.ocu_units
    names = {
        entry.code: entry.name
        for unit in document.ocs_content.ocu_units
        for task in unit.tasks or []
        for entry in task.task_codes or []
    }
    assert names["T1.3"] == "分析機台特性與功能需求"
    assert names["T1.4"] == "評估開發成本及時程"
    assert names["T1.5"] == "搜尋與檢索相關專利"
    assert names["T2.5"] == "規劃介面定義與系統整合"
    assert names["T2.6"] == "訂定軟體驗證標準表"


@pytest.mark.parametrize(
    ("continuation", "expected"),
    [
        ("T1.1整合", [("T1.1", "規劃系統整合")]),
        ("T1.1規劃系統整合", [("T1.1", "規劃系統整合")]),
        (
            "T1.1規劃系統\nT1.2驗證",
            [("T1.1", "規劃系統"), ("T1.2", "驗證")],
        ),
    ],
)
def test_repeated_task_codes_extend_names_without_repeating_source_cells(
    continuation: str, expected: list[tuple[str, str]]
) -> None:
    rows: list[list[str | None]] = [
        ["主要職責", "工作任務", "工作產出", "行為指標", "職能級別", "知識", "技能"],
        ["T1職責", "T1.1規劃系統", "O1產出", "P1.1.1指標", "3", "K01知識", "S01技能"],
        [None, continuation, None, None, None, None, None],
    ]
    cells: list[list[models.BBox | None]] = [
        [(i * 50, j * 30, (i + 1) * 50, (j + 1) * 30) for i in range(len(row))]
        for j, row in enumerate(rows)
    ]
    source = models.PDFDocument(
        Path("continuation.pdf"),
        "snapshot",
        [
            models.PDFPage(
                1,
                "",
                [models.PDFTable(rows, cells, (0, 0, 350, 90), 1, 1)],
                [],
                400,
                800,
            )
        ],
    )
    document = ocs_transformer.transform_document(source)
    assert document.ocs_content is not None and document.ocs_content.ocu_units
    tasks = document.ocs_content.ocu_units[0].tasks
    assert tasks is not None and len(tasks) == 1
    assert tasks[0].task_codes
    assert [(entry.code, entry.name) for entry in tasks[0].task_codes] == expected
    assert tasks[0].competency_blocks and len(tasks[0].competency_blocks) == 1
    block = tasks[0].competency_blocks[0]
    assert block.indicators and [
        (item.code, item.text) for item in block.indicators
    ] == [("P1.1.1", "指標")]
    assert block.knowledge and [(item.code, item.name) for item in block.knowledge] == [
        ("K01", "知識")
    ]
    assert block.skills and [(item.code, item.name) for item in block.skills] == [
        ("S01", "技能")
    ]
