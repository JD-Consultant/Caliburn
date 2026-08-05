"""Readiness 純函式（ADR 0052 決定 1–7、ADR 0053 決定 6–8）。"""

from __future__ import annotations

import pytest

from app.job_analysis.application.readiness import (
    DocumentReadiness,
    ReadinessIssueCode,
    assess_readiness,
)
from app.job_analysis.domain import Duty, JdHeader, JdTask


def _duty(duty_id: str = "duty-1", *, order: int = 0) -> Duty:
    return Duty(duty_id=duty_id, statement="維運門市系統", display_order=order)


def _task(
    task_id: str = "task-1",
    *,
    order: int = 0,
    duty_id: str | None = "duty-1",
    competency_level: int | None = 4,
) -> JdTask:
    return JdTask(
        task_id=task_id,
        statement="每週彙整營運週報",
        display_order=order,
        duty_id=duty_id,
        competency_level=competency_level,
    )


def _assess(header=None, duties=None, tasks=None):
    """完整結構的預設：一個 Duty、一個已歸屬且已填級別的 Task。"""

    return assess_readiness(
        header=_complete_header() if header is None else header,
        duties=(_duty(),) if duties is None else duties,
        tasks=(_task(),) if tasks is None else tasks,
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
    readiness = _assess()

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
    readiness = _assess(header=_complete_header(**{field: None}))

    assert tuple(issue.code for issue in readiness.issues) == (expected,)


def test_an_empty_header_reports_every_first_version_issue() -> None:
    readiness = _assess(header=JdHeader())

    assert tuple(issue.code for issue in readiness.issues) == (
        ReadinessIssueCode.COMPETENCY_NAME_MISSING,
        ReadinessIssueCode.WORK_DESCRIPTION_MISSING,
        ReadinessIssueCode.COMPETENCY_LEVEL_MISSING,
    )
    assert readiness.issue_count == 3


def test_notes_are_conditional_and_never_reported_missing() -> None:
    """ADR 0053 決定 8：說明與補充事項空白不列缺漏。"""

    readiness = _assess(header=_complete_header(notes=None))

    assert readiness.issues == ()


def test_the_category_group_stays_silent_in_the_first_version() -> None:
    """ADR 0052 決定 6：官方規則無法確定必填的一律不提示。"""

    readiness = _assess(
        header=_complete_header(
            occupation_category_name=None,
            occupation_name=None,
            occupation_code=None,
            industry_name=None,
            industry_code=None,
        )
    )

    assert readiness.issues == ()


def test_issue_order_is_deterministic_and_follows_the_official_form() -> None:
    first = _assess(header=JdHeader())
    second = _assess(header=JdHeader())

    assert first == second
    assert first.issues == second.issues


def test_readiness_reports_no_completion_verdict() -> None:
    """ADR 0053 決定 6：第一版不得有 is_complete／ready／百分比。"""

    fields = set(DocumentReadiness.model_fields)

    assert fields == {"issues"}
    for banned in ("is_complete", "ready", "complete", "percent", "percentage", "score"):
        assert banned not in fields


def test_every_issue_carries_the_field_it_points_at() -> None:
    readiness = _assess(header=JdHeader())

    assert tuple(issue.field for issue in readiness.issues) == (
        "jd_header.competency_name",
        "jd_header.work_description",
        "jd_header.competency_level",
    )


def test_readiness_is_a_frozen_value() -> None:
    readiness = _assess(header=JdHeader())

    with pytest.raises(Exception):
        readiness.issues = ()  # type: ignore[misc]


def test_assessment_is_pure_and_does_not_touch_transport_or_io() -> None:
    """ADR 0052 決定 1：規則住 app/job_analysis，不依賴 transport contract。"""

    import ast
    from pathlib import Path

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


# ── Duty 與 Task 職能級別（Duty 切片 T2）──────────────────────────────────────


def test_a_complete_structure_stays_silent():
    assert _assess().issues == ()


def test_an_unassigned_task_is_reported():
    readiness = _assess(tasks=(_task(duty_id=None),))

    assert ReadinessIssueCode.TASK_DUTY_MISSING in {
        issue.code for issue in readiness.issues
    }


def test_a_task_without_a_competency_level_is_reported():
    readiness = _assess(tasks=(_task(competency_level=None),))

    assert ReadinessIssueCode.TASK_COMPETENCY_LEVEL_MISSING in {
        issue.code for issue in readiness.issues
    }


def test_a_duty_with_no_task_under_it_is_reported():
    """空職責在版型上推不出任何 `T{i}.{j}` 列。"""

    readiness = _assess(duties=(_duty("duty-1"), _duty("duty-2", order=1)))

    assert ReadinessIssueCode.DUTY_WITHOUT_TASK in {
        issue.code for issue in readiness.issues
    }


def test_structural_gaps_are_reported_once_per_code_not_once_per_task():
    """readiness 是提示不是待辦清單；UI 也用 code 當 key。"""

    readiness = _assess(
        tasks=(
            _task("task-1", order=0, duty_id=None, competency_level=None),
            _task("task-2", order=1, duty_id=None, competency_level=None),
            _task("task-3", order=2, duty_id=None, competency_level=None),
        ),
    )
    codes = [issue.code for issue in readiness.issues]

    assert len(codes) == len(set(codes))
    assert codes.count(ReadinessIssueCode.TASK_DUTY_MISSING) == 1
    assert codes.count(ReadinessIssueCode.TASK_COMPETENCY_LEVEL_MISSING) == 1


def test_header_issues_come_before_structural_issues():
    """把唯一的 Task 抽離職責，也就讓那個職責變成空的——兩者都該報。"""

    readiness = _assess(header=JdHeader(), tasks=(_task(duty_id=None),))

    assert tuple(issue.code for issue in readiness.issues) == (
        ReadinessIssueCode.COMPETENCY_NAME_MISSING,
        ReadinessIssueCode.WORK_DESCRIPTION_MISSING,
        ReadinessIssueCode.COMPETENCY_LEVEL_MISSING,
        ReadinessIssueCode.TASK_DUTY_MISSING,
        ReadinessIssueCode.DUTY_WITHOUT_TASK,
    )


def test_the_two_competency_level_codes_point_at_different_fields():
    """header 與 Task 各有一個 competency_level;`field` 必須分得出來是哪一個。"""

    header_gap = _assess(header=_complete_header(competency_level=None))
    task_gap = _assess(tasks=(_task(competency_level=None),))

    assert [i.field for i in header_gap.issues] == ["jd_header.competency_level"]
    assert [i.field for i in task_gap.issues] == ["current_jd.competency_level"]


def test_an_empty_document_reports_only_header_gaps():
    """沒有 Task 就沒有 Task 層缺漏可談;也不新增計畫外的 issue。"""

    readiness = assess_readiness(header=JdHeader(), duties=(), tasks=())

    assert tuple(issue.code for issue in readiness.issues) == (
        ReadinessIssueCode.COMPETENCY_NAME_MISSING,
        ReadinessIssueCode.WORK_DESCRIPTION_MISSING,
        ReadinessIssueCode.COMPETENCY_LEVEL_MISSING,
    )


def test_every_argument_is_required_so_a_caller_cannot_silently_skip_tasks():
    """漏傳要炸,不能安靜地變成「這份文件沒有結構缺漏」。"""

    with pytest.raises(TypeError):
        assess_readiness(header=JdHeader())  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        assess_readiness(JdHeader(), (), ())  # type: ignore[misc]
