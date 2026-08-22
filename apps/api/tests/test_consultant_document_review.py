from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore

from app.consultant.document_review import (
    AtomicSubgroupIncomplete,
    DocumentReviewError,
    RejectedChangeRequiresNewEvidence,
    ReviewDependencyUnresolved,
    apply_review_command,
    block_review_dependent_work,
    create_document_changeset,
    revalidate_review_queue,
    stale_superseded_review_actions,
    stale_review_queue_for_direct_edit,
)
from app.consultant.document_authority import apply_document_actions
from app.consultant.graph import build_consultant_graph
from app.consultant.interview import (
    VerifiedConsultantCommit,
    _publish_persisted_changeset,
    apply_verified_consultant_commit,
)
from app.consultant.results import (
    AnalysisBasis,
    ConsultantResult,
    DocumentChangeOperation,
    GapReason,
    OpksKind,
    ReviewableDocumentChange,
    SufficiencyRecommendation,
)
from app.consultant.state import (
    ApprovedDuty,
    ApprovedJobDocument,
    ApprovedOpksItem,
    ApprovedOpksKind,
    ApprovedTask,
    DocumentChangeSet,
    DocumentChangeStatus,
    EmployeeSourceKind,
    InterviewPriority,
    InterviewWorkItem,
    InterviewWorkStatus,
    QuoteAnchor,
    SourceReference,
)
from app.consultant.views import document_review_projection_from_state
from app.consultant.understanding import semantic_progress_from_state


def _config(document_id: UUID) -> dict[str, dict[str, str]]:
    return {"configurable": {"thread_id": str(document_id)}}


def _source_reference(
    source_id: UUID,
    kind: EmployeeSourceKind = EmployeeSourceKind.EMPLOYEE_TURN,
) -> SourceReference:
    return SourceReference(
        source_id=source_id,
        kind=kind,
        created_at=datetime.now(UTC),
    )


def _basis(source_id: UUID) -> AnalysisBasis:
    return AnalysisBasis(
        source_ids=(source_id,),
        skill_ids=("task-boundary",),
    )


def _result(
    source_id: UUID,
) -> ConsultantResult:
    basis = _basis(source_id)
    return ConsultantResult(
        visible_reply="我整理了一組可供您審核的文件變更。",
        reply_basis=basis,
        used_skill_ids=("task-boundary",),
        sufficiency=SufficiencyRecommendation(
            currently_enough=False,
            reason="仍有工作細節待確認。",
            remaining_gap_reasons=(GapReason.WORK_COVERAGE_MISSING,),
            continuing_benefit="繼續訪談可補齊其他工作。",
            basis=basis,
        ),
    )


def _document(
    document_id: UUID,
    *,
    source_id: UUID,
) -> tuple[ApprovedJobDocument, UUID, UUID, UUID, UUID]:
    duty_a = uuid4()
    duty_b = uuid4()
    task_a = uuid4()
    task_b = uuid4()
    return (
        ApprovedJobDocument(
            document_id=document_id,
            job_title="採購專員",
            work_description="處理日常採購與供應商資料。",
            duties=(
                ApprovedDuty(
                    duty_id=duty_a,
                    statement="執行採購作業",
                    display_order=0,
                ),
                ApprovedDuty(
                    duty_id=duty_b,
                    statement="維護供應商資料",
                    display_order=1,
                ),
            ),
            tasks=(
                ApprovedTask(
                    task_id=task_a,
                    duty_id=duty_a,
                    statement="建立請購單",
                    action="建立",
                    object="請購單",
                    display_order=0,
                ),
                ApprovedTask(
                    task_id=task_b,
                    duty_id=duty_b,
                    statement="更新供應商資料",
                    action="更新",
                    object="供應商資料",
                    display_order=1,
                ),
            ),
            opks=(
                ApprovedOpksItem(
                    item_id=uuid4(),
                    kind=ApprovedOpksKind.KNOWLEDGE,
                    text="採購流程知識",
                    display_order=0,
                    task_ids=(task_a,),
                    evidence_source_ids=(source_id,),
                ),
            ),
        ),
        duty_a,
        duty_b,
        task_a,
        task_b,
    )


def _change(
    *,
    source_id: UUID,
    path: str,
    after: object,
    operation: DocumentChangeOperation = DocumentChangeOperation.REVISE,
    target_ids: tuple[UUID, ...] = (),
    task_ids: tuple[UUID, ...] = (),
    opks_kind: OpksKind | None = None,
) -> ReviewableDocumentChange:
    return ReviewableDocumentChange(
        operation=operation,
        path=path,
        after=after,
        target_ids=target_ids,
        task_ids=task_ids,
        opks_kind=opks_kind,
        basis=_basis(source_id),
    )


def _opks_add(
    *,
    source_id: UUID,
    task_id: UUID,
    item_id: UUID,
    skill_ids: tuple[str, ...] = ("output",),
    anchored: bool = False,
) -> ReviewableDocumentChange:
    anchors = (
        (QuoteAnchor(source_id=source_id, start=0, end=2, quote="完成"),)
        if anchored
        else ()
    )
    return ReviewableDocumentChange(
        operation=DocumentChangeOperation.ADD,
        path="/opks",
        after={
            "item_id": str(item_id),
            "text": "完成的請購單",
            "display_order": None,
        },
        task_ids=(task_id,),
        opks_kind=OpksKind.OUTPUT,
        basis=AnalysisBasis(
            source_ids=(source_id,),
            quote_anchors=anchors,
            skill_ids=skill_ids,
        ),
    )


async def _initialize_with_document(
    document: ApprovedJobDocument,
    *,
    source_id: UUID,
):
    saver = InMemorySaver()
    store = InMemoryStore()
    graph = build_consultant_graph(saver, store)
    await graph.ainvoke(
        {},
        _config(document.document_id),
        context={
            "action": "initialize",
            "document_id": str(document.document_id),
        },
    )
    state = await graph.ainvoke(
        {},
        _config(document.document_id),
        context={
            "action": "direct_edit",
            "document_id": str(document.document_id),
            "expected_revision": 0,
            "source_reference": _source_reference(
                source_id, EmployeeSourceKind.DIRECT_EDIT
            ).model_dump(mode="json"),
            "approved_document": document.model_dump(mode="json"),
        },
    )
    return graph, saver, store, state


async def _register_source(
    graph,
    document_id: UUID,
    *,
    revision: int,
    source_id: UUID,
):
    return await graph.ainvoke(
        {},
        _config(document_id),
        context={
            "action": "register_source",
            "document_id": str(document_id),
            "expected_revision": revision,
            "source_reference": _source_reference(source_id).model_dump(mode="json"),
        },
    )


async def _commit_changes(
    graph,
    document_id: UUID,
    *,
    revision: int,
    source_id: UUID,
    run_id: UUID,
    changes: tuple[ReviewableDocumentChange, ...],
):
    state = (await graph.aget_state(_config(document_id))).values
    document = ApprovedJobDocument.model_validate(state["approved_document"])
    published_changeset = create_document_changeset(
        document_id=document_id,
        run_id=run_id,
        summary="我整理了一組可供您審核的文件變更。",
        read_revision=revision,
        document=document,
        changes=changes,
        existing_review_queue=state.get("review_queue", {}),
        interview_work=state.get("interview_work", {}),
    )
    now = datetime.now(UTC)
    commit = VerifiedConsultantCommit(
        run_id=run_id,
        answer_source_id=source_id,
        started_at=now,
        completed_at=now,
        result=_result(source_id),
    )
    published = apply_verified_consultant_commit(
        state,
        document_id=document_id,
        revision=revision + 1,
        commit=commit,
        published_changeset=published_changeset,
    )
    await graph.aupdate_state(_config(document_id), published)
    return (await graph.aget_state(_config(document_id))).values


def test_application_assigns_stable_action_ids_and_remembers_rejection_by_target() -> None:
    document_id = uuid4()
    source_id = uuid4()
    document, _duty_a, _duty_b, task_a, _task_b = _document(
        document_id,
        source_id=source_id,
    )
    run_id = uuid4()
    semantic_change = _change(
        source_id=source_id,
        path=f"/tasks/{task_a}/statement",
        after="建立並覆核請購單",
    )

    first = create_document_changeset(
        document_id=document_id,
        run_id=run_id,
        summary="更新請購任務敘述。",
        read_revision=4,
        document=document,
        changes=(semantic_change,),
        existing_review_queue={},
        interview_work={},
    )
    replay = create_document_changeset(
        document_id=document_id,
        run_id=run_id,
        summary="更新請購任務敘述。",
        read_revision=4,
        document=document,
        changes=(semantic_change,),
        existing_review_queue={},
        interview_work={},
    )
    assert first == replay
    assert first.actions[0].before == "建立請購單"
    assert first.actions[0].read_set[0].path == f"/tasks/{task_a}/statement"

    rejected_action = first.actions[0].model_copy(
        update={
            "status": DocumentChangeStatus.REJECTED,
            "rejection_reason": "這不是我的工作內容。",
        }
    )
    rejected = first.model_copy(update={"actions": (rejected_action,)})
    queue = {str(rejected.changeset_id): rejected.model_dump(mode="json")}
    replayed = _change(
        source_id=source_id,
        path=f"/tasks/{task_a}/statement",
        after="建立並覆核請購單",
    )
    with pytest.raises(RejectedChangeRequiresNewEvidence):
        create_document_changeset(
            document_id=document_id,
            run_id=uuid4(),
            summary="重新提出同一路徑。",
            read_revision=4,
            document=document,
            changes=(replayed,),
            existing_review_queue=queue,
            interview_work={},
        )


    new_source = uuid4()
    with_new_evidence = _change(
        source_id=new_source,
        path=f"/tasks/{task_a}/statement",
        after="建立請購資料並完成覆核",
    )
    proposed_again = create_document_changeset(
        document_id=document_id,
        run_id=uuid4(),
        summary="新證據支持重新提出。",
        read_revision=4,
        document=document,
        changes=(with_new_evidence,),
        existing_review_queue=queue,
        interview_work={},
    )
    assert proposed_again.actions[0].source_ids == (new_source,)


