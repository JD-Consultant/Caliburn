"""Detached PDF snapshots characterize supported layouts and coverage failures."""

from pathlib import Path

import pytest

from caliburn.modules.occupation_reference.infrastructure.pdf import errors
from caliburn.modules.occupation_reference.infrastructure.pdf.parsers import models
from caliburn.modules.occupation_reference.infrastructure.pdf.transformers import (
    ocs_transformer,
)
from caliburn.modules.occupation_reference.infrastructure.pdf.validators import (
    OCSSchemaValidator,
)

HEADER: list[str | None] = [
    "主要職責",
    "工作任務",
    "工作產出",
    "行為指標",
    "職能級別",
    "知識",
    "技能",
]


def source_table(rows: list[list[str | None]], page_number: int) -> models.PDFTable:
    return models.PDFTable(
        rows,
        [
            [(i * 50, j * 30, (i + 1) * 50, (j + 1) * 30) for i in range(len(row))]
            for j, row in enumerate(rows)
        ],
        (0, 0, len(rows[0]) * 50, len(rows) * 30),
        page_number,
        1,
    )


def source_document(
    *pages: list[list[str | None]], text: str = ""
) -> models.PDFDocument:
    return models.PDFDocument(
        Path("memory.pdf"),
        "snapshot",
        [
            models.PDFPage(number, text, [source_table(rows, number)], [], 400, 800)
            for number, rows in enumerate(pages, 1)
        ],
    )


def test_shared_task_codes_and_uncoded_output_remain_one_group() -> None:
    source = source_document(
        [
            HEADER,
            [
                "T1職責",
                "T1.1第一任務\nT1.2第二任務",
                "無碼產出",
                "P1.1.1指標",
                "6",
                "K01知識",
                "S01技能",
            ],
        ],
        text="職能內涵（A=attitude態度）\n無碼態度。\n說明與補充事項\n-20°C 至 0°C。",
    )
    document = ocs_transformer.transform_document(source)
    assert document.ocs_content is not None and document.ocs_content.ocu_units
    tasks = document.ocs_content.ocu_units[0].tasks
    assert tasks is not None and len(tasks) == 1
    assert tasks[0].task_codes is not None and tasks[0].competency_blocks
    assert [(entry.code, entry.name) for entry in tasks[0].task_codes] == [
        ("T1.1", "第一任務"),
        ("T1.2", "第二任務"),
    ]
    block = tasks[0].competency_blocks[0]
    assert block.outputs is not None
    assert [(entry.code, entry.name) for entry in block.outputs] == [(None, "無碼產出")]
    assert block.competency_level == 6
    assert document.ocs_attitude is not None and document.ocs_attitude.attitudes
    assert document.ocs_attitude.attitudes[0].code is None
    assert document.ocs_attitude.attitudes[0].name == "無碼態度。"
    assert document.notes is not None and document.notes.supplements == [
        "-20°C 至 0°C。"
    ]
    assert OCSSchemaValidator().validate_source(source, document) == (True, [])
    tasks[0].task_codes.pop()
    valid, issues = OCSSchemaValidator().validate_source(source, document)
    assert not valid and any("T1.2" in issue for issue in issues)


def test_headerless_next_page_continues_the_same_task() -> None:
    source = source_document(
        [
            HEADER,
            ["T1職責", "T1.1任務", "O1產出", "P1.1.1指標", "3", "K01第一", "S01第一"],
        ],
        [[None, None, None, None, None, "K99後續知識", "S99後續技能"]],
    )
    document = ocs_transformer.transform_document(source)
    assert document.ocs_content is not None and document.ocs_content.ocu_units
    tasks = document.ocs_content.ocu_units[0].tasks
    assert tasks and tasks[0].competency_blocks
    block = tasks[0].competency_blocks[0]
    assert block.knowledge is not None and block.skills is not None
    assert [entry.code for entry in block.knowledge] == ["K01", "K99"]
    assert [entry.code for entry in block.skills] == ["S01", "S99"]
    assert OCSSchemaValidator().validate_source(source, document) == (True, [])


