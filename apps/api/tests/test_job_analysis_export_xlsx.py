"""XLSX renderer：讀回產出的位元組驗證內容（切片 B T2，ADR 0058 決定 9–13）。"""

from __future__ import annotations

import io

import pytest
from openpyxl import load_workbook

from app.job_analysis.application import JobAnalysisState, assess_readiness
from app.job_analysis.application.export import assemble_export_document
from app.job_analysis.application.export_xlsx import (
    ATTITUDE_HEADER,
    DISCLAIMER,
    ISSUED_BY_ICAP,
    NOTES_HEADER,
    READINESS_LABELS,
    SHEET_FORM,
    SHEET_READINESS,
    TABLE_HEADERS,
    UNASSIGNED_LABEL,
    UNLINKED_LABEL,
    render_xlsx,
)
from app.job_analysis.application.readiness import ReadinessIssueCode
from app.job_analysis.domain import (
    Duty,
    JdHeader,
    JdTask,
    OpksEntityKind,
    OpksEvidenceLink,
    OpksItem,
    SourceKind,
    SourceRef,
)


def evidence() -> OpksEvidenceLink:
    return OpksEvidenceLink(
        source_ref=SourceRef(kind=SourceKind.EMPLOYEE_TURN, id="turn-1"),
        quote="我每週彙整營運週報",
    )


def opks(entity_id, kind, order, *, task_refs=(), text="營運週報") -> OpksItem:
    return OpksItem(
        entity_id=entity_id,
        entity_kind=kind,
        text=text,
        display_order=order,
        task_refs=task_refs,
        evidence_links=(evidence(),),
    )


def rendered(state: JobAnalysisState, *, title: str = "門市營運專員"):
    document = assemble_export_document(state, title=title)
    readiness = assess_readiness(
        header=state.jd_header,
        duties=state.current_duties,
        tasks=state.current_jd,
    )
    workbook = load_workbook(io.BytesIO(render_xlsx(document, readiness)))
    return workbook


def cells(sheet) -> list[str]:
    return [
        str(cell.value)
        for row in sheet.iter_rows()
        for cell in row
        if cell.value is not None
    ]


COMPLETE = JobAnalysisState(
    jd_header=JdHeader(
        competency_name="門市營運專員",
        occupation_category_name="批發及零售業",
        occupation_name="門市服務人員",
        occupation_code="5223",
        industry_name="綜合商品零售業",
        industry_code="47",
        work_description="維運門市日常營運並彙整營運資訊。",
        competency_level=4,
        notes="本表由員工確認，尚未經主管核准。",
    ),
    current_duties=(
        Duty(duty_id="d1", statement="維運門市營運系統", display_order=0),
    ),
    current_jd=(
        JdTask(
            task_id="t1",
            statement="每週彙整營運週報",
            display_order=0,
            duty_id="d1",
            competency_level=4,
        ),
    ),
    current_opks={
        "items": (
            opks("o1", OpksEntityKind.OUTPUT, 0, task_refs=("t1",)),
            opks("p1", OpksEntityKind.INDICATOR, 0, task_refs=("t1",), text="準時交付"),
            opks("k1", OpksEntityKind.KNOWLEDGE, 0, task_refs=("t1",), text="營運指標定義"),
            opks("s1", OpksEntityKind.SKILL, 0, task_refs=("t1",), text="資料彙整"),
            opks("a1", OpksEntityKind.ATTITUDE, 0, text="主動積極"),
        )
    },
)


# ── 工作表結構 ─────────────────────────────────────────────────────────────


def test_the_workbook_has_the_form_and_the_readiness_sheets():
    workbook = rendered(COMPLETE)

    assert workbook.sheetnames == [SHEET_FORM, SHEET_READINESS]


def test_the_main_table_has_the_seven_official_columns():
    """逐字照 2026-08-06 核對的七份官方範例，K 與 S 是主表欄位不是底部清單。"""

    values = cells(rendered(COMPLETE)[SHEET_FORM])

    for title in TABLE_HEADERS:
        assert title in values
    assert len(TABLE_HEADERS) == 7


