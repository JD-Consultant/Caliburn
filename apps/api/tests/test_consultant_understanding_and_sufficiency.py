from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore

from app.consultant.graph import build_consultant_graph
from app.consultant.document_review import create_document_changeset
from app.consultant.interview import (
    VerifiedConsultantCommit,
    apply_verified_consultant_commit,
)
from app.consultant.results import (
    AnalysisBasis,
    AttentionChange,
    AttentionOperation,
    ConsultantResult,
    DocumentChangeOperation,
    GapReason,
    ReviewableDocumentChange,
    SufficiencyRecommendation,
    UnderstandingChange,
    UnderstandingOperation,
    VisibleGap,
)
from app.consultant.state import (
    CalibrationDecision,
    ApprovedJobDocument,
    EmployeeSourceKind,
    InterviewPriority,
    InterviewWorkStatus,
    SourceReference,
    UnderstandingImpact,
)
from app.consultant.views import snapshot_from_state


def _config(document_id: UUID) -> dict[str, dict[str, str]]:
    return {"configurable": {"thread_id": str(document_id)}}


def _basis(source_id: UUID, skill: str = "work-discovery") -> AnalysisBasis:
    return AnalysisBasis(source_ids=(source_id,), skill_ids=(skill,))


async def _graph_with_source(document_id: UUID, source_id: UUID):
    saver = InMemorySaver()
    store = InMemoryStore()
    graph = build_consultant_graph(saver, store)
    await graph.ainvoke(
        {},
        _config(document_id),
        context={"action": "initialize", "document_id": str(document_id)},
    )
    reference = SourceReference(
        source_id=source_id,
        kind=EmployeeSourceKind.EMPLOYEE_TURN,
        created_at=datetime.now(UTC),
    )
    state = await graph.ainvoke(
        {},
        _config(document_id),
        context={
            "action": "register_source",
            "document_id": str(document_id),
            "expected_revision": 0,
            "source_reference": reference.model_dump(mode="json"),
        },
    )
    return graph, saver, store, state


