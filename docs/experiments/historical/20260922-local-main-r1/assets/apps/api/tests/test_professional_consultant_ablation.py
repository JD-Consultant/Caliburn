"""ADR 0040 literal registry and fast-screen planning tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from evals.professional_consultant.r1.ablation import (
    ABLATION_ARMS,
    build_fast_screen_plan,
)
from evals.professional_consultant.r1.loader import load_runtime_suite


CASES_ROOT = (
    Path(__file__).parents[1]
    / "evals"
    / "professional_consultant"
    / "r1"
    / "cases"
)


def test_ablation_registry_is_the_six_literal_adr_0040_arms() -> None:
    assert [
        (
            arm.arm_id.value,
            arm.model_tier.value,
            arm.schema_profile.value,
            arm.runner_kind.value,
            arm.harness_profile.value,
            arm.expected_generator_calls,
        )
        for arm in ABLATION_ARMS
    ] == [
        ("A1", "strongest", "light", "once", "minimal", 1),
        ("A2", "strongest", "light", "two_stage", "full", 2),
        ("A3", "strongest", "heavy", "two_stage", "full", 2),
        ("A4", "cheap", "light", "two_stage", "full", 2),
        ("A5", "cheap", "heavy", "two_stage", "full", 2),
        ("A6", "strongest", "light", "once", "full", 1),
    ]


def test_fast_screen_plan_has_48_slots_and_80_generator_calls() -> None:
    cases = load_runtime_suite(CASES_ROOT)

    plan = build_fast_screen_plan(cases)

    assert plan.schema_version == "r1_fast_screen_plan.v1"
    assert plan.case_count == 8
    assert plan.arm_count == 6
    assert plan.planned_observations == 48
    assert plan.expected_generator_calls == 80
    assert plan.grader_calls_included is False
    assert len(plan.trials) == 48
    assert len({trial.trial_id for trial in plan.trials}) == 48
    assert {
        (trial.case_id, trial.arm.arm_id.value) for trial in plan.trials
    } == {
        (case.metadata.case_id, arm.arm_id.value)
        for case in cases
        for arm in ABLATION_ARMS
    }


def test_fast_screen_plan_rejects_anything_other_than_eight_unique_cases() -> None:
    cases = load_runtime_suite(CASES_ROOT)

    with pytest.raises(ValueError, match="exactly eight"):
        build_fast_screen_plan(cases[:-1])
    with pytest.raises(ValueError, match="unique"):
        build_fast_screen_plan((*cases[:-1], cases[0]))