def test_application_review_factory_accepts_a_run_independent_identity_scope() -> None:
    document_id = uuid4()
    source_id = uuid4()
    document, _duty_a, _duty_b, task_a, _task_b = _document(
        document_id,
        source_id=source_id,
    )
    change = _change(
        source_id=source_id,
        path=f"/tasks/{task_a}/statement",
        after="依工作區內容複核請購單",
    )
    kwargs = {
        "document_id": document_id,
        "summary": "工作區語意審查。",
        "read_revision": 4,
        "document": document,
        "changes": (change,),
        "existing_review_queue": {},
        "interview_work": {},
        "identity_scope": "workspace:revision=4:generation=2:digest=abc",
    }

    first = create_document_changeset(run_id=uuid4(), **kwargs)
    another_run = create_document_changeset(run_id=uuid4(), **kwargs)

    assert first == another_run


def test_rejection_memory_distinguishes_opks_axes_from_the_same_evidence() -> None:
    document_id = uuid4()
    source_id = uuid4()
    document, _duty_a, _duty_b, task_a, _task_b = _document(
        document_id,
        source_id=source_id,
    )
    output = _change(
        source_id=source_id,
        path="/opks",
        operation=DocumentChangeOperation.ADD,
        after="完成的請購單",
        task_ids=(task_a,),
        opks_kind=OpksKind.OUTPUT,
    )
    rejected_bundle = create_document_changeset(
        document_id=document_id,
        run_id=uuid4(),
        summary="建議工作產出。",
        read_revision=1,
        document=document,
        changes=(output,),
        existing_review_queue={},
        interview_work={},
    )
    rejected = rejected_bundle.model_copy(
        update={
            "actions": (
                rejected_bundle.actions[0].model_copy(
                    update={
                        "status": DocumentChangeStatus.REJECTED,
                        "rejection_reason": "這不是本工作的產出。",
                    }
                ),
            )
        }
    )
    indicator = _change(
        source_id=source_id,
        path="/opks",
        operation=DocumentChangeOperation.ADD,
        after="請購內容正確",
        task_ids=(task_a,),
        opks_kind=OpksKind.PERFORMANCE_INDICATOR,
    )

    allowed = create_document_changeset(
        document_id=document_id,
        run_id=uuid4(),
        summary="建議績效指標。",
        read_revision=1,
        document=document,
        changes=(indicator,),
        existing_review_queue={
            str(rejected.changeset_id): rejected.model_dump(mode="json")
        },
        interview_work={},
    )

    assert allowed.actions[0].target_key != rejected.actions[0].target_key


def test_rejected_opks_add_cannot_reappear_by_changing_method_or_anchor() -> None:
    document_id = uuid4()
    source_id = uuid4()
    item_id = uuid4()
    document, _duty_a, _duty_b, task_a, _task_b = _document(
        document_id,
        source_id=source_id,
    )
    rejected_bundle = create_document_changeset(
        document_id=document_id,
        run_id=uuid4(),
        summary="建議工作產出。",
        read_revision=1,
        document=document,
        changes=(_opks_add(source_id=source_id, task_id=task_a, item_id=item_id),),
        existing_review_queue={},
        interview_work={},
    )
    rejected = rejected_bundle.model_copy(
        update={
            "actions": (
                rejected_bundle.actions[0].model_copy(
                    update={
                        "status": DocumentChangeStatus.REJECTED,
                        "rejection_reason": "這不是本工作的產出。",
                    }
                ),
            )
        }
    )
    queue = {str(rejected.changeset_id): rejected.model_dump(mode="json")}

    def _create_again(replay: ReviewableDocumentChange) -> DocumentChangeSet:
        return create_document_changeset(
            document_id=document_id,
            run_id=uuid4(),
            summary="重新提出同一項產出。",
            read_revision=1,
            document=document,
            changes=(replay,),
            existing_review_queue=queue,
            interview_work={},
        )

    for replay in (
        _opks_add(
            source_id=source_id,
            task_id=task_a,
            item_id=item_id,
            skill_ids=("output", "story-interview"),
        ),
        _opks_add(
            source_id=source_id,
            task_id=task_a,
            item_id=item_id,
            anchored=True,
        ),
    ):
        with pytest.raises(RejectedChangeRequiresNewEvidence):
            _create_again(replay)


def test_rejected_opks_add_ignores_application_owned_identity_and_order() -> None:
    document_id = uuid4()
    source_id = uuid4()
    document, _duty_a, _duty_b, task_a, _task_b = _document(
        document_id,
        source_id=source_id,
    )
    rejected_bundle = create_document_changeset(
        document_id=document_id,
        run_id=uuid4(),
        summary="建議工作產出。",
        read_revision=1,
        document=document,
        changes=(
            _opks_add(
                source_id=source_id,
                task_id=task_a,
                item_id=uuid4(),
            ),
        ),
        existing_review_queue={},
        interview_work={},
    )
    rejected = rejected_bundle.model_copy(
        update={
            "actions": (
                rejected_bundle.actions[0].model_copy(
                    update={
                        "status": DocumentChangeStatus.REJECTED,
                        "rejection_reason": "這不是本工作的產出。",
                    }
                ),
            )
        }
    )

    with pytest.raises(RejectedChangeRequiresNewEvidence):
        create_document_changeset(
            document_id=document_id,
            run_id=uuid4(),
            summary="不同 generated identity 的同一項產出。",
            read_revision=1,
            document=document,
            changes=(
                _opks_add(
                    source_id=source_id,
                    task_id=task_a,
                    item_id=uuid4(),
                ),
            ),
            existing_review_queue={
                str(rejected.changeset_id): rejected.model_dump(mode="json")
            },
            interview_work={},
        )


def test_rejected_opks_add_may_reappear_with_new_employee_source() -> None:
    document_id = uuid4()
    source_id = uuid4()
    new_source = uuid4()
    item_id = uuid4()
    document, _duty_a, _duty_b, task_a, _task_b = _document(
        document_id,
        source_id=source_id,
    )
    rejected_bundle = create_document_changeset(
        document_id=document_id,
        run_id=uuid4(),
        summary="建議工作產出。",
        read_revision=1,
        document=document,
        changes=(_opks_add(source_id=source_id, task_id=task_a, item_id=item_id),),
        existing_review_queue={},
        interview_work={},
    )
    rejected = rejected_bundle.model_copy(
        update={
            "actions": (
                rejected_bundle.actions[0].model_copy(
                    update={
                        "status": DocumentChangeStatus.REJECTED,
                        "rejection_reason": "這不是本工作的產出。",
                    }
                ),
            )
        }
    )

    replayed = create_document_changeset(
        document_id=document_id,
        run_id=uuid4(),
        summary="新證據支持重新提出。",
        read_revision=1,
        document=document,
        changes=(_opks_add(source_id=new_source, task_id=task_a, item_id=item_id),),
        existing_review_queue={
            str(rejected.changeset_id): rejected.model_dump(mode="json")
        },
        interview_work={},
    )

    assert replayed.actions


