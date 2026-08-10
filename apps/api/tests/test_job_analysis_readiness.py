"""Readiness 純函式（ADR 0052 決定 1–7、ADR 0053 決定 6–8）。"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.job_analysis.application import JobAnalysisState
from app.job_analysis.application.readiness import (
    DocumentReadiness,
    ReadinessIssue,
    ReadinessIssueCode,
    assess_readiness,
)
from app.core.domain import (
    CurrentJdOpks,
    Duty,
    JdHeader,
    JdTask,
    OpksEntityKind,
    OpksEvidenceLink,
    OpksItem,
    SourceKind,
    SourceRef,
)


def _assess(
    header: JdHeader,
    *,
    duties: tuple[Duty, ...] = (),
    tasks: tuple[JdTask, ...] = (),
    current_opks: CurrentJdOpks | None = None,
) -> DocumentReadiness:
    return assess_readiness(
        header=header,
        duties=duties,
        tasks=tasks,
        current_opks=current_opks or CurrentJdOpks(),
    )


def _complete_header(**overrides: object) -> JdHeader:
    fields: dict[str, object] = {
        "competency_name": "資訊安全維運人員",
        "work_description": "維運企業資訊安全設備並處理資安事件。",
        "competency_level": 4,
    }
    fields.update(overrides)
    return JdHeader(**fields)  # type: ignore[arg-type]


def test_a_complete_header_stays_silent() -> None:
    readiness = _assess(_complete_header())

    assert readiness.issues == ()
    assert readiness.issue_count == 0


@pytest.mark.parametrize(
    ("field", "expected"),
    [
        ("competency_name", ReadinessIssueCode.COMPETENCY_NAME_MISSING),
        ("work_description", ReadinessIssueCode.WORK_DESCRIPTION_MISSING),
        ("competency_level", ReadinessIssueCode.COMPETENCY_LEVEL_MISSING),
    ],
)
def test_each_determinable_header_gap_raises_its_own_issue(
    field: str, expected: ReadinessIssueCode
) -> None:
    readiness = _assess(_complete_header(**{field: None}))

    assert tuple(issue.code for issue in readiness.issues) == (expected,)


def test_an_empty_header_reports_every_first_version_issue() -> None:
    readiness = _assess(JdHeader())

    assert tuple(issue.code for issue in readiness.issues) == (
        ReadinessIssueCode.COMPETENCY_NAME_MISSING,
        ReadinessIssueCode.WORK_DESCRIPTION_MISSING,
        ReadinessIssueCode.COMPETENCY_LEVEL_MISSING,
    )
    assert readiness.issue_count == 3
    assert not hasattr(readiness, "is_complete")


def test_notes_are_conditional_and_never_reported_missing() -> None:
    """ADR 0053 決定 8：說明與補充事項空白不列缺漏。"""

    readiness = _assess(_complete_header(notes=None))

    assert readiness.issues == ()


def test_the_category_group_stays_silent_in_the_first_version() -> None:
    """ADR 0052 決定 6：官方規則無法確定必填的一律不提示。"""

    readiness = _assess(
        _complete_header(
            occupation_category_name=None,
            occupation_name=None,
            occupation_code=None,
            industry_name=None,
            industry_code=None,
        )
    )

    assert readiness.issues == ()


def test_issue_order_is_deterministic_and_follows_the_official_form() -> None:
    first = _assess(JdHeader())
    second = _assess(JdHeader())

    assert first == second
    assert first.issues == second.issues


def test_readiness_reports_no_completion_verdict() -> None:
    """ADR 0053 決定 6：第一版不得有 is_complete／ready／百分比。"""

    fields = set(DocumentReadiness.model_fields)

    assert fields == {"issues"}
    for banned in ("is_complete", "ready", "complete", "percent", "percentage", "score"):
        assert banned not in fields


def test_readiness_issue_rejects_a_redundant_field_locator() -> None:
    with pytest.raises(ValidationError):
        ReadinessIssue(
            code=ReadinessIssueCode.COMPETENCY_NAME_MISSING,
            field="work_description",
        )


def test_readiness_is_a_frozen_value() -> None:
    readiness = _assess(JdHeader())

    with pytest.raises(Exception):
        readiness.issues = ()  # type: ignore[misc]


def test_assessment_is_pure_and_does_not_touch_transport_or_io() -> None:
    """ADR 0052 決定 1：規則住 app/job_analysis，不依賴 transport contract。"""

    source = (
        Path(__file__).parents[1]
        / "app"
        / "job_analysis"
        / "application"
        / "readiness.py"
    )
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            modules.append(node.module)

    for module in modules:
        root = module.split(".", 1)[0]
        assert root not in {
            "job_analysis_contract",
            "fastapi",
            "sqlalchemy",
            "httpx",
        }, module


def test_state_requires_an_explicit_header_partition() -> None:
    with pytest.raises(ValidationError):
        JobAnalysisState()


def test_readiness_reports_each_structure_gap_once_without_task_identity() -> None:
    duties = (
        Duty(duty_id="d1", statement="門市營運", display_order=0),
        Duty(duty_id="d2", statement="庫存管理", display_order=1),
    )
    tasks = (
        JdTask(task_id="t1", statement="盤點庫存", display_order=0),
        JdTask(task_id="t2", statement="整理週報", display_order=1),
    )

    readiness = _assess(_complete_header(), duties=duties, tasks=tasks)

    assert tuple(issue.code for issue in readiness.issues) == (
        ReadinessIssueCode.TASK_DUTY_MISSING,
        ReadinessIssueCode.TASK_COMPETENCY_LEVEL_MISSING,
        ReadinessIssueCode.DUTY_WITHOUT_TASK,
    )
    assert readiness.issue_count == 3


def test_readiness_reports_unlinked_knowledge_or_skill_once() -> None:
    item = OpksItem(
        entity_id="knowledge-1",
        entity_kind=OpksEntityKind.KNOWLEDGE,
        text="庫存差異成因",
        evidence_links=(
            OpksEvidenceLink(
                source_ref=SourceRef(kind=SourceKind.DIRECT_EDIT, id="edit-1")
            ),
        ),
    )

    readiness = _assess(
        _complete_header(),
        current_opks=CurrentJdOpks(items=(item,)),
    )

    assert tuple(issue.code for issue in readiness.issues) == (
        ReadinessIssueCode.OPKS_TASK_LINK_MISSING,
    )


def test_readiness_reports_stale_direct_task_refs_once() -> None:
    duty = Duty(duty_id="d1", statement="門市營運", display_order=0)
    task = JdTask(
        task_id="t1",
        statement="盤點庫存",
        display_order=0,
        duty_id="d1",
        competency_level=4,
    )
    evidence = OpksEvidenceLink(
        source_ref=SourceRef(kind=SourceKind.DIRECT_EDIT, id="edit-1")
    )
    knowledge = OpksItem(
        entity_id="knowledge-1",
        entity_kind=OpksEntityKind.KNOWLEDGE,
        text="庫存差異成因",
        task_refs=("retired-task",),
        evidence_links=(evidence,),
    )
    skill = OpksItem(
        entity_id="skill-1",
        entity_kind=OpksEntityKind.SKILL,
        text="盤點差異分析",
        task_refs=("missing-task",),
        evidence_links=(evidence,),
    )

    readiness = _assess(
        _complete_header(),
        duties=(duty,),
        tasks=(task,),
        current_opks=CurrentJdOpks(items=(knowledge, skill)),
    )

    assert tuple(issue.code for issue in readiness.issues) == (
        ReadinessIssueCode.OPKS_TASK_LINK_MISSING,
    )


def test_readiness_accepts_an_indicator_linked_to_a_current_task() -> None:
    duty = Duty(duty_id="d1", statement="門市營運", display_order=0)
    task = JdTask(
        task_id="t1",
        statement="盤點庫存",
        display_order=0,
        duty_id="d1",
        competency_level=4,
    )
    evidence = OpksEvidenceLink(
        source_ref=SourceRef(kind=SourceKind.DIRECT_EDIT, id="edit-1")
    )
    indicator = OpksItem(
        entity_id="indicator-1",
        entity_kind=OpksEntityKind.INDICATOR,
        text="帳實差異可追溯",
        task_refs=("t1",),
        evidence_links=(evidence,),
    )
    knowledge = OpksItem(
        entity_id="knowledge-1",
        entity_kind=OpksEntityKind.KNOWLEDGE,
        text="庫存差異成因",
        indicator_refs=("indicator-1",),
        evidence_links=(evidence,),
    )

    readiness = _assess(
        _complete_header(),
        duties=(duty,),
        tasks=(task,),
        current_opks=CurrentJdOpks(items=(indicator, knowledge)),
    )

    assert readiness.issues == ()


def test_readiness_reports_an_indicator_whose_task_ref_is_stale() -> None:
    duty = Duty(duty_id="d1", statement="門市營運", display_order=0)
    task = JdTask(
        task_id="t1",
        statement="盤點庫存",
        display_order=0,
        duty_id="d1",
        competency_level=4,
    )
    evidence = OpksEvidenceLink(
        source_ref=SourceRef(kind=SourceKind.DIRECT_EDIT, id="edit-1")
    )
    indicator = OpksItem(
        entity_id="indicator-1",
        entity_kind=OpksEntityKind.INDICATOR,
        text="帳實差異可追溯",
        task_refs=("retired-task",),
        evidence_links=(evidence,),
    )
    knowledge = OpksItem(
        entity_id="knowledge-1",
        entity_kind=OpksEntityKind.KNOWLEDGE,
        text="庫存差異成因",
        indicator_refs=("indicator-1",),
        evidence_links=(evidence,),
    )

    readiness = _assess(
        _complete_header(),
        duties=(duty,),
        tasks=(task,),
        current_opks=CurrentJdOpks(items=(indicator, knowledge)),
    )

    assert tuple(issue.code for issue in readiness.issues) == (
        ReadinessIssueCode.OPKS_TASK_LINK_MISSING,
    )


def test_readiness_does_not_require_output_attitude_or_notes() -> None:
    duty = Duty(duty_id="d1", statement="門市營運", display_order=0)
    task = JdTask(
        task_id="t1",
        statement="盤點庫存",
        display_order=0,
        duty_id="d1",
        competency_level=4,
    )
    output = OpksItem(
        entity_id="output-1",
        entity_kind=OpksEntityKind.OUTPUT,
        text="盤點結果",
        task_refs=("t1",),
        evidence_links=(
            OpksEvidenceLink(
                source_ref=SourceRef(kind=SourceKind.EMPLOYEE_TURN, id="turn-1"),
                quote="員工說明盤點結果",
            ),
        ),
    )
    attitude = OpksItem(
        entity_id="attitude-1",
        entity_kind=OpksEntityKind.ATTITUDE,
        text="謹慎",
        evidence_links=(
            OpksEvidenceLink(
                source_ref=SourceRef(kind=SourceKind.EMPLOYEE_TURN, id="turn-1"),
                quote="員工說明工作態度",
            ),
        ),
    )

    readiness = _assess(
        _complete_header(notes=None),
        duties=(duty,),
        tasks=(task,),
        current_opks=CurrentJdOpks(items=(output, attitude)),
    )

    assert readiness.issues == ()
