from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore

from app.consultant.graph import build_consultant_graph
from app.consultant.interview import VerifiedConsultantCommit
from app.consultant.results import (
    AnalysisBasis,
    AttentionChange,
    AttentionOperation,
    ConsultantResult,
    GapReason,
    NextQuestion,
    SufficiencyRecommendation,
    UnderstandingChange,
    UnderstandingOperation,
    VisibleGap,
)
from app.consultant.state import (
    EmployeeSourceKind,
    InterviewPriority,
    InterviewWorkStatus,
    SourceReference,
    UnderstandingImpact,
    UnderstandingStatus,
)


def _config(document_id: UUID) -> dict[str, dict[str, str]]:
    return {"configurable": {"thread_id": str(document_id)}}


def _basis(source_id: UUID, *skills: str) -> AnalysisBasis:
    return AnalysisBasis(
        source_ids=(source_id,),
        skill_ids=skills or ("work-discovery",),
    )


def _not_enough(source_id: UUID, *skills: str) -> SufficiencyRecommendation:
    return SufficiencyRecommendation(
        currently_enough=False,
        reason="仍有具體工作缺口要釐清。",
        remaining_gap_reasons=(GapReason.WORK_COVERAGE_MISSING,),
        continuing_benefit="繼續訪談可補齊尚未深入的工作範圍。",
        basis=_basis(source_id, *(skills or ("work-discovery",))),
    )


async def _initialize(document_id: UUID):
    saver = InMemorySaver()
    store = InMemoryStore()
    graph = build_consultant_graph(saver, store)
    await graph.ainvoke(
        {},
        _config(document_id),
        context={"action": "initialize", "document_id": str(document_id)},
    )
    return graph, saver, store


async def _register_source(
    graph,
    document_id: UUID,
    *,
    revision: int,
    source_id: UUID,
    supersedes_source_id: UUID | None = None,
):
    reference = SourceReference(
        source_id=source_id,
        kind=EmployeeSourceKind.EMPLOYEE_TURN,
        created_at=datetime.now(UTC),
        supersedes_source_id=supersedes_source_id,
    )
    return await graph.ainvoke(
        {},
        _config(document_id),
        context={
            "action": "register_source",
            "document_id": str(document_id),
            "expected_revision": revision,
            "source_reference": reference.model_dump(mode="json"),
        },
    )


async def _commit(
    graph,
    document_id: UUID,
    *,
    revision: int,
    source_id: UUID,
    result: ConsultantResult,
    returning_after_long_gap: bool = False,
):
    now = datetime.now(UTC)
    commit = VerifiedConsultantCommit(
        run_id=uuid4(),
        answer_source_id=source_id,
        started_at=now,
        completed_at=now,
        returning_after_long_gap=returning_after_long_gap,
        result=result,
    )
    return await graph.ainvoke(
        {},
        _config(document_id),
        context={
            "action": "commit_consultant_result",
            "document_id": str(document_id),
            "expected_revision": revision,
            "semantic_commit": commit.model_dump(mode="json"),
        },
    )


