"""Offline fixture integrity, not an assertion that an LLM understood these jobs."""

import json
from pathlib import Path

import pytest

from caliburn.contracts.generated.tools.create_work_situation_arguments import (
    CreateWorkSituationArguments,
)

FIXTURES = Path(__file__).parents[1] / "fixtures/job_analysis_quality"
CASES = json.loads((FIXTURES / "cases.json").read_text(encoding="utf-8"))
ORACLES = json.loads((FIXTURES / "oracles.json").read_text(encoding="utf-8"))


def test_small_dataset_covers_requested_risks_without_claiming_blind_holdout() -> None:
    cases = CASES["cases"]
    ids = [case["id"] for case in cases]
    assert len(ids) == len(set(ids)) == 13
    assert set(ids) == ORACLES["cases"].keys()
    assert CASES["data_origin"] == "fully_synthetic"
    assert ORACLES["audience"] == "reviewer_only_never_model_input"
    assert sum(case["split"] == "development" for case in cases) == 11
    assert sum(case["split"] == "holdout_candidate" for case in cases) == 2
    risks = {risk for case in cases for risk in case["risks"]}
    assert {
        "correction",
        "missing_subject",
        "partial_coverage",
        "low_frequency",
        "manual_draft",
        "responsibility_boundary",
        "uncertainty",
        "sufficient_evidence",
        "no_forced_write",
        "confirmed_standard",
        "conditional_responsibility",
        "shared_collaborator_scope",
        "work_background",
        "no_profile_repetition",
        "cross_turn_source",
    } <= risks


@pytest.mark.parametrize("case", CASES["cases"], ids=lambda case: case["id"])
def test_inputs_have_realistic_source_positions_and_no_grader_answers(case) -> None:
    supplied = case["input"]
    assert supplied.keys() == {
        "formal_interview",
        "current_input",
        "seed_work_situations",
        "jd_draft",
    }
    messages = supplied["formal_interview"]
    assert [item["sequence"] for item in messages] == list(range(1, len(messages) + 1))
    assert messages[-1]["speaker"] == "consultant"
    for item in messages:
        assert item["speaker"] == ("consultant" if item["sequence"] % 2 else "employee")
        assert item["text"].strip()
    # Pending A input has text only, never a fabricated formal sequence/source identity.
    assert isinstance(supplied["current_input"], str) and supplied["current_input"].strip()
    employee_sequences = {item["sequence"] for item in messages if item["speaker"] == "employee"}
    for seed in supplied["seed_work_situations"]:
        CreateWorkSituationArguments.model_validate(seed)
        assert set(seed["interview_references"]) <= employee_sequences
    for draft in supplied["jd_draft"]:
        assert set(draft["source_sequences"]) <= employee_sequences
        assert draft["authorship"] in {"human", "model"}
        assert type(draft["manual_pending"]) is bool


@pytest.mark.parametrize("case", CASES["cases"], ids=lambda case: case["id"])
def test_each_oracle_has_traceable_basis_role_examples_and_counterexample(case) -> None:
    oracle = ORACLES["cases"][case["id"]]
    inputs = case["input"]
    allowed = {"current_input"}
    allowed.update(f"interview:{item['sequence']}" for item in inputs["formal_interview"])
    allowed.update(f"jd_draft:{index}" for index in range(len(inputs["jd_draft"])))
    assert set(oracle["basis"]) <= allowed
    assert oracle["must_preserve"] and oracle["must_not_assert"] and oracle["hard_failures"]
    assert oracle["roles"].keys() == {"A", "B1", "B2"}
    for examples in oracle["roles"].values():
        assert examples["accept"].strip() and examples["reject"].strip()
        assert examples["accept"] != examples["reject"]
    assert oracle["acceptable_variation"].strip()
    assert oracle["guide_sections"].keys() == {"analysis", "writing", "interview"}


def test_manual_draft_counterexample_cannot_be_mistaken_for_ground_truth() -> None:
    case = next(
        case for case in CASES["cases"] if case["id"] == "manual_draft_is_not_employee_fact"
    )
    draft = case["input"]["jd_draft"][0]
    assert draft["authorship"] == "human" and draft["manual_pending"]
    assert draft["source_sequences"] == [2]
    # This is deliberately a contradictory draft, not a positive reference JD.
    assert "每年降低採購成本20%" in draft["text"]
    assert "沒有那個目標" in case["input"]["current_input"]


def test_background_cases_separate_shared_known_scope_from_unconfirmed_identity() -> None:
    cases = {case["id"]: case for case in CASES["cases"]}
    known = cases["shared_work_background_is_not_per_case_profile"]["input"]
    unknown = cases["unconfirmed_background_is_not_a_profile_blank"]["input"]
    # Context is stated once in the earlier employee answer, not repeated for each task.
    assert "學習推廣組" in known["formal_interview"][1]["text"]
    assert "學習推廣組" not in known["current_input"]
    assert known["seed_work_situations"][0]["interview_references"] == [2]
    # The contrasting case cannot be satisfied by filling the known case's identity.
    assert "正式職稱與歸屬單位還沒有確認" in unknown["formal_interview"][1]["text"]
    assert "仍未確認" in unknown["current_input"]
    assert "unknown_scope_stays_unknown" in cases
