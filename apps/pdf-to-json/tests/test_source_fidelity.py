"""Source-checked regressions: content that existing JSON loses or changes."""

from pathlib import Path

import pytest

from jd_pdf_to_json.core.models import OCSDocument
from jd_pdf_to_json.parsers import PDFPlumberParser
from jd_pdf_to_json.transformers import OCSTransformer
from jd_pdf_to_json.transformers.support.items import extract_output_items, extract_task_level
from jd_pdf_to_json.transformers.support.text import compact_wrapped_text
from jd_pdf_to_json.utils.exceptions import TransformationError
from jd_pdf_to_json.validators import OCSSchemaValidator

CORPUS = Path(__file__).resolve().parents[1] / "data" / "pdfs"


def convert_source(name: str) -> OCSDocument:
    path = CORPUS / f"{name}-職能基準.pdf"
    raw = PDFPlumberParser().parse(path)
    return OCSTransformer().transform(raw)


def test_notes_keep_3d_as_body_text() -> None:
    doc = convert_source("3D列印設備配修人員")
    assert len(doc.notes.supplements) == 1
    assert doc.notes.supplements[0].startswith("3D列印技術：如FDM")
    assert doc.notes.supplements[0].endswith("Polyjet（彩色噴墨）等。")


def test_wrapped_jewelry_notes_remain_four_items() -> None:
    doc = convert_source("3D珠寶設計人員")
    assert len(doc.notes.supplements) == 4
    assert doc.notes.supplements[1].endswith("珠寶設計標準作業流程。")
    assert doc.notes.supplements[3].endswith("製作與材料相關知識、珠寶製作標準作業流程。")


def test_source_level_six_is_preserved() -> None:
    doc = convert_source("機械設計工程師")
    task = next(
        task
        for unit in doc.ocs_content.ocu_units
        for task in unit.tasks
        if task.task_codes[0].code == "T3.2"
    )
    assert task.competency_blocks[0].competency_level == 6


def test_uncoded_attitude_and_unlabelled_supplement_are_preserved() -> None:
    doc = convert_source("機械設計工程師")
    assert [(item.code, item.name) for item in doc.ocs_attitude.attitudes] == [
        (None, "配合產業特質與需求，積極培育技專院校學生之專業技術與能力，以達適才適所之教育目的。")
    ]
    assert doc.notes.prerequisites == []
    assert doc.notes.supplements == [
        "優化內容包括 DFX(指設計時考慮製造、組裝、品管、測試、成本等等因素)。"
    ]
    assert OCSSchemaValidator().validate(doc) == (True, [])


def test_wrapped_inline_attitude_keeps_full_name() -> None:
    doc = convert_source("AIoT應用工程師")
    attitudes = {item.code: item.name for item in doc.ocs_attitude.attitudes}
    assert attitudes["A10"] == "目標導向"
    assert attitudes["A11"] == "職場倫理"


@pytest.mark.parametrize(
    "row,mapping", [([None], {"level": 0}), ([""], {"level": 0}), (["K01"], {})]
)
def test_absent_level_stays_null(row, mapping) -> None:
    assert extract_task_level(row, mapping) is None


@pytest.mark.parametrize("level", ["7", "未知", "3/4"])
def test_invalid_explicit_level_is_rejected(level: str) -> None:
    with pytest.raises(TransformationError):
        extract_task_level([level], {"level": 0})


def test_empty_content_is_rejected() -> None:
    doc = OCSDocument(ocs_profile={"ocs_code": "TEST1234"})
    valid, errors = OCSSchemaValidator().validate(doc)
    assert not valid
    assert any("content" in error.lower() for error in errors)


def test_transformation_uses_extracted_data_after_source_is_removed(tmp_path: Path) -> None:
    source = tmp_path / "source.pdf"
    source.write_bytes((CORPUS / "3D列印設備配修人員-職能基準.pdf").read_bytes())
    raw = PDFPlumberParser().parse(source)
    source.unlink()
    doc = OCSTransformer().transform(raw)
    assert doc.ocs_profile.ocs_code == "MEM3400-001v1"
    assert doc.notes.supplements[0].startswith("3D列印技術")


