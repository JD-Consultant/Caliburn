"""Segment 5：只保護會影響 R1a 結論或付費停線的 pure 行為。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from .blind_grader import build_blind_packets, build_grader_stage
from .contracts import load_case_dir
from .live_batch import (
    CALIBRATION_GOLD,
    R1A_ARM_IDS,
    build_screening_report,
    calibration_matches_gold,
    map_grades_to_arms,
    run_grader_pair,
    select_r1a_plans,
)
from .matrix import max_generator_calls
from .paths import CASES_DIR
from .runner import OUTCOME_COMPLETED, ObservationResult
from .runner import OUTCOME_FINAL_INVALID


def test_r1a_is_exactly_eight_cases_by_three_architecture_arms() -> None:
    plans = select_r1a_plans(load_case_dir(CASES_DIR))

    assert len(plans) == 24
    assert {plan.arm.arm_id for plan in plans} == set(R1A_ARM_IDS)
    assert max_generator_calls(plans) == 32


def test_grader_labels_are_mapped_back_only_after_blind_reconciliation() -> None:
    mapped = map_grades_to_arms(
        {"candidate-01": "A6", "candidate-02": "A1"},
        {
            "candidate-01": {"meaningful_outcome": "pass"},
            "candidate-02": {"meaningful_outcome": "unknown"},
        },
    )

    assert mapped == {
        "A1": {"meaningful_outcome": "unknown"},
        "A6": {"meaningful_outcome": "pass"},
    }


def test_calibration_requires_exact_pre_registered_gold() -> None:
    gold = {
        "candidate-01": {
            "meaningful_outcome": "pass",
            "source_grounding": "pass",
        },
        "candidate-02": {
            "meaningful_outcome": "fail",
            "source_grounding": "pass",
        },
        "candidate-03": {
            "meaningful_outcome": "unknown",
            "source_grounding": "unknown",
        },
    }

    assert calibration_matches_gold(gold, gold)
    assert not calibration_matches_gold(
        gold,
        {
            **gold,
            "candidate-03": {
                "meaningful_outcome": "pass",
                "source_grounding": "pass",
            },
        },
    )
    assert CALIBRATION_GOLD["candidate-03"] == {
        "meaningful_outcome": "unknown",
        "source_grounding": "unknown",
    }


def test_grader_prompt_requires_concise_reasons_to_fit_bounded_output() -> None:
    stage = build_grader_stage(
        {
            "case_id": "calibration",
            "sources": [],
            "candidates": [
                {
                    "label": "candidate-01",
                    "view": {
                        "analysis_decision": "no_change",
                        "proposed_tasks": [],
                        "next_question": None,
                        "limitations": [],
                    },
                }
            ],
        },
        dimensions=("meaningful_outcome",),
    )

    assert "每個 reason 限一個短句" in stage.system_instruction


def test_report_stays_provisional_until_owner_reviews_anchors() -> None:
    cases = load_case_dir(CASES_DIR)
    plans = select_r1a_plans(cases)
    results = [
        ObservationResult(
            observation_id=plan.observation_id,
            outcome=OUTCOME_COMPLETED,
            call_count=plan.arm.stage_count,
            canonical_view={
                "analysis_decision": "no_change",
                "proposed_tasks": [],
                "next_question": None,
                "limitations": [],
            },
            state_change_view=None,
            findings=(),
            stage_outputs=(),
        )
        for plan in plans
    ]
    grades = {
        case["case_id"]: {
            arm_id: {
                dimension: "pass"
                for dimension in case["expected"][
                    "common_applicable_rubric_dimensions"
                ]
            }
            for arm_id in R1A_ARM_IDS
        }
        for case in cases
    }

    report = build_screening_report(
        cases=cases,
        plans=plans,
        results=results,
        grades_by_case=grades,
        total_cost="1.90",
    )

    assert report["batch_complete"] is True
    assert report["provisional_screening_eligible"] is True
    assert report["quality_conclusion_eligible"] is False
    assert len(report["owner_review_queue"]) == 6


@pytest.mark.asyncio
async def test_grader_pair_maps_anonymous_labels_back_after_reconciliation() -> None:
    cases = load_case_dir(CASES_DIR)
    case = cases[0]
    results = {
        arm_id: ObservationResult(
            observation_id=f"{case['case_id']}:{arm_id}",
            outcome=OUTCOME_COMPLETED,
            call_count=1,
            canonical_view={
                "analysis_decision": "no_change",
                "proposed_tasks": [],
                "next_question": None,
                "limitations": [],
            },
            state_change_view=None,
            findings=(),
            stage_outputs=(),
        )
        for arm_id in R1A_ARM_IDS
    }
    forward, reverse, label_to_arm = build_blind_packets(case, results, seed=20260727)

    @dataclass
    class FakeSession:
        calls: int = 0

        async def send_structured(self, **kwargs: Any) -> dict[str, Any]:
            self.calls += 1
            return {
                "grades": [
                    {
                        "label": candidate["label"],
                        "dimensions": [
                            {
                                "dimension": "meaningful_outcome",
                                "verdict": "pass",
                                "reason": "test",
                            }
                        ],
                    }
                    for candidate in kwargs["context_packet"]["candidates"]
                ]
            }

    session = FakeSession()
    mapped = await run_grader_pair(
        session=session,
        case=case,
        suite_hash="suite",
        forward=forward,
        reverse=reverse,
        label_to_arm=label_to_arm,
        dimensions=("meaningful_outcome",),
    )

    assert session.calls == 2
    assert mapped == {
        arm_id: {"meaningful_outcome": "pass"}
        for arm_id in sorted(R1A_ARM_IDS)
    }


def test_deterministic_invalid_is_a_completed_quality_observation_not_missing_data() -> None:
    cases = load_case_dir(CASES_DIR)
    plans = select_r1a_plans(cases)
    results = [
        ObservationResult(
            observation_id=plan.observation_id,
            outcome=(
                OUTCOME_FINAL_INVALID
                if plan.observation_id == plans[0].observation_id
                else OUTCOME_COMPLETED
            ),
            call_count=plan.arm.stage_count,
            canonical_view=None,
            state_change_view=None,
            findings=(),
            stage_outputs=(),
        )
        for plan in plans
    ]
    grades = {
        case["case_id"]: {
            arm_id: {
                dimension: "pass"
                for dimension in case["expected"][
                    "common_applicable_rubric_dimensions"
                ]
            }
            for arm_id in R1A_ARM_IDS
            if not (
                case["case_id"] == plans[0].case_id
                and arm_id == plans[0].arm.arm_id
            )
        }
        for case in cases
    }

    report = build_screening_report(
        cases=cases,
        plans=plans,
        results=results,
        grades_by_case=grades,
        total_cost="1.00",
    )

    assert report["batch_complete"] is True
    assert report["provisional_screening_eligible"] is True
    assert report["outcomes"][OUTCOME_FINAL_INVALID] == 1
    assert {
        (item["case_id"], item["arm_id"], item["reason"])
        for item in report["owner_review_queue"]
    } >= {
        (
            plans[0].case_id,
            plans[0].arm.arm_id,
            "deterministic_invalid",
        )
    }
