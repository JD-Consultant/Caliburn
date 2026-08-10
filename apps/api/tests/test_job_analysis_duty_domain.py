"""Duty 與 Task 層級的 domain 不變量。"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.job_analysis.application import JobAnalysisState
from app.core.domain import CurrentWorkModel, Duty, JdHeader, JdTask


def _task(*, duty_id: str | None = None) -> JdTask:
    return JdTask(
        task_id="task-1",
        statement="每週彙整營運週報",
        display_order=0,
        duty_id=duty_id,
    )


def test_state_requires_current_duties_explicitly() -> None:
    with pytest.raises(ValidationError, match="current_duties"):
        JobAnalysisState(jd_header=JdHeader())


def test_state_rejects_a_task_pointing_to_a_missing_duty() -> None:
    with pytest.raises(ValidationError, match="unknown Duty"):
        JobAnalysisState(
            jd_header=JdHeader(),
            current_duties=(),
            current_jd=(_task(duty_id="d9"),),
        )


def test_state_rejects_duplicate_duty_ids() -> None:
    duties = (
        Duty(duty_id="d1", statement="門市營運", display_order=0),
        Duty(duty_id="d1", statement="庫存管理", display_order=1),
    )

    with pytest.raises(ValidationError, match="duplicate Duty ids"):
        JobAnalysisState(jd_header=JdHeader(), current_duties=duties)


def test_state_rejects_duplicate_duty_display_orders() -> None:
    duties = (
        Duty(duty_id="d1", statement="門市營運", display_order=0),
        Duty(duty_id="d2", statement="庫存管理", display_order=0),
    )

    with pytest.raises(ValidationError, match="Duty display orders must be unique"):
        JobAnalysisState(jd_header=JdHeader(), current_duties=duties)


def test_state_requires_duties_in_canonical_display_order() -> None:
    duties = (
        Duty(duty_id="d2", statement="庫存管理", display_order=1),
        Duty(duty_id="d1", statement="門市營運", display_order=0),
    )

    with pytest.raises(ValidationError, match="Duties must be sorted"):
        JobAnalysisState(jd_header=JdHeader(), current_duties=duties)


def test_state_accepts_a_task_reference_to_an_existing_duty() -> None:
    duties = (Duty(duty_id="d1", statement="門市營運", display_order=0),)

    state = JobAnalysisState(
        jd_header=JdHeader(),
        current_duties=duties,
        current_jd=(_task(duty_id="d1"),),
        work_model=CurrentWorkModel(),
    )

    assert state.current_duties == duties
