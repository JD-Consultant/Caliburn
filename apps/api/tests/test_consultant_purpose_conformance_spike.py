from __future__ import annotations

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from consultant_purpose_conformance_spike import build_consultant_purpose_graph


def _config(thread_id: str) -> dict[str, dict[str, str]]:
    return {"configurable": {"thread_id": thread_id}}


def _units() -> list[dict[str, object]]:
    return [
        {"id": "ordering", "title": "請購下單", "status": "active", "order": 1},
        {
            "id": "shortage",
            "title": "缺料協調",
            "status": "pending",
            "order": 2,
        },
        {
            "id": "supplier",
            "title": "供應商績效",
            "status": "pending",
            "order": 3,
        },
    ]


@pytest.mark.asyncio
async def test_dynamic_control_keeps_gaps_visible_and_reopens_corrected_unit() -> None:
    graph = build_consultant_purpose_graph(InMemorySaver())
    config = _config("dynamic-control")
    await graph.ainvoke(
        {"command": {"kind": "seed", "interview_units": _units()}}, config
    )

    with_gap = await graph.ainvoke(
        {
            "command": {
                "kind": "discover_issue",
                "issue": {
                    "id": "gap-inventory-report",
                    "summary": "庫存報表尚未分析",
                    "reason": "side_clue",
                    "status": "open",
                },
            }
        },
        config,
    )
    assert with_gap["active_unit_id"] == "ordering"
    assert with_gap["issue_queue"]["gap-inventory-report"]["status"] == "open"

    after_defer = await graph.ainvoke(
        {
            "command": {
                "kind": "defer_unit",
                "unit_id": "ordering",
                "reason": "先釐清缺料處理",
            }
        },
        config,
    )
    assert after_defer["active_unit_id"] == "shortage"
    assert after_defer["interview_units"]["ordering"]["status"] == "deferred"

    returned = await graph.ainvoke(
        {"command": {"kind": "complete_unit", "unit_id": "shortage"}}, config
    )
    assert returned["active_unit_id"] == "ordering"
    assert returned["interview_units"]["ordering"]["status"] == "active"

    moved_on = await graph.ainvoke(
        {"command": {"kind": "complete_unit", "unit_id": "ordering"}}, config
    )
    assert moved_on["active_unit_id"] == "supplier"

    reopened = await graph.ainvoke(
        {
            "command": {
                "kind": "correct_source",
                "source_id": "answer-ordering",
                "correction_id": "correction-ordering",
                "text": "請購不是每天執行，只有低於安全庫存時才做。",
                "affected_unit_ids": ["ordering"],
            }
        },
        config,
    )
    assert reopened["active_unit_id"] == "ordering"
    assert reopened["interview_units"]["ordering"]["status"] == "reopened"
    assert reopened["interview_units"]["shortage"]["status"] == "completed"
    assert reopened["issue_queue"]["gap-inventory-report"]["status"] == "open"
    assert "percent_complete" not in reopened


@pytest.mark.asyncio
async def test_correction_challenges_only_source_dependent_understanding() -> None:
    graph = build_consultant_purpose_graph(InMemorySaver())
    config = _config("source-correction")
    await graph.ainvoke(
        {
            "command": {
                "kind": "seed",
                "interview_units": _units(),
                "employee_evidence": {
                    "answer-ordering": {
                        "text": "我每天建立請購單。",
                        "speaker": "employee",
                    },
                    "answer-shortage": {
                        "text": "缺料時我通知生管。",
                        "speaker": "employee",
                    },
                },
                "evolving_understanding": {
                    "claim-ordering": {
                        "text": "員工每天建立請購單",
                        "status": "active",
                        "depends_on_source_ids": ["answer-ordering"],
                        "unit_id": "ordering",
                        "quote_anchor": {
                            "source_id": "answer-ordering",
                            "start": 0,
                            "end": 9,
                        },
                    },
                    "claim-shortage": {
                        "text": "員工負責缺料通知",
                        "status": "active",
                        "depends_on_source_ids": ["answer-shortage"],
                        "unit_id": "shortage",
                        "quote_anchor": {
                            "source_id": "answer-shortage",
                            "start": 0,
                            "end": 8,
                        },
                    },
                },
            }
        },
        config,
    )

    corrected = await graph.ainvoke(
        {
            "command": {
                "kind": "correct_source",
                "source_id": "answer-ordering",
                "correction_id": "correction-ordering",
                "text": "只有低於安全庫存時才建立請購單。",
                "affected_unit_ids": ["ordering"],
            }
        },
        config,
    )

    assert corrected["evolving_understanding"]["claim-ordering"]["status"] == "challenged"
    assert corrected["evolving_understanding"]["claim-shortage"]["status"] == "active"
    assert corrected["employee_evidence"]["answer-ordering"]["text"] == "我每天建立請購單。"
    assert corrected["employee_evidence"]["correction-ordering"] == {
        "text": "只有低於安全庫存時才建立請購單。",
        "speaker": "employee",
        "supersedes": "answer-ordering",
    }
    assert corrected["evolving_understanding"]["claim-ordering"]["quote_anchor"] == {
        "source_id": "answer-ordering",
        "start": 0,
        "end": 9,
    }
    assert corrected["active_unit_id"] == "ordering"