async def _commit(
    graph,
    document_id: UUID,
    revision: int,
    source_id: UUID,
    result: ConsultantResult,
    *,
    returning_after_long_gap: bool = False,
    published_changeset=None,
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
    if published_changeset is None:
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
    state = (await graph.aget_state(_config(document_id))).values
    updated = apply_verified_consultant_commit(
        state,
        document_id=document_id,
        revision=revision + 1,
        commit=commit,
        published_changeset=published_changeset,
    )
    await graph.aupdate_state(_config(document_id), updated)
    return (await graph.aget_state(_config(document_id))).values


def _result_with_understanding(
    source_id: UUID,
    *,
    impact: UnderstandingImpact,
    enough: bool = False,
) -> ConsultantResult:
    remaining = () if enough else (GapReason.WORK_COVERAGE_MISSING,)
    return ConsultantResult(
        visible_reply="我目前理解你會依缺料狀況建立請購單。",
        reply_basis=_basis(source_id),
        used_skill_ids=("work-discovery",),
        understanding_changes=(
            UnderstandingChange(
                operation=UnderstandingOperation.ADD,
                kind="current_responsibility",
                text="員工依缺料狀況建立請購單。",
                impact=impact,
                basis=_basis(source_id),
            ),
        ),
        attention_changes=(
            AttentionChange(
                operation=AttentionOperation.ADD,
                kind="task_boundary",
                title="請購下單",
                reason="先釐清本人責任與完成結果。",
                missing_before_enough="缺少主管核准邊界。",
                recommended_next_step="詢問最近一次請購故事。",
                priority=InterviewPriority.CONTRADICTION_OR_RESPONSIBILITY,
                disposition=(
                    InterviewWorkStatus.SUFFICIENT_FOR_NOW
                    if enough
                    else InterviewWorkStatus.AVAILABLE
                ),
                make_current=not enough,
                basis=_basis(source_id),
            ),
        ),
        gaps=(
            ()
            if enough
            else (
                VisibleGap(
                    reason=GapReason.WORK_COVERAGE_MISSING,
                    description="其他例行工作尚未盤點。",
                    subject_kind="job",
                    basis=_basis(source_id),
                ),
            )
        ),
        sufficiency=SufficiencyRecommendation(
            currently_enough=enough,
            reason=(
                "主要工作已具本人責任、結果與完成判準。"
                if enough
                else "仍有例行工作尚未盤點。"
            ),
            remaining_gap_reasons=remaining,
            continuing_benefit=(
                "繼續訪談最可能補強低頻例外。"
                if enough
                else "繼續盤點可避免漏掉例行工作。"
            ),
            basis=_basis(source_id),
        ),
    )


@pytest.mark.asyncio
async def test_understanding_is_always_visible_and_calibration_is_triggered_by_impact() -> None:
    document_id = uuid4()
    source_id = uuid4()
    graph, _, _, state = await _graph_with_source(document_id, source_id)
    state = await _commit(
        graph,
        document_id,
        state["revision"],
        source_id,
        _result_with_understanding(
            source_id,
            impact=UnderstandingImpact.MEANINGFUL_SHIFT,
        ),
    )
    snapshot = snapshot_from_state(state)

    assert snapshot.understanding_projection.label == "AI 目前理解"
    assert snapshot.understanding_projection.collapsible is True
    assert snapshot.understanding_projection.items
    assert snapshot.understanding_projection.calibration is not None
    assert snapshot.understanding_projection.calibration.kind == "soft"
    assert snapshot.understanding_projection.calibration.allowed_actions == (
        "confirm",
        "direct_correction",
        "later",
    )

    calibration_id = snapshot.understanding_projection.calibration.calibration_id
    before_document = state["approved_document"]
    confirmation_source = SourceReference(
        source_id=uuid4(),
        kind=EmployeeSourceKind.EMPLOYEE_TURN,
        created_at=datetime.now(UTC),
    )
    confirmed = await graph.ainvoke(
        {},
        _config(document_id),
        context={
            "action": "decide_understanding_calibration",
            "document_id": str(document_id),
            "expected_revision": state["revision"],
            "calibration_id": str(calibration_id),
            "calibration_decision": CalibrationDecision.CONFIRM.value,
            "source_reference": confirmation_source.model_dump(mode="json"),
        },
    )
    assert confirmed["approved_document"] == before_document
    assert confirmed["review_queue"] == state["review_queue"]
    assert any(
        item["status"] == "employee_confirmed"
        for item in confirmed["understanding"].values()
        if item["superseded_by_version_id"] is None
    )
    assert any(
        str(confirmation_source.source_id) in item["source_ids"]
        for item in confirmed["understanding"].values()
        if item["superseded_by_version_id"] is None
    )


@pytest.mark.asyncio
async def test_blocking_calibration_blocks_only_dependent_branch_and_later_is_not_finish() -> None:
    document_id = uuid4()
    source_id = uuid4()
    graph, _, _, state = await _graph_with_source(document_id, source_id)
    first = _result_with_understanding(
        source_id,
        impact=UnderstandingImpact.ROUTINE,
    )
    first = first.model_copy(
        update={
            "attention_changes": (
                *first.attention_changes,
                AttentionChange(
                    operation=AttentionOperation.ADD,
                    kind="work_clue",
                    title="供應商績效",
                    reason="另一項可獨立訪談的工作。",
                    priority=InterviewPriority.COVERAGE,
                    basis=_basis(source_id),
                ),
            )
        }
    )
    state = await _commit(
        graph,
        document_id,
        state["revision"],
        source_id,
        first,
    )
    ordering = next(
        item for item in state["interview_work"].values() if item["title"] == "請購下單"
    )
    active_understanding = next(
        item
        for item in state["understanding"].values()
        if item["superseded_by_version_id"] is None
    )
    structural = ConsultantResult(
        visible_reply="主管核准邊界會影響請購 Task 的責任描述，先請你確認。",
        reply_basis=_basis(source_id),
        used_skill_ids=("work-discovery",),
        understanding_changes=(
            UnderstandingChange(
                operation=UnderstandingOperation.REVISE,
                understanding_id=UUID(active_understanding["understanding_id"]),
                kind="current_responsibility",
                text="員工提出請購建議，主管決定是否核准。",
                impact=UnderstandingImpact.STRUCTURAL_PREMISE,
                work_ids=(UUID(ordering["work_id"]),),
                basis=_basis(source_id),
            ),
        ),
        sufficiency=SufficiencyRecommendation(
            currently_enough=False,
            reason="責任邊界尚未由員工校準。",
            remaining_gap_reasons=(GapReason.CURRENT_RESPONSIBILITY_UNCLEAR,),
            continuing_benefit="確認後才能可靠描述請購 Task。",
            basis=_basis(source_id),
        ),
    )
    state = await _commit(
        graph,
        document_id,
        state["revision"],
        source_id,
        structural,
    )
    snapshot = snapshot_from_state(state)
    calibration = snapshot.understanding_projection.calibration
    assert calibration is not None
    assert calibration.kind == "branch_blocking"
    assert state["interview_work"][str(ordering["work_id"])]["status"] == "blocked"
    supplier = next(
        item for item in state["interview_work"].values() if item["title"] == "供應商績效"
    )
    assert supplier["status"] != "blocked"

    later = await graph.ainvoke(
        {},
        _config(document_id),
        context={
            "action": "decide_understanding_calibration",
            "document_id": str(document_id),
            "expected_revision": state["revision"],
            "calibration_id": str(calibration.calibration_id),
            "calibration_decision": CalibrationDecision.LATER.value,
            "source_reference": None,
        },
    )
    assert later["interview_work"][str(ordering["work_id"])]["status"] == "blocked"
    assert later["understanding_calibrations"][str(calibration.calibration_id)]["status"] == "later"
    assert "finish" not in json.dumps(later, ensure_ascii=False, default=str).lower()


@pytest.mark.asyncio
async def test_semantic_progress_is_explainable_and_has_no_percentage_or_pause_state() -> None:
    document_id = uuid4()
    source_id = uuid4()
    graph, _, _, state = await _graph_with_source(document_id, source_id)
    snapshot = snapshot_from_state(state)
    assert snapshot.opening_navigation.visible is True
    assert len(snapshot.opening_navigation.steps) == 4

    result = _result_with_understanding(
        source_id,
        impact=UnderstandingImpact.ROUTINE,
    )
    changeset = create_document_changeset(
        document_id=document_id,
        run_id=uuid4(),
        summary="建立待審 Task 候選。",
        read_revision=state["revision"],
        document=ApprovedJobDocument.model_validate(state["approved_document"]),
        changes=(
            ReviewableDocumentChange(
                operation=DocumentChangeOperation.ADD,
                path="/tasks",
                after={
                    "statement": "依缺料狀況建立請購單",
                    "action": "建立",
                    "object": "請購單",
                    "display_order": 0,
                },
                basis=_basis(source_id),
            ),
        ),
        existing_review_queue=state["review_queue"],
        interview_work=state["interview_work"],
    )
    state = await _commit(
        graph,
        document_id,
        state["revision"],
        source_id,
        result,
        published_changeset=changeset,
    )
    snapshot = snapshot_from_state(state)
    payload = snapshot.model_dump(mode="json")
    serialized = json.dumps(payload, ensure_ascii=False).lower()
    assert snapshot.opening_navigation.visible is False
    assert snapshot.current_interview is not None
    assert snapshot.current_interview.why_now
    assert snapshot.current_interview.missing_before_enough
    assert snapshot.understanding_projection.calibration is None
    assert snapshot.semantic_progress.currently_known_work_count == 1
    assert snapshot.semantic_progress.coverage
    assert snapshot.semantic_progress.depth
    assert snapshot.semantic_progress.depth[0].task_boundary == "interviewing"
    assert snapshot.semantic_progress.depth[0].duty_grouping == "not_yet_deepened"
    assert snapshot.semantic_progress.depth[0].knowledge == "not_yet_deepened"
    assert snapshot.semantic_progress.employee_decisions.pending == 1
    assert snapshot.approved_document.tasks == ()
    assert snapshot.semantic_progress.gaps[0].reason_code == "work_coverage_missing"
    assert "percent" not in serialized
    assert "本輪可停" not in serialized
    assert "pause" not in serialized
    assert "finish_interview" not in serialized


@pytest.mark.asyncio
async def test_long_return_creates_soft_calibration_without_resume_lifecycle() -> None:
    document_id = uuid4()
    first_source = uuid4()
    graph, _, _, state = await _graph_with_source(document_id, first_source)
    state = await _commit(
        graph,
        document_id,
        state["revision"],
        first_source,
        _result_with_understanding(
            first_source,
            impact=UnderstandingImpact.ROUTINE,
        ),
    )
    second_source = uuid4()
    reference = SourceReference(
        source_id=second_source,
        kind=EmployeeSourceKind.EMPLOYEE_TURN,
        created_at=datetime.now(UTC),
    )
    state = await graph.ainvoke(
        {},
        _config(document_id),
        context={
            "action": "register_source",
            "document_id": str(document_id),
            "expected_revision": state["revision"],
            "source_reference": reference.model_dump(mode="json"),
        },
    )
    returned_result = _result_with_understanding(
        second_source,
        impact=UnderstandingImpact.ROUTINE,
    ).model_copy(update={"attention_changes": ()})
    state = await _commit(
        graph,
        document_id,
        state["revision"],
        second_source,
        returned_result,
        returning_after_long_gap=True,
    )
    calibration = snapshot_from_state(state).understanding_projection.calibration
    assert calibration is not None
    assert calibration.kind == "soft"
    assert calibration.trigger == "long_return"
    assert "resume" not in state
    assert "paused" not in state


@pytest.mark.asyncio
async def test_sufficiency_is_hybrid_advice_and_new_evidence_recalculates_without_reopen() -> None:
    document_id = uuid4()
    source_id = uuid4()
    graph, saver, store, state = await _graph_with_source(document_id, source_id)
    state = await _commit(
        graph,
        document_id,
        state["revision"],
        source_id,
        _result_with_understanding(
            source_id,
            impact=UnderstandingImpact.ROUTINE,
            enough=True,
        ),
    )
    snapshot = snapshot_from_state(state)
    assert snapshot.sufficiency.currently_enough is True
    assert snapshot.sufficiency.why_enough
    assert snapshot.sufficiency.likely_benefit_of_continuing
    assert snapshot.sufficiency.deterministic_evidence.known_work_count == 1
    depth = snapshot.semantic_progress.depth[0]
    assert depth.task_boundary == "sufficient_for_now"
    assert depth.duty_grouping == "not_yet_deepened"
    assert depth.output == "not_yet_deepened"
    assert depth.knowledge == "not_yet_deepened"
    assert depth.skill == "not_yet_deepened"

    new_source_id = uuid4()
    reference = SourceReference(
        source_id=new_source_id,
        kind=EmployeeSourceKind.EMPLOYEE_TURN,
        created_at=datetime.now(UTC),
    )
    with_new_evidence = await graph.ainvoke(
        {},
        _config(document_id),
        context={
            "action": "register_source",
            "document_id": str(document_id),
            "expected_revision": state["revision"],
            "source_reference": reference.model_dump(mode="json"),
        },
    )
    assert snapshot_from_state(with_new_evidence).sufficiency.currently_enough is False
    assert snapshot_from_state(with_new_evidence).sufficiency.needs_recalculation is True

    recalculated = await _commit(
        graph,
        document_id,
        with_new_evidence["revision"],
        new_source_id,
        _result_with_understanding(
            new_source_id,
            impact=UnderstandingImpact.ROUTINE,
            enough=True,
        ),
    )
    assert snapshot_from_state(recalculated).sufficiency.currently_enough is True

    reopened_graph = build_consultant_graph(saver, store)
    reopened = await reopened_graph.aget_state(_config(document_id))
    assert snapshot_from_state(reopened.values).sufficiency.currently_enough is True
    assert "closed" not in reopened.values
    assert "reopened" not in reopened.values