@pytest.mark.asyncio
async def test_multiple_bundles_support_partial_defer_out_of_order_and_edit_accept() -> None:
    document_id = uuid4()
    seed_source = uuid4()
    document, _duty_a, _duty_b, task_a, task_b = _document(
        document_id,
        source_id=seed_source,
    )
    graph, _saver, _store, state = await _initialize_with_document(
        document,
        source_id=seed_source,
    )
    source_a = uuid4()
    state = await _register_source(
        graph,
        document_id,
        revision=state["revision"],
        source_id=source_a,
    )
    run_a = uuid4()
    state = await _commit_changes(
        graph,
        document_id,
        revision=state["revision"],
        source_id=source_a,
        run_id=run_a,
        changes=(
            _change(
                source_id=source_a,
                path=f"/tasks/{task_a}/statement",
                after="建立與覆核請購單",
            ),
            _change(
                source_id=source_a,
                path="/work_description",
                after="處理採購、覆核與供應商資料維護。",
            ),
        ),
    )
    source_b = uuid4()
    state = await _register_source(
        graph,
        document_id,
        revision=state["revision"],
        source_id=source_b,
    )
    run_b = uuid4()
    state = await _commit_changes(
        graph,
        document_id,
        revision=state["revision"],
        source_id=source_b,
        run_id=run_b,
        changes=(
            _change(
                source_id=source_b,
                path=f"/tasks/{task_b}/statement",
                after="定期更新供應商基本資料",
            ),
        ),
    )
    bundles = {
        key: DocumentChangeSet.model_validate(value)
        for key, value in state["review_queue"].items()
    }
    bundle_a = next(item for item in bundles.values() if len(item.actions) == 2)
    bundle_b = next(item for item in bundles.values() if len(item.actions) == 1)
    task_a_action, description_action = bundle_a.actions
    task_b_action = bundle_b.actions[0]
    source_count_before_decisions = state["source_count"]

    state = await graph.ainvoke(
        {},
        _config(document_id),
        context={
            "action": "defer_changes",
            "document_id": str(document_id),
            "expected_revision": state["revision"],
            "changeset_id": str(bundle_a.changeset_id),
            "action_ids": [str(task_a_action.action_id)],
        },
    )
    state = await graph.ainvoke(
        {},
        _config(document_id),
        context={
            "action": "accept_changes",
            "document_id": str(document_id),
            "expected_revision": state["revision"],
            "changeset_id": str(bundle_b.changeset_id),
            "action_ids": [str(task_b_action.action_id)],
        },
    )
    state = await graph.ainvoke(
        {},
        _config(document_id),
        context={
            "action": "reject_changes",
            "document_id": str(document_id),
            "expected_revision": state["revision"],
            "changeset_id": str(bundle_a.changeset_id),
            "action_ids": [str(description_action.action_id)],
            "rejection_reason": "工作描述先維持原文。",
        },
    )
    edit_source = uuid4()
    state = await graph.ainvoke(
        {},
        _config(document_id),
        context={
            "action": "edit_and_accept_changes",
            "document_id": str(document_id),
            "expected_revision": state["revision"],
            "changeset_id": str(bundle_a.changeset_id),
            "action_ids": [str(task_a_action.action_id)],
            "edited_after_by_action_id": {
                str(task_a_action.action_id): "建立、覆核並送出請購單"
            },
            "source_reference": _source_reference(
                edit_source, EmployeeSourceKind.DIRECT_EDIT
            ).model_dump(mode="json"),
        },
    )

    approved = ApprovedJobDocument.model_validate(state["approved_document"])
    by_task = {item.task_id: item for item in approved.tasks}
    assert by_task[task_b].statement == "定期更新供應商基本資料"
    assert by_task[task_a].statement == "建立、覆核並送出請購單"
    assert approved.work_description == document.work_description
    assert state["source_count"] == source_count_before_decisions + 1
    updated_a = DocumentChangeSet.model_validate(
        state["review_queue"][str(bundle_a.changeset_id)]
    )
    assert [item.status for item in updated_a.actions] == [
        DocumentChangeStatus.EDIT_ACCEPTED,
        DocumentChangeStatus.REJECTED,
    ]
    assert updated_a.actions[0].employee_after == "建立、覆核並送出請購單"
    assert updated_a.actions[1].rejection_reason == "工作描述先維持原文。"
    decisions = semantic_progress_from_state(state).employee_decisions
    assert decisions.accepted == 1
    assert decisions.edit_accepted == 1
    assert decisions.rejected == 1
    assert decisions.pending == 0
    assert decisions.deferred == 0


@pytest.mark.asyncio
async def test_direct_edit_stales_only_conflicting_action_and_keeps_independent_review() -> None:
    document_id = uuid4()
    seed_source = uuid4()
    document, _duty_a, _duty_b, task_a, task_b = _document(
        document_id,
        source_id=seed_source,
    )
    graph, _saver, _store, state = await _initialize_with_document(
        document,
        source_id=seed_source,
    )
    answer_source = uuid4()
    state = await _register_source(
        graph,
        document_id,
        revision=state["revision"],
        source_id=answer_source,
    )
    state = await _commit_changes(
        graph,
        document_id,
        revision=state["revision"],
        source_id=answer_source,
        run_id=uuid4(),
        changes=(
            _change(
                source_id=answer_source,
                path=f"/tasks/{task_a}/statement",
                after="AI 修改 A",
            ),
            _change(
                source_id=answer_source,
                path=f"/tasks/{task_b}/statement",
                after="AI 修改 B",
            ),
        ),
    )
    bundle = DocumentChangeSet.model_validate(next(iter(state["review_queue"].values())))
    action_a, action_b = bundle.actions
    edited_document = document.model_copy(
        update={
            "tasks": (
                document.tasks[0].model_copy(update={"statement": "員工直接修改 A"}),
                document.tasks[1],
            )
        }
    )
    state = await graph.ainvoke(
        {},
        _config(document_id),
        context={
            "action": "direct_edit",
            "document_id": str(document_id),
            "expected_revision": state["revision"],
            "source_reference": _source_reference(
                uuid4(), EmployeeSourceKind.DIRECT_EDIT
            ).model_dump(mode="json"),
            "approved_document": edited_document.model_dump(mode="json"),
        },
    )
    updated = DocumentChangeSet.model_validate(
        state["review_queue"][str(bundle.changeset_id)]
    )
    assert updated.actions[0].status is DocumentChangeStatus.STALE
    assert "員工直接修改" in updated.actions[0].stale_reason
    assert updated.actions[1].status is DocumentChangeStatus.PENDING

    state = await graph.ainvoke(
        {},
        _config(document_id),
        context={
            "action": "accept_changes",
            "document_id": str(document_id),
            "expected_revision": state["revision"],
            "changeset_id": str(bundle.changeset_id),
            "action_ids": [str(action_b.action_id)],
        },
    )
    approved = ApprovedJobDocument.model_validate(state["approved_document"])
    assert approved.tasks[0].statement == "員工直接修改 A"
    assert approved.tasks[1].statement == "AI 修改 B"

    with pytest.raises(DocumentReviewError, match="pending or deferred"):
        await graph.ainvoke(
            {},
            _config(document_id),
            context={
                "action": "accept_changes",
                "document_id": str(document_id),
                "expected_revision": state["revision"],
                "changeset_id": str(bundle.changeset_id),
                "action_ids": [str(action_a.action_id)],
            },
        )
    unchanged = ApprovedJobDocument.model_validate(state["approved_document"])
    assert unchanged == approved


@pytest.mark.asyncio
async def test_employee_source_correction_stales_only_dependent_review_actions() -> None:
    document_id = uuid4()
    seed_source = uuid4()
    document, _duty_a, _duty_b, task_a, task_b = _document(
        document_id,
        source_id=seed_source,
    )
    graph, _saver, _store, state = await _initialize_with_document(
        document,
        source_id=seed_source,
    )
    source_a = uuid4()
    state = await _register_source(
        graph,
        document_id,
        revision=state["revision"],
        source_id=source_a,
    )
    state = await _commit_changes(
        graph,
        document_id,
        revision=state["revision"],
        source_id=source_a,
        run_id=uuid4(),
        changes=(
            _change(
                source_id=source_a,
                path=f"/tasks/{task_a}/statement",
                after="依舊說法修改 A",
            ),
        ),
    )
    source_b = uuid4()
    state = await _register_source(
        graph,
        document_id,
        revision=state["revision"],
        source_id=source_b,
    )
    state = await _commit_changes(
        graph,
        document_id,
        revision=state["revision"],
        source_id=source_b,
        run_id=uuid4(),
        changes=(
            _change(
                source_id=source_b,
                path=f"/tasks/{task_b}/statement",
                after="不相干的修改 B",
            ),
        ),
    )
    correction_source = uuid4()
    state = await graph.ainvoke(
        {},
        _config(document_id),
        context={
            "action": "register_source",
            "document_id": str(document_id),
            "expected_revision": state["revision"],
            "source_reference": SourceReference(
                source_id=correction_source,
                kind=EmployeeSourceKind.EMPLOYEE_TURN,
                created_at=datetime.now(UTC),
                supersedes_source_id=source_a,
            ).model_dump(mode="json"),
        },
    )
    by_source = {
        bundle.source_ids[0]: bundle.actions[0]
        for bundle in (
            DocumentChangeSet.model_validate(raw)
            for raw in state["review_queue"].values()
        )
    }
    assert by_source[source_a].status is DocumentChangeStatus.STALE
    assert "更正" in by_source[source_a].stale_reason
    assert by_source[source_b].status is DocumentChangeStatus.PENDING