@pytest.mark.asyncio
async def test_review_queue_allows_defer_continue_edit_and_out_of_order_acceptance() -> None:
    graph = build_consultant_purpose_graph(InMemorySaver())
    config = _config("review-queue")
    await graph.ainvoke(
        {
            "command": {
                "kind": "seed",
                "interview_units": _units(),
                "approved_artifact": {
                    "tasks": {
                        "task-a": {"statement": "舊任務 A"},
                        "task-b": {"statement": "舊任務 B"},
                    }
                },
            }
        },
        config,
    )
    patch_a = {
        "id": "patch-a",
        "status": "pending",
        "operations": [
            {
                "path": ["tasks", "task-a", "statement"],
                "before": "舊任務 A",
                "after": "AI 建議 A",
            }
        ],
    }
    patch_b = {
        "id": "patch-b",
        "status": "pending",
        "operations": [
            {
                "path": ["tasks", "task-b", "statement"],
                "before": "舊任務 B",
                "after": "AI 建議 B",
            }
        ],
    }
    await graph.ainvoke(
        {"command": {"kind": "add_review", "review": patch_a}}, config
    )
    two_pending = await graph.ainvoke(
        {"command": {"kind": "add_review", "review": patch_b}}, config
    )
    assert set(two_pending["review_queue"]) == {"patch-a", "patch-b"}

    await graph.ainvoke(
        {
            "command": {
                "kind": "decide_review",
                "review_id": "patch-a",
                "decision": "defer",
            }
        },
        config,
    )
    continued = await graph.ainvoke(
        {
            "command": {
                "kind": "discover_issue",
                "issue": {
                    "id": "gap-supplier-rating",
                    "summary": "績效評分依據待釐清",
                    "reason": "missing_evidence",
                    "status": "open",
                },
            }
        },
        config,
    )
    assert continued["review_queue"]["patch-a"]["status"] == "deferred"
    assert continued["active_unit_id"] == "ordering"

    accepted_b = await graph.ainvoke(
        {
            "command": {
                "kind": "decide_review",
                "review_id": "patch-b",
                "decision": "accept",
            }
        },
        config,
    )
    assert accepted_b["approved_artifact"]["tasks"]["task-b"]["statement"] == "AI 建議 B"
    assert accepted_b["review_queue"]["patch-a"]["status"] == "deferred"

    accepted_a = await graph.ainvoke(
        {
            "command": {
                "kind": "decide_review",
                "review_id": "patch-a",
                "decision": "edit_accept",
                "edited_operations": [
                    {
                        "path": ["tasks", "task-a", "statement"],
                        "before": "舊任務 A",
                        "after": "員工修訂 A",
                    }
                ],
            }
        },
        config,
    )
    assert accepted_a["approved_artifact"]["tasks"]["task-a"]["statement"] == "員工修訂 A"
    assert accepted_a["review_queue"]["patch-a"]["status"] == "accepted"

    await graph.ainvoke(
        {
            "command": {
                "kind": "add_review",
                "review": {
                    "id": "patch-stale",
                    "status": "pending",
                    "operations": [
                        {
                            "path": ["tasks", "task-a", "statement"],
                            "before": "員工修訂 A",
                            "after": "過時的 AI 建議",
                        }
                    ],
                },
            }
        },
        config,
    )
    await graph.ainvoke(
        {
            "command": {
                "kind": "direct_edit",
                "operations": [
                    {
                        "path": ["tasks", "task-a", "statement"],
                        "before": "員工修訂 A",
                        "after": "員工後續直接修改",
                    }
                ],
            }
        },
        config,
    )
    stale = await graph.ainvoke(
        {
            "command": {
                "kind": "decide_review",
                "review_id": "patch-stale",
                "decision": "accept",
            }
        },
        config,
    )
    assert stale["review_queue"]["patch-stale"]["status"] == "stale"
    assert stale["approved_artifact"]["tasks"]["task-a"]["statement"] == "員工後續直接修改"


@pytest.mark.asyncio
async def test_required_clarification_resumes_as_employee_evidence_not_document_acceptance() -> None:
    saver = InMemorySaver()
    graph = build_consultant_purpose_graph(saver)
    config = _config("required-clarification")
    approved = {"tasks": {"task-a": {"statement": "建立請購單"}}}
    pending_review = {
        "patch-a": {
            "id": "patch-a",
            "status": "pending",
            "operations": [],
        }
    }
    await graph.ainvoke(
        {
            "command": {
                "kind": "seed",
                "interview_units": [
                    {"id": "ordering", "title": "請購下單", "status": "active", "order": 1}
                ],
                "approved_artifact": approved,
                "review_queue": pending_review,
            }
        },
        config,
    )
    paused = await graph.ainvoke(
        {
            "command": {
                "kind": "require_clarification",
                "request": {
                    "id": "clarify-trigger",
                    "reason": "兩次回答對請購觸發條件互相衝突",
                    "question": "實際在哪種情況才建立請購單？",
                    "choices": ["每天", "低於安全庫存", "其他"],
                    "affected_unit_id": "ordering",
                    "affected_branch": "ordering.trigger",
                },
            }
        },
        config,
    )
    card = paused["__interrupt__"][0].value
    assert card == {
        "kind": "required_clarification",
        "request_id": "clarify-trigger",
        "reason": "兩次回答對請購觸發條件互相衝突",
        "question": "實際在哪種情況才建立請購單？",
        "choices": ["每天", "低於安全庫存", "其他"],
        "affected_unit_id": "ordering",
        "affected_branch": "ordering.trigger",
    }

    restarted = build_consultant_purpose_graph(saver)
    resumed = await restarted.ainvoke(
        Command(
            resume={
                "choice": "低於安全庫存",
                "text": "低於安全庫存才建立請購單。",
            }
        ),
        config,
    )
    assert resumed["employee_evidence"]["clarify-trigger"] == {
        "speaker": "employee",
        "choice": "低於安全庫存",
        "text": "低於安全庫存才建立請購單。",
        "reason": "required_clarification",
    }
    assert resumed["required_inputs"]["clarify-trigger"]["status"] == "resolved"
    assert resumed["interview_units"]["ordering"]["status"] == "reopened"
    assert resumed["approved_artifact"] == approved
    assert resumed["review_queue"] == pending_review
