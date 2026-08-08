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
from app.job_analysis.domain import JdHeader


def _complete_header(**overrides: object) -> JdHeader:
    fields: dict[str, object] = {
        "competency_name": "資訊安全維運人員",
        "work_description": "維運企業資訊安全設備並處理資安事件。",
        "competency_level": 4,
    }
    fields.update(overrides)
    return JdHeader(**fields)  # type: ignore[arg-type]


def test_a_complete_header_stays_silent() -> None:
    readiness = assess_readiness(_complete_header())

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
    readiness = assess_readiness(_complete_header(**{field: None}))

    assert tuple(issue.code for issue in readiness.issues) == (expected,)


def test_an_empty_header_reports_every_first_version_issue() -> None:
    readiness = assess_readiness(JdHeader())

    assert tuple(issue.code for issue in readiness.issues) == (
        ReadinessIssueCode.COMPETENCY_NAME_MISSING,
        ReadinessIssueCode.WORK_DESCRIPTION_MISSING,
        ReadinessIssueCode.COMPETENCY_LEVEL_MISSING,
    )
    assert readiness.issue_count == 3
    assert not hasattr(readiness, "is_complete")


def test_notes_are_conditional_and_never_reported_missing() -> None:
    """ADR 0053 決定 8：說明與補充事項空白不列缺漏。"""

    readiness = assess_readiness(_complete_header(notes=None))

    assert readiness.issues == ()


def test_the_category_group_stays_silent_in_the_first_version() -> None:
    """ADR 0052 決定 6：官方規則無法確定必填的一律不提示。"""

    readiness = assess_readiness(
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
    first = assess_readiness(JdHeader())
    second = assess_readiness(JdHeader())

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
    readiness = assess_readiness(JdHeader())

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