def test_structural_atomic_group_blocks_only_its_dependent_work() -> None:
    document_id = uuid4()
    source_id = uuid4()
    document, _duty_a, _duty_b, task_a, task_b = _document(
        document_id,
        source_id=source_id,
    )
    work_a = uuid4()
    work_b = uuid4()
    interview_work = {
        str(work_a): InterviewWorkItem(
            work_id=work_a,
            kind="task",
            title="請購下單",
            subject_id=task_a,
            status=InterviewWorkStatus.ACTIVE,
            priority=InterviewPriority.TASK_BOUNDARY,
            priority_reason="目前正在釐清責任範圍。",
            source_ids=(source_id,),
            last_changed_revision=2,
        ).model_dump(mode="json"),
        str(work_b): InterviewWorkItem(
            work_id=work_b,
            kind="task",
            title="供應商維護",
            subject_id=task_b,
            status=InterviewWorkStatus.PARKED,
            priority=InterviewPriority.COVERAGE,
            priority_reason="稍後仍可安全訪談。",
            source_ids=(source_id,),
            last_changed_revision=2,
        ).model_dump(mode="json"),
    }
    new_duty = uuid4()
    bundle = create_document_changeset(
        document_id=document_id,
        run_id=uuid4(),
        summary="建立新職責並重新歸類任務。",
        read_revision=2,
        document=document,
        changes=(
            _change(
                source_id=source_id,
                path="/duties",
                operation=DocumentChangeOperation.ADD,
                after={
                    "duty_id": str(new_duty),
                    "statement": "管理請購與覆核",
                    "display_order": 2,
                },
            ),
            _change(
                source_id=source_id,
                path=f"/tasks/{task_a}/duty_id",
                operation=DocumentChangeOperation.REASSIGN,
                after=str(new_duty),
                task_ids=(task_a,),
            ),
        ),
        existing_review_queue={},
        interview_work=interview_work,
    )
    add_duty, reassign = bundle.actions
    assert add_duty.atomic_subgroup_id is not None
    assert add_duty.atomic_subgroup_id == reassign.atomic_subgroup_id
    assert add_duty.action_id in reassign.depends_on_action_ids
    assert reassign.affected_work_ids == (work_a,)

    blocked_work = {
        **interview_work,
        str(work_a): InterviewWorkItem.model_validate(
            interview_work[str(work_a)]
        ).model_copy(
            update={
                "status": InterviewWorkStatus.BLOCKED,
                "blocked_by_decision_ids": (reassign.action_id,),
                "resume_status": InterviewWorkStatus.ACTIVE,
            }
        ).model_dump(mode="json"),
    }
    with_safe_branch = document_review_projection_from_state(
        {
            "review_queue": {
                str(bundle.changeset_id): bundle.model_dump(mode="json")
            },
            "interview_work": blocked_work,
        }
    )
    assert with_safe_branch.safe_interview_work_available is True
    assert with_safe_branch.decision_required_before_more_interview is False
    no_safe_branch = document_review_projection_from_state(
        {
            "review_queue": {
                str(bundle.changeset_id): bundle.model_dump(mode="json")
            },
            "interview_work": {str(work_a): blocked_work[str(work_a)]},
        }
    )
    assert no_safe_branch.decision_required_before_more_interview is True
    assert "需先處理" in no_safe_branch.explanation

    state = {
        "document_id": str(document_id),
        "revision": 2,
        "approved_document": document.model_dump(mode="json"),
        "review_queue": {
            str(bundle.changeset_id): bundle.model_dump(mode="json")
        },
        "interview_work": interview_work,
        "current_work_id": str(work_a),
        "gaps": {},
        "understanding": {},
    }
    with pytest.raises(AtomicSubgroupIncomplete):
        apply_review_command(
            state,
            action="accept_changes",
            changeset_id=bundle.changeset_id,
            action_ids=(reassign.action_id,),
            revision=3,
        )

    update = apply_review_command(
        state,
        action="accept_changes",
        changeset_id=bundle.changeset_id,
        action_ids=(add_duty.action_id, reassign.action_id),
        revision=3,
    )
    approved = ApprovedJobDocument.model_validate(update["approved_document"])
    assert {item.duty_id for item in approved.duties} >= {new_duty}
    assert next(item for item in approved.tasks if item.task_id == task_a).duty_id == new_duty
    work = {
        key: InterviewWorkItem.model_validate(value)
        for key, value in update["interview_work"].items()
    }
    assert work[str(work_a)].status is not InterviewWorkStatus.BLOCKED
    assert work[str(work_b)].status is not InterviewWorkStatus.BLOCKED


def test_document_decision_preserves_non_review_blockers_and_projection_scope() -> None:
    document_id = uuid4()
    source_id = uuid4()
    document, _duty_a, duty_b, task_a, task_b = _document(
        document_id,
        source_id=source_id,
    )
    affected_work_id = uuid4()
    safe_work_id = uuid4()
    work = {
        str(affected_work_id): InterviewWorkItem(
            work_id=affected_work_id,
            kind="task",
            title="請購下單",
            subject_id=task_a,
            status=InterviewWorkStatus.ACTIVE,
            priority=InterviewPriority.TASK_BOUNDARY,
            priority_reason="目前正在釐清責任範圍。",
            source_ids=(source_id,),
            last_changed_revision=2,
        ).model_dump(mode="json"),
        str(safe_work_id): InterviewWorkItem(
            work_id=safe_work_id,
            kind="task",
            title="供應商維護",
            subject_id=task_b,
            status=InterviewWorkStatus.PARKED,
            priority=InterviewPriority.COVERAGE,
            priority_reason="稍後仍可安全訪談。",
            source_ids=(source_id,),
            last_changed_revision=2,
        ).model_dump(mode="json"),
    }
    bundle = create_document_changeset(
        document_id=document_id,
        run_id=uuid4(),
        summary="重新歸類請購任務。",
        read_revision=2,
        document=document,
        changes=(
            _change(
                source_id=source_id,
                path=f"/tasks/{task_a}/duty_id",
                operation=DocumentChangeOperation.REASSIGN,
                after=str(duty_b),
                task_ids=(task_a,),
            ),
        ),
        existing_review_queue={},
        interview_work=work,
    )
    review_action = bundle.actions[0]
    work = block_review_dependent_work(work, bundle.actions, revision=3)
    clarification_id = uuid4()
    affected = InterviewWorkItem.model_validate(work[str(affected_work_id)])
    work[str(affected_work_id)] = affected.model_copy(
        update={
            "blocked_by_decision_ids": (
                *affected.blocked_by_decision_ids,
                clarification_id,
            )
        }
    ).model_dump(mode="json")

    projection = document_review_projection_from_state(
        {
            "review_queue": {
                str(bundle.changeset_id): bundle.model_dump(mode="json")
            },
            "interview_work": work,
        }
    )
    assert projection.blocked_branches[0].decision_action_ids == (
        review_action.action_id,
    )

    update = apply_review_command(
        {
            "approved_document": document.model_dump(mode="json"),
            "review_queue": {
                str(bundle.changeset_id): bundle.model_dump(mode="json")
            },
            "interview_work": work,
            "understanding": {},
            "gaps": {},
        },
        action="accept_changes",
        changeset_id=bundle.changeset_id,
        action_ids=(review_action.action_id,),
        revision=3,
    )
    remaining = InterviewWorkItem.model_validate(
        update["interview_work"][str(affected_work_id)]
    )
    assert remaining.status is InterviewWorkStatus.BLOCKED
    assert remaining.blocked_by_decision_ids == (clarification_id,)


def test_responsibility_change_blocks_only_the_affected_task_branch() -> None:
    document_id = uuid4()
    source_id = uuid4()
    document, _duty_a, _duty_b, task_a, task_b = _document(
        document_id,
        source_id=source_id,
    )
    affected_work_id = uuid4()
    safe_work_id = uuid4()
    work = {
        str(affected_work_id): InterviewWorkItem(
            work_id=affected_work_id,
            kind="task",
            title="請購下單",
            subject_id=task_a,
            status=InterviewWorkStatus.ACTIVE,
            priority=InterviewPriority.HIGH_IMPACT,
            priority_reason="釐清本人責任。",
            source_ids=(source_id,),
            last_changed_revision=1,
        ).model_dump(mode="json"),
        str(safe_work_id): InterviewWorkItem(
            work_id=safe_work_id,
            kind="task",
            title="供應商維護",
            subject_id=task_b,
            status=InterviewWorkStatus.PARKED,
            priority=InterviewPriority.COVERAGE,
            priority_reason="可繼續訪談。",
            source_ids=(source_id,),
            last_changed_revision=1,
        ).model_dump(mode="json"),
    }
    bundle = create_document_changeset(
        document_id=document_id,
        run_id=uuid4(),
        summary="確認請購責任由本人主責。",
        read_revision=1,
        document=document,
        changes=(
            _change(
                source_id=source_id,
                path=f"/tasks/{task_a}/responsibility_role",
                after="primary",
            ),
        ),
        existing_review_queue={},
        interview_work=work,
    )
    action = bundle.actions[0]
    assert action.blocks_dependent_analysis is True
    assert action.affected_work_ids == (affected_work_id,)
    blocked = block_review_dependent_work(work, bundle.actions, revision=2)
    assert (
        InterviewWorkItem.model_validate(blocked[str(affected_work_id)]).status
        is InterviewWorkStatus.BLOCKED
    )
    assert (
        InterviewWorkItem.model_validate(blocked[str(safe_work_id)]).status
        is InterviewWorkStatus.PARKED
    )


