"""All methods get the same scheduled cases; a stopped arm is never silently restarted."""

import asyncio

import pytest
from caliburn.agent_execution.request_capacity import (
    CompactionRequiredError,
    RequestCapacityError,
    RequestOverCapacityError,
)
from study_batch import run_schedule, schedule
from study_window import StudyCapacityError


def test_eight_cases_rotate_arm_order_without_future_input():
    cases = [{"case_id": f"c{i:02}", "employee_input": str(i)} for i in range(1, 9)]
    planned = schedule(cases)
    assert len(planned) == 24
    assert [arm for arm, _ in planned[:9]] == [
        "raw",
        "summary",
        "memory",
        "summary",
        "memory",
        "raw",
        "memory",
        "raw",
        "summary",
    ]
    assert [c["employee_input"] for arm, c in planned if arm == "memory"] == [
        str(i) for i in range(1, 9)
    ]


def test_capacity_stop_skips_only_that_arm_and_keeps_partial_evidence():
    seen = []
    events = []

    async def run(arm, case):
        seen.append((arm, case["case_id"]))
        if arm == "summary":
            raise StudyCapacityError("second_pre_work_reset_required")

    cases = [{"case_id": "c01", "employee_input": "a"}, {"case_id": "c02", "employee_input": "b"}]
    outcome = asyncio.run(run_schedule(cases, run, events.append))
    assert seen == [
        ("raw", "c01"),
        ("summary", "c01"),
        ("memory", "c01"),
        ("memory", "c02"),
        ("raw", "c02"),
    ]
    assert outcome["completed"] == {"raw": ["c01", "c02"], "summary": [], "memory": ["c01", "c02"]}
    assert outcome["capacity_stops"] == {"summary": "second_pre_work_reset_required"}
    assert events[1]["event"] == "capacity_stop"


def test_unexpected_failure_does_not_advance_next_arm():
    seen = []

    async def run(arm, case):
        seen.append(arm)
        raise RuntimeError("synthetic")

    import pytest

    with pytest.raises(RuntimeError):
        asyncio.run(
            run_schedule([{"case_id": "c01", "employee_input": "a"}], run, lambda event: None)
        )
    assert seen == ["raw"]


@pytest.mark.parametrize("kind", ["hard_capacity", "after_compact"])
def test_valid_counted_overflow_does_not_stop_other_arms(kind):
    seen = []

    async def run(arm, case):
        seen.append(arm)
        if arm == "summary":
            if kind == "hard_capacity":
                raise RequestOverCapacityError(input_tokens=922001, allowed_input_tokens=922000)
            try:
                raise CompactionRequiredError("counted 160001")
            except CompactionRequiredError as cause:
                raise RequestCapacityError(
                    "The compacted window still exceeds the boundary threshold"
                ) from cause

    result = asyncio.run(
        run_schedule([{"case_id": "c01", "employee_input": "a"}], run, lambda event: None)
    )
    assert seen == ["raw", "summary", "memory"]
    assert "summary" in result["capacity_stops"]


def test_invalid_capacity_policy_is_not_a_method_capacity_result():
    async def run(arm, case):
        raise RequestCapacityError("invalid policy")

    with pytest.raises(RequestCapacityError, match="invalid policy"):
        asyncio.run(
            run_schedule([{"case_id": "c01", "employee_input": "a"}], run, lambda event: None)
        )