def test_source_check_rejects_knowledge_attached_to_wrong_task() -> None:
    source = PDFPlumberParser().parse(CORPUS / "電控系統工程師-職能基準.pdf")
    doc = OCSTransformer().transform(source)
    assert OCSSchemaValidator().validate_source(source, doc) == (True, [])
    tasks = {
        entry.code: task
        for unit in doc.ocs_content.ocu_units
        for task in unit.tasks
        for entry in task.task_codes
    }
    origin = tasks["T1.2"].competency_blocks[0]
    item = next(item for item in origin.knowledge if item.code == "K17")
    origin.knowledge.remove(item)
    tasks["T2.1"].competency_blocks[0].knowledge.append(item)
    valid, errors = OCSSchemaValidator().validate_source(source, doc)
    assert not valid
    assert any("T1.2" in error and "knowledge" in error for error in errors)


def test_source_check_rejects_truncated_indicator_text() -> None:
    source = PDFPlumberParser().parse(CORPUS / "3D列印設備配修人員-職能基準.pdf")
    doc = OCSTransformer().transform(source)
    assert OCSSchemaValidator().validate_source(source, doc) == (True, [])
    doc.ocs_content.ocu_units[0].tasks[0].competency_blocks[0].indicators[0].text = "刪去正文"
    valid, errors = OCSSchemaValidator().validate_source(source, doc)
    assert not valid
    assert any("behavioral" in error for error in errors)


def test_continuation_keeps_prefix_before_new_output_and_skill_codes() -> None:
    doc = convert_source("電控系統工程師")
    task = next(
        task
        for unit in doc.ocs_content.ocu_units
        for task in unit.tasks
        if task.task_codes[0].code == "T2.2"
    )
    assert task.competency_blocks[0].outputs[0].name == "電腦軟體程式"
    assert task.competency_blocks[0].skills[0].name == "機電整合之電路配線設計能力"


def test_latin_word_spaces_survive_cell_wrapping() -> None:
    assert compact_wrapped_text("PC Base\n程式語言") == "PC Base程式語言"
    assert compact_wrapped_text("machine\nlearning") == "machine learning"


def test_numeric_source_output_code_is_preserved_without_changing_zero_to_o() -> None:
    items = extract_output_items("04.2.1產\n品")
    assert [(item.code, item.name) for item in items] == [("04.2.1", "產品")]


def test_related_categories_are_supplements_not_prerequisites() -> None:
    doc = convert_source("3D列印積層製造工程師")
    assert doc.notes.prerequisites == ["具備電腦實體建模基本能力，且對積層製造有基本認識者。"]
    assert doc.notes.supplements[0] == "相關所屬類別："
    assert any("研究發展經理人員（1223）" in line for line in doc.notes.supplements)


@pytest.mark.parametrize("field", ["task_name", "level", "profile", "version"])
def test_source_check_rejects_missing_known_field(field: str) -> None:
    name = "3D珠寶設計人員" if field == "version" else "3D列印設備配修人員"
    source = PDFPlumberParser().parse(CORPUS / f"{name}-職能基準.pdf")
    doc = OCSTransformer().transform(source)
    if field == "task_name":
        doc.ocs_content.ocu_units[0].tasks[0].task_codes[0].name = ""
    elif field == "level":
        doc.ocs_content.ocu_units[0].tasks[0].competency_blocks[0].competency_level = None
    elif field == "profile":
        doc.ocs_profile.job_description = ""
    else:
        doc.version_info.versions.clear()
    valid, errors = OCSSchemaValidator().validate_source(source, doc)
    assert not valid, errors


def test_source_check_requires_every_code_in_a_shared_task_cell() -> None:
    source = PDFPlumberParser().parse(CORPUS / "工具機軟體人機介面工程師-職能基準.pdf")
    doc = OCSTransformer().transform(source)
    for unit in doc.ocs_content.ocu_units:
        for task in unit.tasks:
            task.task_codes = [entry for entry in task.task_codes if entry.code != "T1.5"]
    valid, errors = OCSSchemaValidator().validate_source(source, doc)
    assert not valid, errors