def test_one_stale_atomic_member_stales_the_whole_subgroup() -> None:
    document_id = uuid4()
    source_id = uuid4()
    document, duty_a, duty_b, _task_a, _task_b = _document(
        document_id,
        source_id=source_id,
    )
    duty_c = uuid4()
    document = document.model_copy(
        update={
            "duties": (
                *document.duties,
                ApprovedDuty(
                    duty_id=duty_c,
                    statement="管理合約文件",
                    display_order=2,
                ),
            )
        }
    )
    bundle = create_document_changeset(
        document_id=document_id,
        run_id=uuid4(),
        summary="交換兩項職責順序。",
        read_revision=2,
        document=document,
        changes=(
            _change(
                source_id=source_id,
                path=f"/duties/{duty_a}/display_order",
                operation=DocumentChangeOperation.REORDER,
                after=1,
            ),
            _change(
                source_id=source_id,
                path=f"/duties/{duty_b}/display_order",
                operation=DocumentChangeOperation.REORDER,
                after=0,
            ),
        ),
        existing_review_queue={},
        interview_work={},
    )
    assert bundle.actions[0].atomic_subgroup_id == bundle.actions[1].atomic_subgroup_id
    edited = document.model_copy(
        update={
            "duties": (
                document.duties[0].model_copy(update={"display_order": 2}),
                document.duties[1],
                document.duties[2].model_copy(update={"display_order": 0}),
            )
        }
    )
    queue = stale_review_queue_for_direct_edit(
        document,
        edited,
        {str(bundle.changeset_id): bundle.model_dump(mode="json")},
    )
    updated = DocumentChangeSet.model_validate(queue[str(bundle.changeset_id)])
    assert {item.status for item in updated.actions} == {
        DocumentChangeStatus.STALE
    }


def test_employee_document_can_keep_competency_attitude_and_classification_fields() -> None:
    document_id = uuid4()
    source_id = uuid4()
    task_id = uuid4()
    document = ApprovedJobDocument(
        document_id=document_id,
        occupation_category_name="生產製造",
        occupation_name="採購人員",
        occupation_code="3343",
        industry_name="製造業",
        industry_code="C",
        competency_level=4,
        tasks=(
            ApprovedTask(
                task_id=task_id,
                statement="建立請購單",
                action="建立",
                object="請購單",
                display_order=0,
                competency_level=3,
            ),
        ),
        opks=(
            ApprovedOpksItem(
                item_id=uuid4(),
                kind=ApprovedOpksKind.ATTITUDE,
                text="細心",
                display_order=0,
                evidence_source_ids=(source_id,),
            ),
        ),
    )
    assert document.competency_level == 4
    assert document.opks[0].kind is ApprovedOpksKind.ATTITUDE
    with pytest.raises(ValueError):
        ApprovedJobDocument.model_validate(
            {
                **document.model_dump(mode="json"),
                "competency_standard_code": "ICAP-FAKE",
            }
        )

    with pytest.raises(DocumentReviewError, match="existing axis"):
        create_document_changeset(
            document_id=document_id,
            run_id=uuid4(),
            summary="模型不得把 A 偽裝成 K 修改。",
            read_revision=1,
            document=document,
            changes=(
                _change(
                    source_id=source_id,
                    path=f"/opks/{document.opks[0].item_id}/text",
                    after="模型修改的態度",
                    opks_kind=OpksKind.KNOWLEDGE,
                    task_ids=(task_id,),
                ),
            ),
            existing_review_queue={},
            interview_work={},
        )


def test_first_release_model_document_surfaces_apply_with_employee_authority() -> None:
    document_id = uuid4()
    source_id = uuid4()
    document, duty_a, duty_b, task_a, task_b = _document(
        document_id,
        source_id=source_id,
    )
    knowledge_id = document.opks[0].item_id
    changes = (
        _change(source_id=source_id, path="/job_title", after="資深採購專員"),
        _change(
            source_id=source_id,
            path="/work_description",
            after="負責採購、覆核與供應商資訊維護。",
        ),
        _change(
            source_id=source_id,
            path=f"/duties/{duty_a}/statement",
            after="規劃與執行採購",
        ),
        _change(
            source_id=source_id,
            path=f"/duties/{duty_a}/display_order",
            operation=DocumentChangeOperation.REORDER,
            after=1,
        ),
        _change(
            source_id=source_id,
            path=f"/duties/{duty_b}/display_order",
            operation=DocumentChangeOperation.REORDER,
            after=0,
        ),
        _change(
            source_id=source_id,
            path=f"/tasks/{task_a}/statement",
            after="建立、覆核並送出請購單",
        ),
        _change(
            source_id=source_id,
            path=f"/tasks/{task_a}/duty_id",
            operation=DocumentChangeOperation.REASSIGN,
            after=str(duty_b),
            task_ids=(task_a,),
        ),
        _change(
            source_id=source_id,
            path=f"/tasks/{task_a}/display_order",
            operation=DocumentChangeOperation.REORDER,
            after=1,
        ),
        _change(
            source_id=source_id,
            path=f"/tasks/{task_b}/display_order",
            operation=DocumentChangeOperation.REORDER,
            after=0,
        ),
        _change(
            source_id=source_id,
            path="/opks",
            operation=DocumentChangeOperation.ADD,
            after="完成覆核的請購單",
            task_ids=(task_a,),
            opks_kind=OpksKind.OUTPUT,
        ),
        _change(
            source_id=source_id,
            path="/opks",
            operation=DocumentChangeOperation.ADD,
            after="請購內容正確且可追溯",
            task_ids=(task_a,),
            opks_kind=OpksKind.PERFORMANCE_INDICATOR,
        ),
        _change(
            source_id=source_id,
            path=f"/opks/{knowledge_id}/text",
            after="採購與覆核流程知識",
            task_ids=(task_a,),
            opks_kind=OpksKind.KNOWLEDGE,
        ),
        _change(
            source_id=source_id,
            path="/opks",
            operation=DocumentChangeOperation.ADD,
            after="核對採購需求與表單",
            task_ids=(task_a, task_b),
            opks_kind=OpksKind.SKILL,
        ),
    )
    bundle = create_document_changeset(
        document_id=document_id,
        run_id=uuid4(),
        summary="更新職務名稱、職責、任務、排序、分組與 OPKS。",
        read_revision=1,
        document=document,
        changes=changes,
        existing_review_queue={},
        interview_work={},
    )
    state = {
        "document_id": str(document_id),
        "revision": 1,
        "approved_document": document.model_dump(mode="json"),
        "review_queue": {
            str(bundle.changeset_id): bundle.model_dump(mode="json")
        },
        "interview_work": {},
        "understanding": {},
        "gaps": {},
    }
    update = apply_review_command(
        state,
        action="accept_changes",
        changeset_id=bundle.changeset_id,
        action_ids=tuple(item.action_id for item in bundle.actions),
        revision=2,
    )
    approved = ApprovedJobDocument.model_validate(update["approved_document"])
    assert approved.job_title == "資深採購專員"
    assert approved.work_description == "負責採購、覆核與供應商資訊維護。"
    assert {item.duty_id: item.display_order for item in approved.duties} == {
        duty_a: 1,
        duty_b: 0,
    }
    task_by_id = {item.task_id: item for item in approved.tasks}
    assert task_by_id[task_a].duty_id == duty_b
    assert task_by_id[task_a].display_order == 1
    assert task_by_id[task_b].display_order == 0
    assert {item.kind for item in approved.opks} == {
        ApprovedOpksKind.OUTPUT,
        ApprovedOpksKind.PERFORMANCE_INDICATOR,
        ApprovedOpksKind.KNOWLEDGE,
        ApprovedOpksKind.SKILL,
    }
    assert all(item.evidence_source_ids for item in approved.opks)


def test_application_allocates_new_duty_and_task_identity_before_review() -> None:
    document_id = uuid4()
    source_id = uuid4()
    document = ApprovedJobDocument(document_id=document_id)
    duty_bundle = create_document_changeset(
        document_id=document_id,
        run_id=uuid4(),
        summary="新增採購管理職責。",
        read_revision=0,
        document=document,
        changes=(
            _change(
                source_id=source_id,
                path="/duties",
                operation=DocumentChangeOperation.ADD,
                after={"statement": "管理採購作業"},
            ),
        ),
        existing_review_queue={},
        interview_work={},
    )
    assert duty_bundle.actions[0].after["duty_id"]
    assert duty_bundle.actions[0].after["display_order"] == 0
    update = apply_review_command(
        {
            "approved_document": document.model_dump(mode="json"),
            "review_queue": {
                str(duty_bundle.changeset_id): duty_bundle.model_dump(mode="json")
            },
            "interview_work": {},
            "understanding": {},
            "gaps": {},
        },
        action="accept_changes",
        changeset_id=duty_bundle.changeset_id,
        action_ids=(duty_bundle.actions[0].action_id,),
        revision=1,
    )
    document = ApprovedJobDocument.model_validate(update["approved_document"])
    duty_id = document.duties[0].duty_id
    task_bundle = create_document_changeset(
        document_id=document_id,
        run_id=uuid4(),
        summary="新增請購任務。",
        read_revision=1,
        document=document,
        changes=(
            _change(
                source_id=source_id,
                path="/tasks",
                operation=DocumentChangeOperation.ADD,
                after={
                    "duty_id": str(duty_id),
                    "statement": "建立請購單",
                    "action": "建立",
                    "object": "請購單",
                },
            ),
        ),
        existing_review_queue=update["review_queue"],
        interview_work={},
    )
    assert task_bundle.actions[0].after["task_id"]
    assert task_bundle.actions[0].after["display_order"] == 0