def test_the_form_carries_the_header_the_codes_and_the_body():
    values = cells(rendered(COMPLETE)[SHEET_FORM])

    assert "門市營運專員職能基準" in values
    assert "維運門市日常營運並彙整營運資訊。" in values
    assert "本表由員工確認，尚未經主管核准。" in values
    # 官方版面：位置碼與文字直接相連，**不留空格**
    assert "T1維運門市營運系統" in values
    assert "T1.1每週彙整營運週報" in values
    assert "O1.1.1營運週報" in values
    assert "P1.1.1準時交付" in values
    assert "K01營運指標定義" in values
    assert "S01資料彙整" in values
    assert "A01主動積極" in values


def test_the_header_offers_both_name_rows_and_pairs_each_category_with_its_code():
    values = cells(rendered(COMPLETE)[SHEET_FORM])

    assert "職能基準名稱\n（擇一填寫）" in values
    assert "職類" in values and "職業" in values
    for label in ("職類別", "職業別", "行業別"):
        assert label in values
        assert f"{label}代碼" in values


def test_several_outputs_share_one_cell_separated_by_line_breaks():
    """官方版面同一格內換行並列，不是一筆一列。"""

    state = JobAnalysisState(
        current_duties=(Duty(duty_id="d1", statement="維運門市系統", display_order=0),),
        current_jd=(
            JdTask(
                task_id="t1",
                statement="每週彙整營運週報",
                display_order=0,
                duty_id="d1",
            ),
        ),
        current_opks={
            "items": (
                opks("o1", OpksEntityKind.OUTPUT, 0, task_refs=("t1",), text="營運週報"),
                opks("o2", OpksEntityKind.OUTPUT, 1, task_refs=("t1",), text="異常追蹤表"),
            )
        },
    )

    assert "O1.1.1營運週報\nO1.1.2異常追蹤表" in cells(rendered(state)[SHEET_FORM])


def test_the_attitude_and_notes_blocks_use_the_official_headings():
    values = cells(rendered(COMPLETE)[SHEET_FORM])

    assert ATTITUDE_HEADER in values
    assert NOTES_HEADER in values


def test_the_two_icap_issued_codes_are_marked_not_generated():
    """ADR 0052 決定 8：由 iCAP 配發，不開輸入欄、不生成。"""

    values = cells(rendered(COMPLETE)[SHEET_FORM])

    assert "職能基準代碼" in values
    assert "職類別代碼" in values
    assert values.count(ISSUED_BY_ICAP) == 2


def test_the_official_wording_is_always_present():
    """ADR 0040 決定 33 的公版措辭固定出現。"""

    assert DISCLAIMER in cells(rendered(COMPLETE)[SHEET_FORM])


# ── 缺漏呈現 ───────────────────────────────────────────────────────────────


def test_a_missing_field_stays_a_blank_cell_with_no_placeholder_text():
    """欄位必須在，只是空的——不補值、不印「（尚未填寫）」弄髒要交出去的表。"""

    state = JobAnalysisState(jd_header=JdHeader(competency_name="門市營運專員"))
    values = cells(rendered(state)[SHEET_FORM])

    assert "工作描述" in values  # 標籤在
    assert not any("尚未填寫" in value for value in values)
    assert not any("不完整" in value for value in values)


def test_the_readiness_sheet_reports_what_assess_readiness_found():
    """落實 ADR 0052 決定 4：exporter 呼叫同一套 assessment。"""

    state = JobAnalysisState(jd_header=JdHeader(competency_name="門市營運專員"))
    readiness = assess_readiness(
        header=state.jd_header, duties=(), tasks=()
    )
    values = cells(rendered(state)[SHEET_READINESS])

    assert f"iCAP 版型欄位尚有 {readiness.issue_count} 項未填" in values
    assert readiness.issue_count > 0
    for issue in readiness.issues:
        assert READINESS_LABELS[issue.code] in values


