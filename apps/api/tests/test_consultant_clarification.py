from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore
from langgraph.types import Command

from app.consultant.graph import build_consultant_graph
from app.consultant.interview import (
    VerifiedConsultantCommit,
    apply_source_correction,
    apply_verified_consultant_commit,
)
from app.consultant.results import (
    AnalysisBasis,
    AttentionChange,
    AttentionOperation,
    ConsultantResult,
    GapReason,
    RequiredClarificationDraft,
    SufficiencyRecommendation,
)
from app.consultant.state import (
    ApprovedJobDocument,
    EmployeeSourceKind,
    InterviewPriority,
    InterviewWorkItem,
    InterviewWorkStatus,
    RequiredClarification,
    SourceReference,
    initial_thread_state,
)


def _config(document_id: UUID) -> dict[str, dict[str, str]]:
    return {"configurable": {"thread_id": str(document_id)}}


def _source_reference(source_id: UUID) -> SourceReference:
    return SourceReference(
        source_id=source_id,
        kind=EmployeeSourceKind.EMPLOYEE_TURN,
        created_at=datetime.now(UTC),
    )


def test_safe_follow_up_preserves_an_unanswered_required_clarification() -> None:
    document_id = uuid4()
    source_id = uuid4()
    work_id = uuid4()
    clarification_id = uuid4()
    request = RequiredClarification(
        clarification_id=clarification_id,
        question="實際由誰建立請購單？",
        reason="兩次回答的責任人不同。",
        current_understanding="可能由本人或主管建立。",
        choices=("由我建立", "由主管建立", "其他"),
        affected_work_ids=(work_id,),
        affected_branch="請購下單／責任歸屬",
        source_ids=(source_id,),
    )
    state = initial_thread_state(document_id)
    state.update(
        {
            "revision": 2,
            "latest_source_id": str(source_id),
            "source_count": 1,
            "interview_work": {
                str(work_id): InterviewWorkItem(
                    work_id=work_id,
                    kind="task_boundary",
                    title="請購責任歸屬",
                    status=InterviewWorkStatus.BLOCKED,
                    priority=InterviewPriority.CONTRADICTION_OR_RESPONSIBILITY,
                    priority_reason="待員工澄清。",
                    blocked_by_decision_ids=(clarification_id,),
                    resume_status=InterviewWorkStatus.ACTIVE,
                    source_ids=(source_id,),
                    last_changed_revision=2,
                ).model_dump(mode="json")
            },
            "required_clarification": request.model_dump(mode="json"),
        }
    )
    basis = AnalysisBasis(
        source_ids=(source_id,),
        skill_ids=("work-discovery",),
    )
    result = ConsultantResult(
        visible_reply="我先整理不受這個衝突影響的其他工作。",
        reply_basis=basis,
        sufficiency=SufficiencyRecommendation(
            currently_enough=False,
            reason="仍有責任歸屬待確認。",
            remaining_gap_reasons=(GapReason.SOURCE_CONTRADICTION,),
            continuing_benefit="澄清後可繼續分析請購分支。",
            basis=basis,
        ),
    )
    now = datetime.now(UTC)

    update = apply_verified_consultant_commit(
        state,
        document_id=document_id,
        revision=3,
        commit=VerifiedConsultantCommit(
            run_id=uuid4(),
            answer_source_id=source_id,
            started_at=now,
            completed_at=now,
            result=result,
        ),
    )

    assert RequiredClarification.model_validate(
        update["required_clarification"]
    ) == request


def test_source_correction_retires_affected_clarification_but_preserves_other_blockers() -> None:
    document_id = uuid4()
    superseded_source_id = uuid4()
    correction_source_id = uuid4()
    work_id = uuid4()
    clarification_id = uuid4()
    unrelated_blocker_id = uuid4()
    request = RequiredClarification(
        clarification_id=clarification_id,
        question="實際由誰建立請購單？",
        reason="舊來源互相衝突。",
        current_understanding="可能由本人或主管建立。",
        choices=("由我建立", "由主管建立", "其他"),
        affected_work_ids=(work_id,),
        affected_branch="請購下單／責任歸屬",
        source_ids=(superseded_source_id,),
    )
    state = initial_thread_state(document_id)
    state.update(
        {
            "revision": 2,
            "latest_source_id": str(superseded_source_id),
            "interview_work": {
                str(work_id): InterviewWorkItem(
                    work_id=work_id,
                    kind="task_boundary",
                    title="請購責任歸屬",
                    status=InterviewWorkStatus.BLOCKED,
                    priority=InterviewPriority.CONTRADICTION_OR_RESPONSIBILITY,
                    priority_reason="待員工澄清。",
                    blocked_by_decision_ids=(
                        clarification_id,
                        unrelated_blocker_id,
                    ),
                    resume_status=InterviewWorkStatus.ACTIVE,
                    source_ids=(superseded_source_id,),
                    last_changed_revision=2,
                ).model_dump(mode="json")
            },
            "required_clarification": request.model_dump(mode="json"),
        }
    )

    update = apply_source_correction(
        state,
        document_id=document_id,
        superseded_source_id=superseded_source_id,
        correction_source_id=correction_source_id,
        revision=3,
    )

    assert "required_clarification" in update
    assert update["required_clarification"] is None
    work = InterviewWorkItem.model_validate(update["interview_work"][str(work_id)])
    assert work.status is InterviewWorkStatus.BLOCKED
    assert work.blocked_by_decision_ids == (unrelated_blocker_id,)