def test_multiple_adds_get_collection_local_orders_and_distinct_target_keys() -> None:
    document_id = uuid4()
    source_id = uuid4()
    bundle = create_document_changeset(
        document_id=document_id,
        run_id=uuid4(),
        summary="建立職稱與兩項採購任務。",
        read_revision=0,
        document=ApprovedJobDocument(document_id=document_id),
        changes=(
            _change(
                source_id=source_id,
                path="/job_title",
                after="採購專員",
            ),
            _change(
                source_id=source_id,
                path="/tasks",
                operation=DocumentChangeOperation.ADD,
                after={
                    "statement": "確認採購需求",
                    "action": "確認",
                    "object": "採購需求",
                },
            ),
            _change(
                source_id=source_id,
                path="/tasks",
                operation=DocumentChangeOperation.ADD,
                after={
                    "statement": "追蹤採購交期",
                    "action": "追蹤",
                    "object": "採購交期",
                },
            ),
        ),
        existing_review_queue={},
        interview_work={},
    )

    task_actions = bundle.actions[1:]
    assert [action.after["display_order"] for action in task_actions] == [0, 1]
    assert len({action.target_key for action in task_actions}) == 2


def test_one_way_dependency_does_not_become_an_atomic_subgroup() -> None:
    document_id = uuid4()
    source_id = uuid4()
    document = ApprovedJobDocument(document_id=document_id)
    task_id = uuid4()
    bundle = create_document_changeset(
        document_id=document_id,
        run_id=uuid4(),
        summary="新增任務，並建議相關知識。",
        read_revision=0,
        document=document,
        changes=(
            _change(
                source_id=source_id,
                path="/tasks",
                operation=DocumentChangeOperation.ADD,
                after={
                    "task_id": str(task_id),
                    "statement": "建立請購單",
                    "action": "建立",
                    "object": "請購單",
                    "display_order": 0,
                },
            ),
            _change(
                source_id=source_id,
                path="/opks",
                operation=DocumentChangeOperation.ADD,
                after="採購流程知識",
                task_ids=(task_id,),
                opks_kind=OpksKind.KNOWLEDGE,
            ),
        ),
        existing_review_queue={},
        interview_work={},
    )
    task_action, knowledge_action = bundle.actions
    assert task_action.atomic_subgroup_id is None
    assert knowledge_action.atomic_subgroup_id is None
    assert knowledge_action.depends_on_action_ids == (task_action.action_id,)
    state = {
        "approved_document": document.model_dump(mode="json"),
        "review_queue": {
            str(bundle.changeset_id): bundle.model_dump(mode="json")
        },
        "interview_work": {},
        "understanding": {},
        "gaps": {},
    }

    first = apply_review_command(
        state,
        action="accept_changes",
        changeset_id=bundle.changeset_id,
        action_ids=(task_action.action_id,),
        revision=1,
    )
    approved = ApprovedJobDocument.model_validate(first["approved_document"])
    assert [item.task_id for item in approved.tasks] == [task_id]
    pending = DocumentChangeSet.model_validate(
        first["review_queue"][str(bundle.changeset_id)]
    )
    assert pending.actions[1].status is DocumentChangeStatus.PENDING

    second = apply_review_command(
        first,
        action="accept_changes",
        changeset_id=bundle.changeset_id,
        action_ids=(knowledge_action.action_id,),
        revision=2,
    )
    approved = ApprovedJobDocument.model_validate(second["approved_document"])
    assert approved.opks[0].task_ids == (task_id,)


def test_invalid_employee_edit_is_rejected_without_consuming_the_review() -> None:
    document_id = uuid4()
    source_id = uuid4()
    document, _duty_a, _duty_b, task_a, _task_b = _document(
        document_id,
        source_id=source_id,
    )
    bundle = create_document_changeset(
        document_id=document_id,
        run_id=uuid4(),
        summary="修改請購任務。",
        read_revision=1,
        document=document,
        changes=(
            _change(
                source_id=source_id,
                path=f"/tasks/{task_a}/statement",
                after="建立並覆核請購單",
            ),
        ),
        existing_review_queue={},
        interview_work={},
    )
    action = bundle.actions[0]
    state = {
        "approved_document": document.model_dump(mode="json"),
        "review_queue": {
            str(bundle.changeset_id): bundle.model_dump(mode="json")
        },
        "interview_work": {},
        "understanding": {},
        "gaps": {},
    }

    with pytest.raises(DocumentReviewError, match="employee-edited"):
        apply_review_command(
            state,
            action="edit_and_accept_changes",
            changeset_id=bundle.changeset_id,
            action_ids=(action.action_id,),
            revision=2,
            edited_after_by_action_id={action.action_id: 42},
        )

    original = DocumentChangeSet.model_validate(
        state["review_queue"][str(bundle.changeset_id)]
    )
    assert original.actions[0].status is DocumentChangeStatus.PENDING


@pytest.mark.parametrize("operation", [DocumentChangeOperation.MERGE, DocumentChangeOperation.SPLIT])
def test_duty_merge_and_split_are_atomic_with_task_reassignment(
    operation: DocumentChangeOperation,
) -> None:
    document_id = uuid4()
    source_id = uuid4()
    document, duty_a, duty_b, task_a, task_b = _document(
        document_id,
        source_id=source_id,
    )
    if operation is DocumentChangeOperation.MERGE:
        new_duties = (
            {
                "duty_id": str(uuid4()),
                "statement": "管理採購與供應商",
                "display_order": 0,
            },
        )
        duty_targets = (duty_a, duty_b)
    else:
        new_duties = (
            {
                "duty_id": str(uuid4()),
                "statement": "辦理請購作業",
                "display_order": 0,
            },
            {
                "duty_id": str(uuid4()),
                "statement": "維護供應商資訊",
                "display_order": 1,
            },
        )
        duty_targets = (duty_a, duty_b)
    changes = [
        _change(
            source_id=source_id,
            path="/duties",
            operation=operation,
            after=list(new_duties) if operation is DocumentChangeOperation.SPLIT else new_duties[0],
            target_ids=duty_targets,
        ),
        _change(
            source_id=source_id,
            path=f"/tasks/{task_a}/duty_id",
            operation=DocumentChangeOperation.REASSIGN,
            after=new_duties[0]["duty_id"],
            task_ids=(task_a,),
        ),
        _change(
            source_id=source_id,
            path=f"/tasks/{task_b}/duty_id",
            operation=DocumentChangeOperation.REASSIGN,
            after=new_duties[-1]["duty_id"],
            task_ids=(task_b,),
        ),
    ]
    bundle = create_document_changeset(
        document_id=document_id,
        run_id=uuid4(),
        summary="重新整理職責分組。",
        read_revision=1,
        document=document,
        changes=tuple(changes),
        existing_review_queue={},
        interview_work={},
    )
    assert len({item.atomic_subgroup_id for item in bundle.actions}) == 1
    with pytest.raises(AtomicSubgroupIncomplete):
        apply_review_command(
            {
                "approved_document": document.model_dump(mode="json"),
                "review_queue": {
                    str(bundle.changeset_id): bundle.model_dump(mode="json")
                },
                "interview_work": {},
                "understanding": {},
                "gaps": {},
            },
            action="accept_changes",
            changeset_id=bundle.changeset_id,
            action_ids=(bundle.actions[0].action_id,),
            revision=2,
        )
    update = apply_review_command(
        {
            "approved_document": document.model_dump(mode="json"),
            "review_queue": {
                str(bundle.changeset_id): bundle.model_dump(mode="json")
            },
            "interview_work": {},
            "understanding": {},
            "gaps": {},
        },
        action="accept_changes",
        changeset_id=bundle.changeset_id,
        action_ids=tuple(item.action_id for item in bundle.actions),
        revision=2,
    )
    approved = ApprovedJobDocument.model_validate(update["approved_document"])
    assert {item.duty_id for item in approved.duties} == {
        UUID(item["duty_id"]) for item in new_duties
    }