@pytest.mark.asyncio
async def test_procurement_interview_keeps_one_focus_and_reopens_only_corrected_work() -> None:
    document_id = uuid4()
    first_source = uuid4()
    second_source = uuid4()
    correction_source = uuid4()
    graph, saver, store = await _initialize(document_id)

    state = await _register_source(
        graph,
        document_id,
        revision=0,
        source_id=first_source,
    )
    broad_map = ConsultantResult(
        visible_reply=(
            "我先整理出請購下單與供應商績效兩塊；現在先釐清請購下單，"
            "供應商績效會保留，稍後再回來。"
        ),
        reply_basis=_basis(first_source, "work-discovery"),
        understanding_changes=(
            UnderstandingChange(
                operation=UnderstandingOperation.ADD,
                kind="task_hypothesis",
                text="員工檢查庫存後建立請購單。",
                basis=_basis(first_source, "work-discovery"),
            ),
        ),
        attention_changes=(
            AttentionChange(
                operation=AttentionOperation.ADD,
                kind="task_boundary",
                title="請購下單",
                reason="這是目前最清楚且可深入的工作故事。",
                missing_before_enough="需釐清觸發條件、本人責任與完成結果。",
                recommended_next_step="從最近一次請購故事開始。",
                priority=InterviewPriority.TASK_BOUNDARY,
                make_current=True,
                basis=_basis(first_source, "work-discovery"),
            ),
            AttentionChange(
                operation=AttentionOperation.ADD,
                kind="work_clue",
                title="供應商績效",
                reason="完整回答中出現的獨立旁支線索。",
                disposition=InterviewWorkStatus.PARKED,
                priority=InterviewPriority.COVERAGE,
                basis=_basis(first_source, "work-discovery"),
            ),
        ),
        gaps=(
            VisibleGap(
                reason=GapReason.WORK_COVERAGE_MISSING,
                description="供應商績效的實際工作尚未深入。",
                subject_kind="work_clue",
                basis=_basis(first_source, "work-discovery"),
            ),
        ),
        next_question=NextQuestion(
            text="最近一次建立請購單時，什麼情況觸發你開始處理？",
            answer_target="請購下單的觸發條件",
            reason="先確認 Task 邊界。",
            basis=_basis(first_source, "work-discovery"),
        ),
        sufficiency=_not_enough(first_source),
    )
    state = await _commit(
        graph,
        document_id,
        revision=state["revision"],
        source_id=first_source,
        result=broad_map,
    )

    work_by_title = {
        item["title"]: item for item in state["interview_work"].values()
    }
    ordering_id = UUID(work_by_title["請購下單"]["work_id"])
    supplier_id = UUID(work_by_title["供應商績效"]["work_id"])
    task_understanding = next(
        item
        for item in state["understanding"].values()
        if item["kind"] == "task_hypothesis"
        and item["superseded_by_version_id"] is None
    )
    assert state["current_work_id"] == str(ordering_id)
    assert work_by_title["請購下單"]["status"] == "active"
    assert work_by_title["供應商績效"]["status"] == "parked"
    assert len(state["messages"]) == 1
    assert state["approved_document"]["tasks"] == []

    state = await _register_source(
        graph,
        document_id,
        revision=state["revision"],
        source_id=second_source,
    )
    dynamic_revision = ConsultantResult(
        visible_reply=(
            "先依你的要求改談供應商績效；同時我把請購下單的 Task 理解修正，"
            "並保留新的 Duty、Output 與 Knowledge 候選。"
        ),
        reply_basis=_basis(
            second_source,
            "work-discovery",
            "task-boundary",
            "duty-grouping",
            "output",
            "knowledge",
        ),
        understanding_changes=(
            UnderstandingChange(
                operation=UnderstandingOperation.REVISE,
                understanding_id=UUID(task_understanding["understanding_id"]),
                kind="task_hypothesis",
                text="員工在低於安全庫存時建立請購單並送主管核准。",
                impact=UnderstandingImpact.MEANINGFUL_SHIFT,
                work_ids=(ordering_id,),
                basis=_basis(second_source, "task-boundary"),
            ),
            UnderstandingChange(
                operation=UnderstandingOperation.ADD,
                kind="duty_hypothesis",
                text="物料供應與採購協調。",
                work_ids=(ordering_id,),
                basis=_basis(second_source, "duty-grouping"),
            ),
            UnderstandingChange(
                operation=UnderstandingOperation.ADD,
                kind="output_candidate",
                text="已送核的請購單。",
                work_ids=(ordering_id,),
                basis=_basis(second_source, "output"),
            ),
            UnderstandingChange(
                operation=UnderstandingOperation.ADD,
                kind="knowledge_candidate",
                text="安全庫存與請購核准規則。",
                work_ids=(ordering_id,),
                basis=_basis(second_source, "knowledge"),
            ),
        ),
        attention_changes=(
            AttentionChange(
                operation=AttentionOperation.PARK,
                attention_id=ordering_id,
                kind="task_boundary",
                title="請購下單",
                reason="員工要求先改談供應商績效。",
                basis=_basis(second_source, "task-boundary"),
            ),
            AttentionChange(
                operation=AttentionOperation.REVISE,
                attention_id=supplier_id,
                kind="work_clue",
                title="供應商績效",
                reason="員工主動改變當前主題。",
                priority=InterviewPriority.EMPLOYEE_REQUEST,
                make_current=True,
                basis=_basis(second_source, "work-discovery"),
            ),
        ),
        gaps=(
            VisibleGap(
                reason=GapReason.PERFORMANCE_EVIDENCE_MISSING,
                description="供應商績效的觀察方式尚未說明。",
                subject_kind="work_clue",
                subject_id=supplier_id,
                basis=_basis(second_source, "output"),
            ),
        ),
        next_question=NextQuestion(
            text="你實際怎麼追蹤或判斷供應商績效？",
            answer_target="供應商績效工作故事",
            reason="尊重員工改談的主題。",
            basis=_basis(second_source, "work-discovery"),
        ),
        sufficiency=_not_enough(second_source, "work-discovery"),
    )
    state = await _commit(
        graph,
        document_id,
        revision=state["revision"],
        source_id=second_source,
        result=dynamic_revision,
    )
    current_understanding_kinds = {
        item["kind"]
        for item in state["understanding"].values()
        if item["superseded_by_version_id"] is None
        and item["status"] != "retired"
    }
    assert state["current_work_id"] == str(supplier_id)
    assert {
        "task_hypothesis",
        "duty_hypothesis",
        "output_candidate",
        "knowledge_candidate",
    } <= current_understanding_kinds

    corrected = await _register_source(
        graph,
        document_id,
        revision=state["revision"],
        source_id=correction_source,
        supersedes_source_id=second_source,
    )
    current_items = [
        item
        for item in corrected["understanding"].values()
        if item["superseded_by_version_id"] is None
    ]
    challenged = {item["kind"] for item in current_items if item["status"] == "challenged"}
    assert {
        "task_hypothesis",
        "duty_hypothesis",
        "output_candidate",
        "knowledge_candidate",
    } <= challenged
    assert corrected["current_work_id"] in {str(ordering_id), str(supplier_id)}
    assert any(
        item["reason"] == GapReason.WORK_COVERAGE_MISSING.value
        and item["status"] == "active"
        for item in corrected["gaps"].values()
    )

    reopened_graph = build_consultant_graph(saver, store)
    reopened = await reopened_graph.aget_state(_config(document_id))
    assert reopened.values["revision"] == corrected["revision"]
    assert reopened.values["current_work_id"] == corrected["current_work_id"]
    serialized = str(reopened.values).lower()
    assert "pause" not in serialized
    assert "finish_interview" not in serialized