@pytest.mark.asyncio
async def test_required_clarification_survives_restart_and_answer_is_only_evidence() -> None:
    document_id = uuid4()
    discovery_source = uuid4()
    saver = InMemorySaver()
    store = InMemoryStore()
    graph = build_consultant_graph(saver, store)
    await graph.ainvoke(
        {},
        _config(document_id),
        context={"action": "initialize", "document_id": str(document_id)},
    )
    state = await graph.ainvoke(
        {},
        _config(document_id),
        context={
            "action": "register_source",
            "document_id": str(document_id),
            "expected_revision": 0,
            "source_reference": _source_reference(discovery_source).model_dump(mode="json"),
        },
    )
    discovery_basis = AnalysisBasis(
        source_ids=(discovery_source,),
        skill_ids=("story-interview",),
    )
    discovery = ConsultantResult(
        visible_reply="我先記下請購觸發條件這個訪談重點。",
        reply_basis=discovery_basis,
        attention_changes=(
            AttentionChange(
                operation=AttentionOperation.ADD,
                kind="task_boundary",
                title="請購觸發條件",
                reason="這會影響實際責任邊界。",
                missing_before_enough="需由員工確認實際觸發條件。",
                recommended_next_step="詢問最近一次實際情況。",
                priority=InterviewPriority.TASK_BOUNDARY,
                make_current=True,
                basis=discovery_basis,
            ),
        ),
        sufficiency=SufficiencyRecommendation(
            currently_enough=False,
            reason="觸發條件仍待釐清。",
            remaining_gap_reasons=(GapReason.TASK_BOUNDARY_UNCLEAR,),
            continuing_benefit="繼續訪談可確認實際責任。",
            basis=discovery_basis,
        ),
    )
    now = datetime.now(UTC)
    state = await graph.ainvoke(
        {},
        _config(document_id),
        context={
            "action": "commit_consultant_result",
            "document_id": str(document_id),
            "expected_revision": state["revision"],
            "semantic_commit": VerifiedConsultantCommit(
                run_id=uuid4(),
                answer_source_id=discovery_source,
                started_at=now,
                completed_at=now,
                result=discovery,
            ).model_dump(mode="json"),
        },
    )
    work_id = UUID(state["current_work_id"])
    answer_source = uuid4()
    state = await graph.ainvoke(
        {},
        _config(document_id),
        context={
            "action": "register_source",
            "document_id": str(document_id),
            "expected_revision": state["revision"],
            "source_reference": _source_reference(answer_source).model_dump(mode="json"),
        },
    )
    basis = AnalysisBasis(
        source_ids=(answer_source,),
        skill_ids=("story-interview",),
    )
    result = ConsultantResult(
        visible_reply="這兩段說法會改變請購責任邊界，我需要先確認一件事。",
        reply_basis=basis,
        required_clarification=RequiredClarificationDraft(
            reason="兩次回答對請購觸發條件互相衝突",
            question="實際在哪種情況才建立請購單？",
            current_understanding="一段說每天建立，另一段說低於安全庫存才建立。",
            choices=("每天", "低於安全庫存", "其他"),
            affected_work_ids=(work_id,),
            affected_branch="請購下單／觸發條件",
            basis=basis,
        ),
        sufficiency=SufficiencyRecommendation(
            currently_enough=False,
            reason="責任觸發條件仍互相衝突。",
            remaining_gap_reasons=(GapReason.SOURCE_CONTRADICTION,),
            continuing_benefit="確認後才能安全地繼續該工作分支。",
            basis=basis,
        ),
    )
    now = datetime.now(UTC)
    paused = await graph.ainvoke(
        {},
        _config(document_id),
        context={
            "action": "commit_consultant_result",
            "document_id": str(document_id),
            "expected_revision": state["revision"],
            "semantic_commit": VerifiedConsultantCommit(
                run_id=uuid4(),
                answer_source_id=answer_source,
                started_at=now,
                completed_at=now,
                result=result,
            ).model_dump(mode="json"),
        },
    )
    card = paused["__interrupt__"][0].value
    assert card["kind"] == "required_clarification"
    assert card["reason"] == "兩次回答對請購觸發條件互相衝突"
    assert card["current_understanding"].startswith("一段說每天")
    assert card["choices"] == ["每天", "低於安全庫存", "其他"]
    assert card["affected_work_ids"] == [str(work_id)]
    assert card["affected_branch"] == "請購下單／觸發條件"

    checkpoint = await graph.aget_state(_config(document_id))
    approved_before = checkpoint.values["approved_document"]
    assert checkpoint.values["required_clarification"] is not None

    restarted = build_consultant_graph(saver, store)
    direct_edit_source = uuid4()
    edited_document = ApprovedJobDocument.model_validate(approved_before).model_copy(
        update={"job_title": "採購專員"}
    )
    waiting_again = await restarted.ainvoke(
        {},
        _config(document_id),
        context={
            "action": "direct_edit",
            "document_id": str(document_id),
            "expected_revision": checkpoint.values["revision"],
            "source_reference": SourceReference(
                source_id=direct_edit_source,
                kind=EmployeeSourceKind.DIRECT_EDIT,
                created_at=datetime.now(UTC),
            ).model_dump(mode="json"),
            "approved_document": edited_document.model_dump(mode="json"),
        },
    )
    assert waiting_again["__interrupt__"][0].value["request_id"] == card["request_id"]
    checkpoint = await restarted.aget_state(_config(document_id))
    assert checkpoint.values["approved_document"]["job_title"] == "採購專員"
    assert checkpoint.values["required_clarification"] is not None

    safe_source = uuid4()
    still_waiting = await restarted.ainvoke(
        {},
        _config(document_id),
        context={
            "action": "register_source",
            "document_id": str(document_id),
            "expected_revision": checkpoint.values["revision"],
            "source_reference": _source_reference(safe_source).model_dump(mode="json"),
        },
    )
    assert still_waiting["__interrupt__"][0].value["request_id"] == card["request_id"]
    checkpoint = await restarted.aget_state(_config(document_id))
    safe_basis = AnalysisBasis(
        source_ids=(safe_source,),
        skill_ids=("work-discovery",),
    )
    now = datetime.now(UTC)
    safe_result = ConsultantResult(
        visible_reply="我先整理另一項不受此衝突影響的工作。",
        reply_basis=safe_basis,
        sufficiency=SufficiencyRecommendation(
            currently_enough=False,
            reason="請購責任仍待確認。",
            remaining_gap_reasons=(GapReason.SOURCE_CONTRADICTION,),
            continuing_benefit="澄清後可回來處理請購分支。",
            basis=safe_basis,
        ),
    )
    still_waiting = await restarted.ainvoke(
        {},
        _config(document_id),
        context={
            "action": "commit_consultant_result",
            "document_id": str(document_id),
            "expected_revision": checkpoint.values["revision"],
            "semantic_commit": VerifiedConsultantCommit(
                run_id=uuid4(),
                answer_source_id=safe_source,
                started_at=now,
                completed_at=now,
                result=safe_result,
            ).model_dump(mode="json"),
        },
    )
    assert still_waiting["__interrupt__"][0].value["request_id"] == card["request_id"]

    clarification_source = uuid4()
    resumed = await restarted.ainvoke(
        Command(
            resume={
                "text": "低於安全庫存時才由我建立請購單。",
                "source_reference": _source_reference(
                    clarification_source
                ).model_dump(mode="json"),
            }
        ),
        _config(document_id),
    )
    assert resumed["required_clarification"] is None
    assert resumed["latest_source_id"] == str(clarification_source)
    assert resumed["source_count"] == 5
    assert resumed["approved_document"]["job_title"] == "採購專員"
    assert resumed["interview_work"][str(work_id)]["status"] in {
        "active",
        "available",
    }


@pytest.mark.asyncio
async def test_clarification_answer_cannot_smuggle_document_acceptance() -> None:
    document_id = uuid4()
    source_id = uuid4()
    saver = InMemorySaver()
    store = InMemoryStore()
    graph = build_consultant_graph(saver, store)
    await graph.ainvoke(
        {},
        _config(document_id),
        context={"action": "initialize", "document_id": str(document_id)},
    )
    # The resume payload is validated by an extra-forbid typed command.  A document
    # decision in this channel must fail rather than being interpreted as authority.
    from app.consultant.clarification import ClarificationAnswer

    with pytest.raises(ValueError):
        ClarificationAnswer.model_validate(
            {
                "text": "由我負責。",
                "source_reference": _source_reference(source_id).model_dump(mode="json"),
                "accept_changeset_id": str(uuid4()),
            }
        )