def test_stale_local_prerequisite_cannot_be_plain_accepted_with_dependent() -> None:
    document_id = uuid4()
    source_id = uuid4()
    document = ApprovedJobDocument(document_id=document_id)
    bundle = create_document_changeset(
        document_id=document_id,
        run_id=uuid4(),
        summary="具本地依賴的建議。",
        read_revision=1,
        document=document,
        changes=(
            _change(
                source_id=source_id,
                path="/duties",
                operation=DocumentChangeOperation.ADD,
                after={"statement": "管理採購作業"},
            ).model_copy(update={"change_ref": "prerequisite"}),
            _change(
                source_id=source_id,
                path="/job_title",
                after="採購專員",
            ).model_copy(
                update={
                    "change_ref": "dependent",
                    "depends_on_change_refs": ("prerequisite",),
                }
            ),
        ),
        existing_review_queue={},
        interview_work={},
    )
    prerequisite, dependent = bundle.actions
    stale_prerequisite = prerequisite.model_copy(
        update={
            "status": DocumentChangeStatus.STALE,
            "stale_reason": "前提已失效。",
        }
    )
    stale_bundle = bundle.model_copy(
        update={"actions": (stale_prerequisite, dependent)}
    )
    approved_before = document.model_dump(mode="json")
    state = {
        "approved_document": approved_before,
        "review_queue": {
            str(stale_bundle.changeset_id): stale_bundle.model_dump(mode="json")
        },
        "interview_work": {},
        "understanding": {},
        "gaps": {},
    }

    with pytest.raises(DocumentReviewError, match="pending or deferred"):
        apply_review_command(
            state,
            action="accept_changes",
            changeset_id=stale_bundle.changeset_id,
            action_ids=(stale_prerequisite.action_id, dependent.action_id),
            revision=2,
        )

    assert state["approved_document"] == approved_before


def test_revalidation_stales_only_action_with_failed_external_dependency() -> None:
    document_id = uuid4()
    source_id = uuid4()
    document = ApprovedJobDocument(document_id=document_id)
    prerequisite = create_document_changeset(
        document_id=document_id,
        run_id=uuid4(),
        summary="外部前提。",
        read_revision=1,
        document=document,
        changes=(
            _change(
                source_id=source_id,
                path="/duties",
                operation=DocumentChangeOperation.ADD,
                after={"statement": "管理採購作業"},
            ),
        ),
        existing_review_queue={},
        interview_work={},
    )
    prerequisite_action = prerequisite.actions[0]
    conditional_document = apply_document_actions(document, prerequisite.actions)
    duty_id = UUID(str(prerequisite_action.after["duty_id"]))  # type: ignore[index]
    mixed = create_document_changeset(
        document_id=document_id,
        run_id=uuid4(),
        summary="相依與獨立建議共存。",
        read_revision=1,
        document=conditional_document,
        changes=(
            _change(
                source_id=source_id,
                path=f"/duties/{duty_id}/statement",
                after="管理國內外採購作業",
            ).model_copy(
                update={
                    "depends_on_action_ids": (prerequisite_action.action_id,)
                }
            ),
            _change(
                source_id=source_id,
                path="/job_title",
                after="採購專員",
            ),
        ),
        existing_review_queue={
            str(prerequisite.changeset_id): prerequisite.model_dump(mode="json")
        },
        interview_work={},
        external_dependency_action_ids=(prerequisite_action.action_id,),
    )
    rejected_prerequisite = prerequisite.model_copy(
        update={
            "actions": (
                prerequisite_action.model_copy(
                    update={
                        "status": DocumentChangeStatus.REJECTED,
                        "rejection_reason": "這不是我的工作。",
                    }
                ),
            )
        }
    )

    updated = revalidate_review_queue(
        document,
        {
            str(rejected_prerequisite.changeset_id): rejected_prerequisite.model_dump(
                mode="json"
            ),
            str(mixed.changeset_id): mixed.model_dump(mode="json"),
        },
        stale_reason="核准文件已變更。",
    )

    updated_mixed = DocumentChangeSet.model_validate(
        updated[str(mixed.changeset_id)]
    )
    assert updated_mixed.actions[0].status is DocumentChangeStatus.STALE
    assert updated_mixed.actions[1].status is DocumentChangeStatus.PENDING


def test_revalidation_propagates_local_dependency_failure_without_touching_independent_action() -> None:
    document_id = uuid4()
    source_id = uuid4()
    document = ApprovedJobDocument(document_id=document_id)
    bundle = create_document_changeset(
        document_id=document_id,
        run_id=uuid4(),
        summary="本地依賴與獨立建議。",
        read_revision=1,
        document=document,
        changes=(
            _change(
                source_id=source_id,
                path="/duties",
                operation=DocumentChangeOperation.ADD,
                after={"statement": "管理採購作業"},
            ).model_copy(update={"change_ref": "local-root"}),
            _change(
                source_id=source_id,
                path="/job_title",
                after="採購專員",
            ).model_copy(
                update={
                    "change_ref": "local-dependent",
                    "depends_on_change_refs": ("local-root",),
                }
            ),
            _change(
                source_id=source_id,
                path="/work_description",
                after="執行採購相關工作。",
            ).model_copy(update={"change_ref": "independent"}),
        ),
        existing_review_queue={},
        interview_work={},
    )
    root, dependent, independent = bundle.actions
    rejected_root = root.model_copy(
        update={
            "status": DocumentChangeStatus.REJECTED,
            "rejection_reason": "這不是我的工作。",
        }
    )
    rejected_bundle = bundle.model_copy(
        update={"actions": (rejected_root, dependent, independent)}
    )

    updated = revalidate_review_queue(
        document,
        {str(bundle.changeset_id): rejected_bundle.model_dump(mode="json")},
        stale_reason="核准文件已變更。",
    )

    actions = DocumentChangeSet.model_validate(
        updated[str(bundle.changeset_id)]
    ).actions
    assert actions[0].status is DocumentChangeStatus.REJECTED
    assert actions[1].status is DocumentChangeStatus.STALE
    assert actions[2].status is DocumentChangeStatus.PENDING


def test_revalidation_reaches_fixed_point_after_atomic_and_three_level_cascade() -> None:
    document_id = uuid4()
    source_id = uuid4()
    document = ApprovedJobDocument(document_id=document_id)
    bundle = create_document_changeset(
        document_id=document_id,
        run_id=uuid4(),
        summary="三層依賴與原子群組。",
        read_revision=1,
        document=document,
        changes=(
            _change(
                source_id=source_id,
                path="/duties",
                operation=DocumentChangeOperation.ADD,
                after={"statement": "第一層前提"},
            ).model_copy(update={"change_ref": "level-one"}),
            _change(
                source_id=source_id,
                path="/duties",
                operation=DocumentChangeOperation.ADD,
                after={"statement": "第二層相依"},
            ).model_copy(
                update={
                    "change_ref": "level-two",
                    "depends_on_change_refs": ("level-one",),
                    "atomic_group_ref": "level-two-group",
                }
            ),
            _change(
                source_id=source_id,
                path="/duties",
                operation=DocumentChangeOperation.ADD,
                after={"statement": "第二層原子同伴"},
            ).model_copy(
                update={
                    "change_ref": "level-two-sibling",
                    "atomic_group_ref": "level-two-group",
                }
            ),
            _change(
                source_id=source_id,
                path="/job_title",
                after="採購專員",
            ).model_copy(
                update={
                    "change_ref": "level-three",
                    "depends_on_change_refs": ("level-two-sibling",),
                }
            ),
        ),
        existing_review_queue={},
        interview_work={},
    )
    level_one, level_two, atomic_sibling, level_three = bundle.actions
    rejected_level_one = level_one.model_copy(
        update={
            "status": DocumentChangeStatus.REJECTED,
            "rejection_reason": "前提不成立。",
        }
    )
    rejected_bundle = bundle.model_copy(
        update={
            "actions": (
                rejected_level_one,
                level_two,
                atomic_sibling,
                level_three,
            )
        }
    )

    updated = revalidate_review_queue(
        document,
        {str(bundle.changeset_id): rejected_bundle.model_dump(mode="json")},
        stale_reason="核准文件已變更。",
    )

    actions = DocumentChangeSet.model_validate(
        updated[str(bundle.changeset_id)]
    ).actions
    assert actions[0].status is DocumentChangeStatus.REJECTED
    assert tuple(action.status for action in actions[1:]) == (
        DocumentChangeStatus.STALE,
        DocumentChangeStatus.STALE,
        DocumentChangeStatus.STALE,
    )


