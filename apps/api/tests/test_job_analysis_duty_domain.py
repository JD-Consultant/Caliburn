"""主要職責（Duty）與 Task 職能級別的結構不變量（ADR 0052 決定 10／13）。"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.job_analysis.application import JobAnalysisState
from app.job_analysis.domain import Duty, JdTask


def duty(duty_id: str = "duty-1", *, order: int = 0, statement: str = "維運門市系統") -> Duty:
    return Duty(duty_id=duty_id, statement=statement, display_order=order)


def jd_task(
    task_id: str = "task-1",
    *,
    order: int = 0,
    duty_id: str | None = None,
    competency_level: int | None = None,
) -> JdTask:
    return JdTask(
        task_id=task_id,
        statement="每週彙整營運週報",
        display_order=order,
        duty_id=duty_id,
        competency_level=competency_level,
    )


# ── Duty 形狀 ──────────────────────────────────────────────────────────────


def test_duty_carries_only_id_statement_and_order():
    """級別掛 Task 不掛 Duty；`T1` 是匯出版面位置碼，不落庫（決定 10）。"""

    fields = set(Duty.model_fields)

    assert fields == {"duty_id", "statement", "display_order"}
    assert not {name for name in fields if "level" in name}
    assert not {name for name in fields if "code" in name}


def test_duty_rejects_a_blank_statement_and_a_negative_order():
    with pytest.raises(ValidationError):
        Duty(duty_id="duty-1", statement="   ", display_order=0)
    with pytest.raises(ValidationError):
        Duty(duty_id="duty-1", statement="維運門市系統", display_order=-1)


def test_duty_is_frozen():
    value = duty()

    with pytest.raises(ValidationError):
        value.statement = "改掉"  # type: ignore[misc]


# ── Task 的兩個新欄位 ──────────────────────────────────────────────────────


@pytest.mark.parametrize("level", [1, 6])
def test_competency_level_accepts_the_official_range(level: int):
    assert jd_task(competency_level=level).competency_level == level


@pytest.mark.parametrize("level", [0, 7, -1])
def test_competency_level_rejects_values_outside_one_to_six(level: int):
    with pytest.raises(ValidationError):
        jd_task(competency_level=level)


def test_an_unassigned_task_is_a_legal_state():
    """ADR 0052 決定 13：不得自動合成假的 T1，所以未指派必須可表示。"""

    task = jd_task()

    assert task.duty_id is None
    assert task.competency_level is None
    assert JobAnalysisState(current_jd=(task,)).current_jd == (task,)


# ── state 層的結構不變量 ───────────────────────────────────────────────────


def test_a_task_pointing_at_an_unknown_duty_is_unrepresentable():
    """指向不存在的 Duty 會讓匯出算不出 T{i}.{j}，所以型別層就擋掉。"""

    with pytest.raises(ValidationError, match="unknown duty"):
        JobAnalysisState(
            current_duties=(duty("duty-1"),),
            current_jd=(jd_task(duty_id="duty-missing"),),
        )


def test_duties_must_be_unique_and_canonically_ordered():
    with pytest.raises(ValidationError, match="duplicate current JD duty ids"):
        JobAnalysisState(
            current_duties=(duty("duty-1", order=0), duty("duty-1", order=1))
        )
    with pytest.raises(ValidationError, match="display orders must be unique"):
        JobAnalysisState(
            current_duties=(duty("duty-1", order=0), duty("duty-2", order=0))
        )
    with pytest.raises(ValidationError, match="sorted by display order"):
        JobAnalysisState(
            current_duties=(duty("duty-2", order=1), duty("duty-1", order=0))
        )


def test_a_canonical_duty_and_task_structure_is_accepted():
    state = JobAnalysisState(
        current_duties=(duty("duty-1", order=0), duty("duty-2", order=1)),
        current_jd=(
            jd_task("task-1", order=0, duty_id="duty-1", competency_level=4),
            jd_task("task-2", order=1, duty_id="duty-2"),
            jd_task("task-3", order=2),
        ),
    )

    assert [d.duty_id for d in state.current_duties] == ["duty-1", "duty-2"]
    assert state.current_jd[2].duty_id is None


def test_state_defaults_to_no_duties():
    assert JobAnalysisState().current_duties == ()


# ── edited_jd_after 不得夾帶結構改動（§10.5）─────────────────────────────────


@pytest.mark.parametrize(
    ("field", "changed"),
    [("duty_id", "duty-2"), ("competency_level", 5)],
)
def test_editing_proposal_text_cannot_smuggle_a_structural_change(field, changed):
    """`edited` 是文字修改。職責歸屬與級別各有自己的入口，不得從改提案文字進來。"""

    from app.job_analysis.domain import JdEntry, validate_edited_jd_after

    original = jd_task("task-1", duty_id="duty-1", competency_level=4)
    before = (JdEntry(task_id="task-1", value=original),)
    edited = (
        JdEntry(
            task_id="task-1",
            value=original.model_copy(update={"statement": "員工改過的文字", field: changed}),
        ),
    )

    with pytest.raises(ValueError, match=field):
        validate_edited_jd_after(before, edited)


def test_editing_only_the_text_is_still_allowed():
    from app.job_analysis.domain import JdEntry, validate_edited_jd_after

    original = jd_task("task-1", duty_id="duty-1", competency_level=4)
    before = (JdEntry(task_id="task-1", value=original),)
    edited = (
        JdEntry(
            task_id="task-1",
            value=original.model_copy(update={"statement": "員工改過的文字"}),
        ),
    )

    validate_edited_jd_after(before, edited)  # 不得拋錯