@pytest.mark.asyncio
async def test_source_correction_only_challenges_dependent_understanding() -> None:
    document_id = uuid4()
    ordering_source = uuid4()
    shortage_source = uuid4()
    correction_source = uuid4()
    graph, _, _ = await _initialize(document_id)
    state = await _register_source(
        graph,
        document_id,
        revision=0,
        source_id=ordering_source,
    )
    state = await _register_source(
        graph,
        document_id,
        revision=state["revision"],
        source_id=shortage_source,
    )
    result = ConsultantResult(
        visible_reply="我先保留兩項工作理解。",
        reply_basis=_basis(shortage_source, "work-discovery"),
        understanding_changes=(
            UnderstandingChange(
                operation=UnderstandingOperation.ADD,
                kind="task_hypothesis",
                text="員工建立請購單。",
                basis=_basis(ordering_source, "work-discovery"),
            ),
            UnderstandingChange(
                operation=UnderstandingOperation.ADD,
                kind="task_hypothesis",
                text="員工通知生管缺料。",
                basis=_basis(shortage_source, "work-discovery"),
            ),
        ),
        attention_changes=(
            AttentionChange(
                operation=AttentionOperation.ADD,
                kind="task_boundary",
                title="請購下單",
                reason="先釐清請購工作。",
                make_current=True,
                basis=_basis(ordering_source, "work-discovery"),
            ),
            AttentionChange(
                operation=AttentionOperation.ADD,
                kind="task_boundary",
                title="缺料通知",
                reason="另一項已知工作。",
                basis=_basis(shortage_source, "work-discovery"),
            ),
        ),
        sufficiency=_not_enough(shortage_source),
    )
    state = await _commit(
        graph,
        document_id,
        revision=state["revision"],
        source_id=shortage_source,
        result=result,
    )
    corrected = await _register_source(
        graph,
        document_id,
        revision=state["revision"],
        source_id=correction_source,
        supersedes_source_id=ordering_source,
    )
    current = [
        item
        for item in corrected["understanding"].values()
        if item["superseded_by_version_id"] is None
    ]
    ordering = next(item for item in current if "請購單" in item["text"])
    shortage = next(item for item in current if "缺料" in item["text"])
    ordering_work = next(
        item
        for item in corrected["interview_work"].values()
        if item["title"] == "請購下單"
    )
    shortage_work = next(
        item
        for item in corrected["interview_work"].values()
        if item["title"] == "缺料通知"
    )
    assert ordering["status"] == UnderstandingStatus.CHALLENGED.value
    assert shortage["status"] == UnderstandingStatus.ACTIVE.value
    assert ordering_work["priority"] == InterviewPriority.CORRECTION.value
    assert ordering_work["status"] == InterviewWorkStatus.ACTIVE.value
    assert shortage_work["priority"] != InterviewPriority.CORRECTION.value


