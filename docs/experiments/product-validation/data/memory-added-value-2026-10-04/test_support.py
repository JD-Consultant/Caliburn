"""Experiment integrity, not a replacement for semantic outcome grading."""

import json
from copy import deepcopy
from decimal import Decimal
from pathlib import Path

import pytest
from support import Budget, context_for, prepare_materials, validate_submission

SOURCE = (
    Path(__file__).parent.parent
    / "compaction-long-interview-2026-10-04/main-03/compaction_hierarchical_memory"
)


def material():
    return prepare_materials(
        json.loads((SOURCE / "product-052.json").read_text(encoding="utf-8")),
        json.loads((SOURCE / "memory-e052.json").read_text(encoding="utf-8")),
    )


def test_complete_interview_and_both_maps_have_no_future_sources():
    result = material()
    assert len(result.get("messages", [])) == 105
    assert len(result["maps"]["work_situation"]["items"]) == 12
    assert len(result["maps"]["work_understanding"]["items"]) == 1
    for obj in result["objects"].values():
        assert all(n <= 104 for n in obj.get("interview_references", []))


def test_raw_and_memory_context_share_full_raw_and_jd_without_old_native_items():
    result = material()
    raw = context_for(result, "raw", "核對退貨")
    memory = context_for(result, "raw_memory", "核對退貨")
    assert len(raw) == len(memory) == 2
    a, b = json.loads(raw[0]["content"]), json.loads(memory[0]["content"])
    assert a["historical_interview"] == b["historical_interview"]
    assert a["jd_draft"] == b["jd_draft"]
    assert "work_situation_map" not in a
    assert "work_situation_map" in b
    assert all(item["role"] == "user" for item in raw + memory)


def test_understanding_references_resolve_to_same_selected_snapshot_revisions():
    result = material()
    understanding = result["objects"][
        "work_understanding:庫存與物流行政的作業核對、追蹤與支援"
    ]
    assert len(understanding["work_situation_references"]) == 12
    assert {
        ref["target_title"] for ref in understanding["work_situation_references"]
    } == {entry["target_title"] for entry in result["maps"]["work_situation"]["items"]}


def test_corrupt_draft_is_shared_but_does_not_rewrite_source():
    product = json.loads((SOURCE / "product-052.json").read_text(encoding="utf-8"))
    before = deepcopy(product)
    result = prepare_materials(
        product, json.loads((SOURCE / "memory-e052.json").read_text(encoding="utf-8"))
    )
    assert "09:25" in result["slots"]["task_2.requirement_1"]
    assert product == before
    assert "09:25" not in "".join(m["text"] for m in result["messages"])


def test_unknown_or_future_citations_reject_entire_submission():
    result = material()
    proposal = {
        "changes": [
            {
                "target_ref": "task_2.description",
                "value": "改稿",
                "references": [
                    {
                        "kind": "interview",
                        "interview_sequence": 106,
                        "target_title": None,
                    }
                ],
            }
        ],
        "questions": [],
        "note": "",
    }
    assert validate_submission(result, "raw", proposal).get("status") == "rejected"
    proposal["changes"][0]["references"][0]["interview_sequence"] = 94
    assert validate_submission(result, "raw", proposal)["status"] == "accepted"


def test_raw_arm_cannot_use_memory_reference():
    result = material()
    proposal = {
        "changes": [
            {
                "target_ref": "task_2.description",
                "value": "改稿",
                "references": [
                    {
                        "kind": "work_situation",
                        "interview_sequence": None,
                        "target_title": "退貨核對、狀態登錄與差異處理",
                    }
                ],
            }
        ],
        "questions": [],
        "note": "",
    }
    assert validate_submission(result, "raw", proposal)["status"] == "rejected"
    assert validate_submission(result, "raw_memory", proposal)["status"] == "accepted"


def test_unknown_usage_keeps_reservation_and_prevents_next_call_over_cap():
    budget = Budget()
    budget.reserve("pending", Decimal("0.19"))
    with pytest.raises(ValueError, match="budget"):
        budget.reserve("next", Decimal("0.02"))
    assert budget.occupied == Decimal("0.19")


def test_settlement_and_time_boundary_are_enforced():
    budget = Budget()
    budget.reserve("one", Decimal("0.02"))
    budget.settle("one", Decimal("0.005"))
    assert budget.occupied == Decimal("0.005")
    budget.started -= 1801
    with pytest.raises(ValueError, match="time"):
        budget.reserve("two", Decimal("0.001"))