def test_the_readiness_sheet_never_uses_forbidden_wording():
    """ADR 0052 決定 7：不得用「不完整／不合格／未通過」。"""

    state = JobAnalysisState(jd_header=JdHeader())
    values = " ".join(cells(rendered(state)[SHEET_READINESS]))

    for forbidden in ("不完整", "不合格", "未通過"):
        assert forbidden not in values


def test_the_readiness_sheet_exists_even_with_no_issues():
    workbook = rendered(COMPLETE)
    values = cells(workbook[SHEET_READINESS])

    assert SHEET_READINESS in workbook.sheetnames
    assert "iCAP 版型欄位尚有 0 項未填" in values


def test_every_readiness_code_has_a_label():
    """新增 issue code 卻忘了文案，這裡會紅——不會默默印出機器代碼。"""

    assert set(READINESS_LABELS) == set(ReadinessIssueCode)


# ── 未歸入主要職責 ─────────────────────────────────────────────────────────


def test_an_unassigned_task_gets_its_own_block_and_keeps_its_outputs():
    """排不進表格不是讓它消失的理由（ADR 0058 決定 3）。"""

    state = JobAnalysisState(
        current_jd=(
            JdTask(task_id="t9", statement="盤點耗材", display_order=0),
        ),
        current_opks={
            "items": (
                opks("o9", OpksEntityKind.OUTPUT, 0, task_refs=("t9",), text="耗材清單"),
            )
        },
    )
    values = cells(rendered(state)[SHEET_FORM])

    assert UNASSIGNED_LABEL in values
    assert "盤點耗材" in values
    # 沒有位置碼,但內容照樣出現在成品上
    assert "耗材清單" in values


def test_a_competency_linked_to_no_task_still_reaches_the_sheet():
    """主表放不下它，但不得從成品上消失。"""

    state = JobAnalysisState(
        current_opks={
            "items": (
                opks("k9", OpksEntityKind.KNOWLEDGE, 0, text="孤兒知識"),
            )
        },
    )
    values = cells(rendered(state)[SHEET_FORM])

    assert UNLINKED_LABEL in values
    assert "K01孤兒知識" in values


def test_an_empty_duty_is_still_shown():
    state = JobAnalysisState(
        current_duties=(Duty(duty_id="d1", statement="維運門市系統", display_order=0),)
    )
    values = cells(rendered(state)[SHEET_FORM])

    assert "T1維運門市系統" in values


# ── 邊界 ───────────────────────────────────────────────────────────────────


def test_an_empty_document_still_renders_a_valid_workbook():
    workbook = rendered(JobAnalysisState(), title="尚未命名")

    assert workbook.sheetnames == [SHEET_FORM, SHEET_READINESS]
    assert "尚未命名職能基準" in cells(workbook[SHEET_FORM])
    assert DISCLAIMER in cells(workbook[SHEET_FORM])


def test_rendering_is_byte_stable_for_the_same_input():
    document = assemble_export_document(COMPLETE, title="門市營運專員")
    readiness = assess_readiness(
        header=COMPLETE.jd_header,
        duties=COMPLETE.current_duties,
        tasks=COMPLETE.current_jd,
    )

    first = load_workbook(io.BytesIO(render_xlsx(document, readiness)))
    second = load_workbook(io.BytesIO(render_xlsx(document, readiness)))

    # XLSX 內含 zip timestamp，位元組不保證相同；比對讀回的內容
    assert cells(first[SHEET_FORM]) == cells(second[SHEET_FORM])
    assert cells(first[SHEET_READINESS]) == cells(second[SHEET_READINESS])


@pytest.mark.parametrize("level", [1, 6])
def test_the_task_competency_level_reaches_the_sheet(level: int):
    state = JobAnalysisState(
        current_duties=(Duty(duty_id="d1", statement="維運門市系統", display_order=0),),
        current_jd=(
            JdTask(
                task_id="t1",
                statement="每週彙整營運週報",
                display_order=0,
                duty_id="d1",
                competency_level=level,
            ),
        ),
    )

    assert str(level) in cells(rendered(state)[SHEET_FORM])