@pytest.mark.asyncio
async def test_semantic_commit_applies_source_correction_with_verified_result_once() -> None:
    document_id = uuid4()
    original_source = uuid4()
    current_source = uuid4()
    graph, _, _ = await _initialize(document_id)

    state = await _register_source(
        graph,
        document_id,
        revision=0,
        source_id=original_source,
    )
    first_result = ConsultantResult(
        visible_reply="我先記下這項工作理解。",
        reply_basis=_basis(original_source),
        understanding_changes=(
            UnderstandingChange(
                operation=UnderstandingOperation.ADD,
                kind="task_hypothesis",
                text="員工整理採購需求。",
                basis=_basis(original_source),
            ),
        ),
        sufficiency=_not_enough(original_source),
    )
    state = await _commit(
        graph,
        document_id,
        revision=state["revision"],
        source_id=original_source,
        result=first_result,
    )
    state = await _register_source(
        graph,
        document_id,
        revision=state["revision"],
        source_id=current_source,
    )
    correction_result = ConsultantResult.model_validate(
        {
            **ConsultantResult(
                visible_reply="我已依你剛才的更正重新檢查受影響理解。",
                reply_basis=_basis(current_source),
                sufficiency=_not_enough(current_source),
            ).model_dump(mode="json"),
            "source_supersession": {
                "superseded_source_id": str(original_source),
            },
        }
    )

    corrected = await _commit(
        graph,
        document_id,
        revision=state["revision"],
        source_id=current_source,
        result=correction_result,
    )

    assert corrected["source_count"] == 2
    assert corrected["source_supersessions"] == {
        str(original_source): str(current_source)
    }
    assert corrected["messages"][-1].content == (
        "我已依你剛才的更正重新檢查受影響理解。"
    )
    understanding = tuple(corrected["understanding"].values())
    assert len(understanding) == 2
    assert {item["status"] for item in understanding} == {
        UnderstandingStatus.SUPERSEDED.value,
        UnderstandingStatus.CHALLENGED.value,
    }