@pytest.mark.parametrize("name,code", [("AIoT應用工程師", "T2.1"), ("電控系統工程師", "T2.2")])
def test_source_check_rejects_knowledge_swapped_between_blocks(name, code) -> None:
    source = PDFPlumberParser().parse(CORPUS / f"{name}-職能基準.pdf")
    doc = OCSTransformer().transform(source)
    assert OCSSchemaValidator().validate_source(source, doc) == (True, [])
    task = next(
        task
        for unit in doc.ocs_content.ocu_units
        for task in unit.tasks
        if task.task_codes[0].code == code
    )
    first, second = task.competency_blocks[:2]
    first.knowledge, second.knowledge = second.knowledge, first.knowledge
    valid, errors = OCSSchemaValidator().validate_source(source, doc)
    assert not valid, errors


def test_shared_task_codes_cannot_be_split_into_an_unrelated_group() -> None:
    source = PDFPlumberParser().parse(CORPUS / "工具機軟體人機介面工程師-職能基準.pdf")
    doc = OCSTransformer().transform(source)
    task = doc.ocs_content.ocu_units[0].tasks[0]
    entry = next(entry for entry in task.task_codes if entry.code == "T1.5")
    task.task_codes.remove(entry)
    wrong = task.model_copy(deep=True)
    wrong.task_codes = [entry]
    wrong.competency_blocks = []
    doc.ocs_content.ocu_units[0].tasks.append(wrong)
    valid, errors = OCSSchemaValidator().validate_source(source, doc)
    assert not valid, errors


@pytest.mark.parametrize("name", ["博物館技術人員", "都更危老整合人", "行動遊戲程式設計師"])
def test_known_header_variants_keep_content(name) -> None:
    source = PDFPlumberParser().parse(CORPUS / f"{name}-職能基準.pdf")
    doc = OCSTransformer().transform(source)
    assert doc.ocs_content.ocu_units
    assert OCSSchemaValidator().validate_source(source, doc) == (True, [])


def test_last_task_sharing_a_table_with_attitudes_is_preserved() -> None:
    source = PDFPlumberParser().parse(CORPUS / "農務人員-職能基準.pdf")
    doc = OCSTransformer().transform(source)
    task = next(
        task
        for unit in doc.ocs_content.ocu_units
        for task in unit.tasks
        if any(entry.code == "T4.2" for entry in task.task_codes)
    )
    block = task.competency_blocks[0]
    assert block.competency_level == 2
    assert block.indicators[0].code == "P4.2.1"
    assert block.outputs[0].name == "工作日誌"
    assert {item.code for item in doc.ocs_attitude.attitudes} == {
        "A01",
        "A02",
        "A03",
        "A04",
        "A05",
        "A06",
        "A07",
        "A08",
    }
    assert OCSSchemaValidator().validate_source(source, doc) == (True, [])
    for unit in doc.ocs_content.ocu_units:
        unit.tasks = [
            task
            for task in unit.tasks
            if not any(entry.code == "T4.2" for entry in task.task_codes)
        ]
    valid, errors = OCSSchemaValidator().validate_source(source, doc)
    assert not valid
    assert any("page 4" in error and "T4.2" in error for error in errors)


@pytest.mark.parametrize(
    "name,code,body",
    [
        ("RF研發工程師", "P5.1.2", "依據國際認證組織的測試法規"),
        ("資料庫分析設計人員", "P2.3.3", "評估雲端儲存的效果"),
    ],
)
def test_spaced_indicator_prefix_is_a_code_not_previous_indicator_body(name, code, body) -> None:
    source = PDFPlumberParser().parse(CORPUS / f"{name}-職能基準.pdf")
    doc = OCSTransformer().transform(source)
    item = next(
        item
        for unit in doc.ocs_content.ocu_units
        for task in unit.tasks
        for block in task.competency_blocks
        for item in block.indicators
        if item.code == code
    )
    assert item.text.startswith(body)
    assert OCSSchemaValidator().validate_source(source, doc) == (True, [])