def test_external_dependency_must_be_employee_accepted_before_dependent_action() -> None:
    document_id = uuid4()
    source_id = uuid4()
    document = ApprovedJobDocument(
        document_id=document_id,
        job_title="採購專員",
        work_description="執行採購作業。",
    )
    prerequisite = create_document_changeset(
        document_id=document_id,
        run_id=uuid4(),
        summary="先修訂職稱。",
        read_revision=1,
        document=document,
        changes=(
            _change(
                source_id=source_id,
                path="/job_title",
                after="資深採購專員",
            ),
        ),
        existing_review_queue={},
        interview_work={},
    )
    prerequisite_id = prerequisite.actions[0].action_id
    conditional_document = apply_document_actions(document, prerequisite.actions)
    dependent_change = _change(
        source_id=source_id,
        path="/work_description",
        after="以資深採購專員角色管理採購作業。",
    ).model_copy(update={"depends_on_action_ids": (prerequisite_id,)})
    dependent = create_document_changeset(
        document_id=document_id,
        run_id=uuid4(),
        summary="依職稱前提修訂工作描述。",
        read_revision=1,
        document=conditional_document,
        changes=(dependent_change,),
        existing_review_queue={
            str(prerequisite.changeset_id): prerequisite.model_dump(mode="json")
        },
        interview_work={},
        external_dependency_action_ids=(prerequisite_id,),
    )
    state = {
        "approved_document": document.model_dump(mode="json"),
        "review_queue": {
            str(prerequisite.changeset_id): prerequisite.model_dump(mode="json"),
            str(dependent.changeset_id): dependent.model_dump(mode="json"),
        },
        "interview_work": {},
        "understanding": {},
        "gaps": {},
    }

    with pytest.raises(ReviewDependencyUnresolved, match=str(prerequisite_id)):
        apply_review_command(
            state,
            action="accept_changes",
            changeset_id=dependent.changeset_id,
            action_ids=(dependent.actions[0].action_id,),
            revision=2,
        )

    prerequisite_accepted = apply_review_command(
        state,
        action="accept_changes",
        changeset_id=prerequisite.changeset_id,
        action_ids=(prerequisite_id,),
        revision=2,
    )
    dependent_accepted = apply_review_command(
        prerequisite_accepted,
        action="accept_changes",
        changeset_id=dependent.changeset_id,
        action_ids=(dependent.actions[0].action_id,),
        revision=3,
    )

    approved = ApprovedJobDocument.model_validate(
        dependent_accepted["approved_document"]
    )
    assert approved.job_title == "資深採購專員"
    assert approved.work_description == "以資深採購專員角色管理採購作業。"


def test_rejected_external_dependency_makes_downstream_action_stale() -> None:
    document_id = uuid4()
    source_id = uuid4()
    document = ApprovedJobDocument(document_id=document_id, job_title="採購專員")
    prerequisite = create_document_changeset(
        document_id=document_id,
        run_id=uuid4(),
        summary="先修訂職稱。",
        read_revision=1,
        document=document,
        changes=(
            _change(
                source_id=source_id,
                path="/job_title",
                after="資深採購專員",
            ),
        ),
        existing_review_queue={},
        interview_work={},
    )
    prerequisite_id = prerequisite.actions[0].action_id
    dependent = create_document_changeset(
        document_id=document_id,
        run_id=uuid4(),
        summary="依職稱前提修訂工作描述。",
        read_revision=1,
        document=apply_document_actions(document, prerequisite.actions),
        changes=(
            _change(
                source_id=source_id,
                path="/work_description",
                after="管理複雜採購案。",
            ).model_copy(update={"depends_on_action_ids": (prerequisite_id,)}),
        ),
        existing_review_queue={
            str(prerequisite.changeset_id): prerequisite.model_dump(mode="json")
        },
        interview_work={},
        external_dependency_action_ids=(prerequisite_id,),
    )

    update = apply_review_command(
        {
            "approved_document": document.model_dump(mode="json"),
            "review_queue": {
                str(prerequisite.changeset_id): prerequisite.model_dump(mode="json"),
                str(dependent.changeset_id): dependent.model_dump(mode="json"),
            },
            "interview_work": {},
            "understanding": {},
            "gaps": {},
        },
        action="reject_changes",
        changeset_id=prerequisite.changeset_id,
        action_ids=(prerequisite_id,),
        rejection_reason="這不是我的職稱。",
        revision=2,
    )

    downstream = DocumentChangeSet.model_validate(
        update["review_queue"][str(dependent.changeset_id)]
    )
    assert downstream.actions[0].status is DocumentChangeStatus.STALE
    assert "前置" in downstream.actions[0].stale_reason


def test_publication_supersession_stales_only_explicit_unresolved_actions() -> None:
    document_id = uuid4()
    source_id = uuid4()
    document = ApprovedJobDocument(document_id=document_id, job_title="採購專員")
    old = create_document_changeset(
        document_id=document_id,
        run_id=uuid4(),
        summary="舊建議。",
        read_revision=1,
        document=document,
        changes=(
            _change(
                source_id=source_id,
                path="/job_title",
                after="採購管理師",
            ),
        ),
        existing_review_queue={},
        interview_work={},
    )
    replacement = create_document_changeset(
        document_id=document_id,
        run_id=uuid4(),
        summary="新建議。",
        read_revision=1,
        document=document,
        changes=(
            _change(
                source_id=source_id,
                path="/job_title",
                after="資深採購管理師",
            ).model_copy(
                update={"supersedes_action_ids": (old.actions[0].action_id,)}
            ),
        ),
        existing_review_queue={
            str(old.changeset_id): old.model_dump(mode="json")
        },
        interview_work={},
    )

    updated = stale_superseded_review_actions(
        {str(old.changeset_id): old.model_dump(mode="json")},
        published_changeset=replacement,
    )

    stale_old = DocumentChangeSet.model_validate(updated[str(old.changeset_id)])
    assert stale_old.actions[0].status is DocumentChangeStatus.STALE
    assert "取代" in stale_old.actions[0].stale_reason
    assert replacement.actions[0].status is DocumentChangeStatus.PENDING


def test_publishing_supersession_revalidates_cross_bundle_dependencies() -> None:
    document_id = uuid4()
    source_id = uuid4()
    document = ApprovedJobDocument(document_id=document_id, job_title="採購專員")
    prerequisite = create_document_changeset(
        document_id=document_id,
        run_id=uuid4(),
        summary="前置建議。",
        read_revision=1,
        document=document,
        changes=(
            _change(source_id=source_id, path="/job_title", after="採購管理師"),
        ),
        existing_review_queue={},
        interview_work={},
    )
    prerequisite_id = prerequisite.actions[0].action_id
    dependent = create_document_changeset(
        document_id=document_id,
        run_id=uuid4(),
        summary="依賴前置的建議。",
        read_revision=1,
        document=apply_document_actions(document, prerequisite.actions),
        changes=(
            _change(
                source_id=source_id,
                path="/work_description",
                after="以採購管理師角色管理採購作業。",
            ).model_copy(update={"depends_on_action_ids": (prerequisite_id,)}),
        ),
        existing_review_queue={
            str(prerequisite.changeset_id): prerequisite.model_dump(mode="json")
        },
        interview_work={},
        external_dependency_action_ids=(prerequisite_id,),
    )
    unrelated = create_document_changeset(
        document_id=document_id,
        run_id=uuid4(),
        summary="無關建議。",
        read_revision=1,
        document=document,
        changes=(
            _change(
                source_id=source_id,
                path="/notes",
                after="供後續訪談使用。",
            ),
        ),
        existing_review_queue={
            str(prerequisite.changeset_id): prerequisite.model_dump(mode="json"),
            str(dependent.changeset_id): dependent.model_dump(mode="json"),
        },
        interview_work={},
    )
    replacement = create_document_changeset(
        document_id=document_id,
        run_id=uuid4(),
        summary="取代前置的候選。",
        read_revision=1,
        document=document,
        changes=(
            _change(source_id=source_id, path="/job_title", after="資深採購管理師").model_copy(
                update={"supersedes_action_ids": (prerequisite_id,)}
            ),
        ),
        existing_review_queue={
            str(prerequisite.changeset_id): prerequisite.model_dump(mode="json"),
            str(dependent.changeset_id): dependent.model_dump(mode="json"),
            str(unrelated.changeset_id): unrelated.model_dump(mode="json"),
        },
        interview_work={},
    )

    queue, _ = _publish_persisted_changeset(
        document_id=document_id,
        run_id=uuid4(),
        read_revision=1,
        state={
            "approved_document": document.model_dump(mode="json"),
            "review_queue": {
                str(prerequisite.changeset_id): prerequisite.model_dump(mode="json"),
                str(dependent.changeset_id): dependent.model_dump(mode="json"),
                str(unrelated.changeset_id): unrelated.model_dump(mode="json"),
            },
        },
        published_changeset=replacement,
        interview_work={},
    )

    stale_prerequisite = DocumentChangeSet.model_validate(
        queue[str(prerequisite.changeset_id)]
    ).actions[0]
    stale_dependent = DocumentChangeSet.model_validate(
        queue[str(dependent.changeset_id)]
    ).actions[0]
    pending_unrelated = DocumentChangeSet.model_validate(
        queue[str(unrelated.changeset_id)]
    ).actions[0]
    assert stale_prerequisite.status is DocumentChangeStatus.STALE
    assert "取代" in stale_prerequisite.stale_reason
    assert stale_dependent.status is DocumentChangeStatus.STALE
    assert "前置" in stale_dependent.stale_reason
    assert pending_unrelated.status is DocumentChangeStatus.PENDING