@pytest.mark.parametrize(
    "previous,following,expected",
    [
        ("quality", "control", "quality control"),
        ("品質", "管理", "品質管理"),
        ("操作CNC", "machine", "操作CNC machine"),
        ("CAD", "設計", "CAD設計"),
        ("heat-", "treatment", "heat-treatment"),
        ("ISO", "9001", "ISO 9001"),
    ],
)
def test_cross_page_knowledge_and_skill_keep_wrapped_word_boundaries(
    previous: str, following: str, expected: str
) -> None:
    source = source_document(
        [
            HEADER,
            [
                "T1職責",
                "T1.1任務",
                "O1產出",
                "P1.1.1指標",
                "3",
                f"K01 {previous}",
                f"S01 {previous}",
            ],
        ],
        [[None, None, None, None, None, following, following]],
    )
    document = ocs_transformer.transform_document(source)

    assert document.ocs_content is not None and document.ocs_content.ocu_units
    tasks = document.ocs_content.ocu_units[0].tasks
    assert tasks and tasks[0].competency_blocks
    block = tasks[0].competency_blocks[0]
    assert block.knowledge and block.skills
    assert block.knowledge[0].name == expected
    assert block.skills[0].name == expected
    assert OCSSchemaValidator().validate_source(source, document) == (True, [])


def test_unknown_header_cannot_be_completed_using_codes_in_body() -> None:
    header = [*HEADER[:-1], "實作能力"]
    source = source_document(
        [
            header,
            ["T1職責", "T1.1任務", "O1產出", "P1.1.1指標", "3", "K01知識", "S01技能"],
        ]
    )
    with pytest.raises(errors.TransformationError, match="Unsupported content header"):
        ocs_transformer.transform_document(source)


@pytest.mark.parametrize("level", ["7", "3/4", "未知"])
def test_invalid_explicit_level_is_rejected(level: str) -> None:
    source = source_document(
        [
            HEADER,
            ["T1職責", "T1.1任務", "O1產出", "P1.1.1指標", level, "K01知識", "S01技能"],
        ]
    )
    with pytest.raises(errors.TransformationError, match="Invalid competency level"):
        ocs_transformer.transform_document(source)


def test_coverage_rejects_knowledge_swapped_between_blocks() -> None:
    source = source_document(
        [
            HEADER,
            [
                "T1職責",
                "T1.1任務",
                "O1產出",
                "P1.1.1第一指標",
                "3",
                "K01第一知識",
                "S01第一技能",
            ],
            [
                None,
                None,
                "O2第二產出",
                "P1.1.2第二指標",
                "4",
                "K02第二知識",
                "S02第二技能",
            ],
        ]
    )
    document = ocs_transformer.transform_document(source)
    assert OCSSchemaValidator().validate_source(source, document) == (True, [])
    assert document.ocs_content is not None and document.ocs_content.ocu_units
    tasks = document.ocs_content.ocu_units[0].tasks
    assert tasks and tasks[0].competency_blocks
    first, second = tasks[0].competency_blocks
    first.knowledge, second.knowledge = second.knowledge, first.knowledge
    valid, issues = OCSSchemaValidator().validate_source(source, document)
    assert not valid
    assert any("one competency block" in issue for issue in issues)


def test_coverage_rejects_shared_codes_split_into_separate_groups() -> None:
    source = source_document(
        [
            HEADER,
            [
                "T1職責",
                "T1.1第一任務\nT1.2第二任務",
                "O1產出",
                "P1.1.1指標",
                "3",
                "K01知識",
                "S01技能",
            ],
        ]
    )
    document = ocs_transformer.transform_document(source)
    assert OCSSchemaValidator().validate_source(source, document) == (True, [])
    assert document.ocs_content is not None and document.ocs_content.ocu_units
    tasks = document.ocs_content.ocu_units[0].tasks
    assert tasks and tasks[0].task_codes
    separate = tasks[0].model_copy(deep=True)
    separate.task_codes = [tasks[0].task_codes.pop()]
    tasks.append(separate)
    valid, issues = OCSSchemaValidator().validate_source(source, document)
    assert not valid
    assert any("unrelated task groups" in issue for issue in issues)
