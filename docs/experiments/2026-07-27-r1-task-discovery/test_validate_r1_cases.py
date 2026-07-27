"""八案凍結完整性測試。全部離線，不碰 provider、DB 或 Web。"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from contracts import load_case, load_case_dir, suite_hash
from validate_r1_cases import CASES_DIR, EXPECTED_CASE_IDS, validate_suite


@pytest.fixture(scope="module")
def cases() -> list[dict]:
    return load_case_dir(CASES_DIR)


def test_eight_frozen_cases_are_present(cases: list[dict]) -> None:
    assert [c["case_id"] for c in cases] == list(EXPECTED_CASE_IDS)


def test_frozen_suite_validates(cases: list[dict]) -> None:
    result = validate_suite(cases)
    assert result.ok, [str(f) for f in result.findings]


def test_suite_hash_is_stable_and_order_independent(cases: list[dict]) -> None:
    first = suite_hash(cases)
    assert first == suite_hash(list(reversed(cases)))
    assert first == suite_hash(load_case_dir(CASES_DIR))
    assert len(first) == 64


def test_suite_hash_changes_when_a_case_changes(cases: list[dict]) -> None:
    mutated = copy.deepcopy(cases)
    mutated[0]["sources"][0]["text"] += "。"
    assert suite_hash(mutated) != suite_hash(cases)


def test_all_cases_are_constructed_edge(cases: list[dict]) -> None:
    # ADR 0040 風險段：目前沒有真實員工訪談資料。
    assert {c["source_type"] for c in cases} == {"constructed_edge"}


def test_only_ti_r1_08_carries_initial_work_model(cases: list[dict]) -> None:
    with_state = [c["case_id"] for c in cases if c.get("initial_work_model")]
    assert with_state == ["TI-R1-08"]


def test_anchors_are_marked(cases: list[dict]) -> None:
    anchors = {c["case_id"] for c in cases if c.get("locked_regression_anchor")}
    assert anchors == {"TI-R1-02", "TI-R1-07"}


# --- 反例：每條檢查都要真的會擋 -------------------------------------------------


@pytest.fixture()
def one_case() -> dict:
    return load_case(Path(CASES_DIR) / "TI-R1-01.json")


def _errors(case: dict) -> list[str]:
    return [f.check for f in validate_suite([case]).findings]


def test_rejects_wrong_schema_id(one_case: dict) -> None:
    one_case["schema_id"] = "something-else"
    assert "case_shape" in _errors(one_case)


def test_rejects_real_employee_interview_claim(one_case: dict) -> None:
    one_case["source_type"] = "real_employee_interview"
    assert "source_type" in _errors(one_case)


def test_rejects_unknown_source_type(one_case: dict) -> None:
    one_case["source_type"] = "vibes"
    assert "source_type" in _errors(one_case)


def test_rejects_unknown_common_dimension(one_case: dict) -> None:
    one_case["expected"]["common_applicable_rubric_dimensions"] = ["not_a_dimension"]
    assert "dimensions" in _errors(one_case)


def test_rejects_dimension_listed_as_both_common_and_full_only(one_case: dict) -> None:
    one_case["expected"]["common_applicable_rubric_dimensions"].append(
        "state_change_targets_existing_task"
    )
    one_case["expected"]["full_harness_only_dimensions"] = ["state_change_targets_existing_task"]
    assert "dimensions" in _errors(one_case)


def test_rejects_family_id_not_equal_to_case_id(one_case: dict) -> None:
    one_case["case_family_id"] = "TI-R1-99"
    assert "case_family" in _errors(one_case)


def test_rejects_unmarked_anchor() -> None:
    case = load_case(Path(CASES_DIR) / "TI-R1-02.json")
    del case["locked_regression_anchor"]
    assert "anchor" in _errors(case)


def test_rejects_anchor_flag_on_non_anchor(one_case: dict) -> None:
    one_case["locked_regression_anchor"] = True
    assert "anchor" in _errors(one_case)


def test_rejects_template_residue(one_case: dict) -> None:
    one_case["expected"]["required_behaviors"].append("TODO 補這條")
    assert "template_residue" in _errors(one_case)


def test_rejects_duplicate_source_id(one_case: dict) -> None:
    one_case["sources"].append(dict(one_case["sources"][0]))
    assert "sources" in _errors(one_case)


def test_rejects_case_without_employee_turn(one_case: dict) -> None:
    for src in one_case["sources"]:
        src["source_kind"] = "consultant_turn"
    assert "sources" in _errors(one_case)


def test_rejects_empty_source_text(one_case: dict) -> None:
    one_case["sources"][1]["text"] = "   "
    assert "sources" in _errors(one_case)


def test_rejects_initial_work_model_referencing_missing_source() -> None:
    case = load_case(Path(CASES_DIR) / "TI-R1-08.json")
    case["initial_work_model"]["task_candidates"][0]["source_ids"] = ["turn-404"]
    assert "initial_work_model" in _errors(case)


def test_rejects_initial_work_model_without_full_only_dimensions() -> None:
    """這是 B1 的防線：帶既有狀態卻沒宣告 full-only 維度，
    minimal arm 就會在它結構上做不到的維度被記 fail。"""
    case = load_case(Path(CASES_DIR) / "TI-R1-08.json")
    case["expected"]["full_harness_only_dimensions"] = []
    assert "arm_applicability" in _errors(case)


def test_rejects_incomplete_suite(cases: list[dict]) -> None:
    assert "suite" in [f.check for f in validate_suite(cases[:3]).findings]
