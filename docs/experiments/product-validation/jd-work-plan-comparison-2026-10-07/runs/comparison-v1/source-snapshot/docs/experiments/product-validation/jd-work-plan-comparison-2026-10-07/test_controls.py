"""Offline controls: elapsed time, exact source, late review and anonymous events."""

import sys
from decimal import Decimal
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from controls import BatchGuard, accepted_source, checked_decision


def test_cancelled_batch_deadline_keeps_budget_and_usage_bounds():
    now = [0]
    guard = BatchGuard(limit=Decimal(4), clock=lambda: now[0], max_outbound=2)
    payload = {"model": "gpt-6-luna"}
    guard.outbound_attempt(payload)
    now[0] = 10**8
    guard.outbound_attempt(payload)
    with pytest.raises(RuntimeError, match="outbound"):
        guard.outbound_attempt(payload)


def test_unknown_usage_keeps_reservation_and_stops_new_work():
    guard = BatchGuard(limit=Decimal(4))
    guard.attempts["unobserved"] = Decimal("0.5")
    guard.settle("unobserved", None)
    assert guard.occupied == Decimal("0.5")
    with pytest.raises(RuntimeError, match="unknown provider usage"):
        guard.outbound_attempt({"model": "gpt-6-luna"})


def test_historical_equal_text_does_not_establish_current_source():
    command = {"command_id": "new", "text": "相同回答"}
    accepted = {"command_id": "new", "source_id": "new-source"}
    history = [
        {"source_id": "old-source", "speaker": "employee", "interview_text": "相同回答"}
    ]
    with pytest.raises(ValueError, match="source"):
        accepted_source(command, accepted, history)
    current = {**history[0], "source_id": "new-source"}
    assert accepted_source(command, accepted, history + [current]) == current


def test_decision_that_exists_after_timeout_is_not_used(tmp_path):
    path = tmp_path / "decision.json"
    path.write_text('{"question_id":"q"}', encoding="utf-8")
    with pytest.raises(TimeoutError):
        checked_decision(path, "q", 0, lambda: 300)
    assert checked_decision(path, "q", 0, lambda: 299)["question_id"] == "q"


def test_unknown_compound_part_cannot_disclose_known_general_answer():
    from materials import Employee
    from review_policy import reviewed_answer

    employee = Employee("course_admin")
    decision = {
        "mode": "answer",
        "fact_ids": ["refund"],
        "reason": "流程可答，普遍適用未知",
        "subquestions": [
            {
                "quote": "退費流程？",
                "mode": "answer",
                "fact_ids": ["refund"],
                "reason": "一般流程",
            },
            {
                "quote": "特殊情境是否普遍適用？",
                "mode": "unknown",
                "fact_ids": [],
                "reason": "oracle未提供",
            },
        ],
    }
    answer = reviewed_answer(employee, "退費流程？特殊情境是否普遍適用？", decision)
    assert "特殊情境是否普遍適用？" in answer
    decision["subquestions"][1]["fact_ids"] = ["refund"]
    with pytest.raises(ValueError):
        reviewed_answer(
            Employee("course_admin"), "退費流程？特殊情境是否普遍適用？", decision
        )


def test_compound_refusal_and_clarification_are_rendered_and_scope_is_retained():
    import copy

    from materials import Employee
    from review_policy import reviewed_answer

    original = Employee("course_admin")
    candidate = copy.deepcopy(original)
    question = "退費流程？特定投訴個案？那個東西呢？"
    decision = {
        "mode": "answer",
        "fact_ids": ["refund"],
        "reason": "逐問裁決",
        "subquestions": [
            {
                "quote": "退費流程？",
                "mode": "answer",
                "fact_ids": ["refund"],
                "reason": "一般流程",
            },
            {
                "quote": "特定投訴個案？",
                "mode": "refused",
                "fact_ids": [],
                "refused_topic": "evaluations",
                "reason": "凍結拒答範圍",
            },
            {
                "quote": "那個東西呢？",
                "mode": "clarify",
                "fact_ids": [],
                "reason": "指涉不明",
            },
        ],
    }
    answer = reviewed_answer(candidate, question, decision)
    assert "個案我不想談" in answer
    assert "問題我還沒理解" in answer
    assert candidate.refused_topics == {"evaluations"}
    assert not original.refused_topics


def test_pure_refusal_records_the_frozen_scope_after_candidate_adoption():
    from materials import Employee
    from review_policy import reviewed_answer

    employee = Employee("course_admin")
    decision = {
        "mode": "refused",
        "fact_ids": [],
        "reason": "凍結個案拒答",
        "subquestions": [
            {
                "quote": "特定投訴個案？",
                "mode": "refused",
                "fact_ids": [],
                "refused_topic": "evaluations",
                "reason": "凍結個案拒答",
            }
        ],
    }
    reviewed_answer(employee, "特定投訴個案？", decision)
    assert employee.refused_topics == {"evaluations"}


def test_refused_complaint_does_not_block_later_anonymous_general_flow():
    from materials import Employee
    from review_policy import reviewed_answer

    employee = Employee("course_admin")
    refused = {
        "mode": "refused",
        "fact_ids": [],
        "reason": "凍結個案拒答",
        "subquestions": [
            {
                "quote": "特定投訴個案？",
                "mode": "refused",
                "fact_ids": [],
                "refused_topic": "evaluations",
                "reason": "凍結個案拒答",
            }
        ],
    }
    reviewed_answer(employee, "特定投訴個案？", refused)
    flow = {
        "mode": "answer",
        "fact_ids": ["sensitive-evaluation"],
        "reason": "可談一般匿名流程",
        "subquestions": [
            {
                "quote": "匿名滿意度表的一般處理流程？",
                "mode": "answer",
                "fact_ids": ["sensitive-evaluation"],
                "reason": "流程可談，拒答仍有效",
            }
        ],
    }
    answer = reviewed_answer(employee, "匿名滿意度表的一般處理流程？", flow)
    assert "匿名滿意度表" in answer
    assert "不要再追那件事" in answer
    assert employee.refused_topics == {"evaluations"}
