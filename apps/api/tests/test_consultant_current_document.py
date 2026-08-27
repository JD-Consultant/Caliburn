from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from langgraph.store.memory import InMemoryStore

from app.consultant.state import (
    ApprovedJobDocument,
    ApprovedOpksItem,
    ApprovedOpksKind,
    ApprovedTask,
    initial_thread_state,
)
from app.consultant.current_document import (
    attach_employee_source_to_current_edit,
    derive_current_document_edit,
)
from app.consultant.state import (
    DocumentChangeSet,
    DocumentPatchAction,
    DocumentPatchOperation,
    DocumentPathRead,
)
from app.consultant.views import snapshot_from_state
from app.consultant.workspace_resources import (
    apply_pending_task_competency_levels,
)
from app.consultant.workspace_state import (
    PendingTaskCompetencyLevels,
    StoreBackedWorkspace,
)
from app.consultant.workspace_review import (
    WorkspaceReviewGroup,
    WorkspaceReviewProjection,
)


DOCUMENT_ID = UUID("00000000-0000-0000-0000-000000000701")
APPROVED_TASK_ID = UUID("00000000-0000-0000-0000-000000000702")
PENDING_TASK_ID = UUID("00000000-0000-0000-0000-000000000703")
SOURCE_ID = UUID("00000000-0000-0000-0000-000000000704")


def _task(task_id: UUID, statement: str, level: int | None) -> ApprovedTask:
    return ApprovedTask(
        task_id=task_id,
        statement=statement,
        action="整理",
        object="資料",
        display_order=0,
        competency_level=level,
    )


def _review(*actions: DocumentPatchAction) -> WorkspaceReviewProjection:
    if not actions:
        return WorkspaceReviewProjection(workspace_digest="a" * 64)
    changeset = DocumentChangeSet(
        changeset_id=uuid4(),
        summary="AI 待審修改",
        actions=tuple(actions),
        source_ids=(SOURCE_ID,),
        created_revision=0,
    )
    return WorkspaceReviewProjection(
        workspace_digest="a" * 64,
        groups=(
            WorkspaceReviewGroup(
                changeset=changeset,
                group_digest="b" * 64,
                semantic_fingerprint="c" * 64,
                evidence_digest="d" * 64,
                employee_request_digest="e" * 64,
                boundary_digest="f" * 64,
            ),
        ),
    )


def _pending_task_statement_action(
    *,
    before: str,
    after: str,
) -> DocumentPatchAction:
    return DocumentPatchAction(
        action_id=uuid4(),
        operation=DocumentPatchOperation.REVISE,
        path=f"/tasks/{APPROVED_TASK_ID}/statement",
        target_key=str(APPROVED_TASK_ID),
        before=before,
        after=after,
        source_ids=(SOURCE_ID,),
        read_set=(
            DocumentPathRead(
                path=f"/tasks/{APPROVED_TASK_ID}/statement",
                value_sha256="0" * 64,
            ),
        ),
    )


def test_checkpoint_snapshot_does_not_guess_a_store_owned_current_document() -> None:
    snapshot = snapshot_from_state(initial_thread_state(DOCUMENT_ID))

    assert snapshot.current_document is None


def test_pending_task_level_overlay_only_applies_to_ai_new_tasks() -> None:
    approved = ApprovedJobDocument(
        document_id=DOCUMENT_ID,
        tasks=(_task(APPROVED_TASK_ID, "核准工作", 4),),
    )
    current = approved.model_copy(
        update={
            "tasks": (
                approved.tasks[0],
                _task(PENDING_TASK_ID, "AI 待審工作", None),
            )
        }
    )

    projected = apply_pending_task_competency_levels(
        current,
        approved_document=approved,
        handle_registry={
            "task-001": APPROVED_TASK_ID,
            "task-002": PENDING_TASK_ID,
        },
        pending_levels=PendingTaskCompetencyLevels(
            by_task_handle={
                "task-001": 2,
                "task-002": 3,
                "task-999": 5,
            }
        ),
    )

    assert projected.tasks[0].competency_level == 4
    assert projected.tasks[1].competency_level == 3


@pytest.mark.asyncio
async def test_pending_task_level_metadata_round_trips_and_prunes_removed_handles() -> None:
    workspace = StoreBackedWorkspace(
        store=InMemoryStore(),
        document_id=DOCUMENT_ID,
    )
    levels = PendingTaskCompetencyLevels(
        by_task_handle={"task-002": 3, "task-removed": 2}
    )

    await workspace.replace_pending_task_competency_levels(levels)
    assert await workspace.read_pending_task_competency_levels() == levels

    pruned = await workspace.prune_pending_task_competency_levels(
        retained_task_handles={"task-002"}
    )

    assert pruned == PendingTaskCompetencyLevels(
        by_task_handle={"task-002": 3}
    )
    assert await workspace.read_pending_task_competency_levels() == pruned


def test_current_edit_immediately_approves_an_ordinary_scalar_change() -> None:
    approved = ApprovedJobDocument(document_id=DOCUMENT_ID, job_title="採購專員")
    submitted = approved.model_copy(update={"job_title": "資深採購專員"})

    plan = derive_current_document_edit(
        approved=approved,
        current=approved,
        submitted=submitted,
        workspace_review=_review(),
        task_handle_by_id={},
    )

    assert plan.approved_after.job_title == "資深採購專員"
    assert plan.current_after.job_title == "資深採購專員"
    assert plan.approved_paths == ("/job_title",)
    assert plan.pending_paths == ()
    assert plan.employee_source_text == "資深採購專員"
    assert plan.source_positions[0].document_path == "/job_title"
    assert (plan.source_positions[0].start, plan.source_positions[0].end) == (
        0,
        len("資深採購專員"),
    )


def test_current_edit_keeps_an_employee_edit_of_ai_after_state_pending() -> None:
    approved = ApprovedJobDocument(
        document_id=DOCUMENT_ID,
        tasks=(_task(APPROVED_TASK_ID, "核准內容", 4),),
    )
    current = approved.model_copy(
        update={"tasks": (_task(APPROVED_TASK_ID, "AI 待審內容", 4),)}
    )
    submitted = current.model_copy(
        update={"tasks": (_task(APPROVED_TASK_ID, "員工調整後內容", 4),)}
    )

    plan = derive_current_document_edit(
        approved=approved,
        current=current,
        submitted=submitted,
        workspace_review=_review(
            _pending_task_statement_action(
                before="核准內容",
                after="AI 待審內容",
            )
        ),
        task_handle_by_id={APPROVED_TASK_ID: "task-001"},
    )

    assert plan.approved_after.tasks[0].statement == "核准內容"
    assert plan.current_after.tasks[0].statement == "員工調整後內容"
    assert plan.pending_paths == (
        f"/tasks/{APPROVED_TASK_ID}/statement",
    )
    assert plan.approved_paths == ()


def test_current_edit_splits_mixed_ordinary_and_pending_changes_server_side() -> None:
    approved = ApprovedJobDocument(
        document_id=DOCUMENT_ID,
        notes="舊備註",
        tasks=(_task(APPROVED_TASK_ID, "核准內容", 4),),
    )
    current = approved.model_copy(
        update={"tasks": (_task(APPROVED_TASK_ID, "AI 待審內容", 4),)}
    )
    submitted = current.model_copy(
        update={
            "notes": "員工新備註",
            "tasks": (_task(APPROVED_TASK_ID, "員工調整後內容", 4),),
        }
    )

    plan = derive_current_document_edit(
        approved=approved,
        current=current,
        submitted=submitted,
        workspace_review=_review(
            _pending_task_statement_action(
                before="核准內容",
                after="AI 待審內容",
            )
        ),
        task_handle_by_id={APPROVED_TASK_ID: "task-001"},
    )

    assert plan.approved_after.notes == "員工新備註"
    assert plan.approved_after.tasks[0].statement == "核准內容"
    assert plan.current_after.notes == "員工新備註"
    assert plan.current_after.tasks[0].statement == "員工調整後內容"
    assert plan.approved_paths == ("/notes",)
    assert plan.pending_paths == (
        f"/tasks/{APPROVED_TASK_ID}/statement",
    )


@pytest.mark.parametrize("tamper", ["stable_id", "relationship"])
def test_current_edit_rejects_full_document_identity_or_relationship_tampering(
    tamper: str,
) -> None:
    approved = ApprovedJobDocument(
        document_id=DOCUMENT_ID,
        tasks=(_task(APPROVED_TASK_ID, "核准內容", 4),),
    )
    replacement = (
        _task(uuid4(), "核准內容", 4)
        if tamper == "stable_id"
        else approved.tasks[0].model_copy(update={"duty_id": uuid4()})
    )
    submitted = approved.model_copy(update={"tasks": (replacement,)})

    with pytest.raises(ValueError, match="stable identity|relationship"):
        derive_current_document_edit(
            approved=approved,
            current=approved,
            submitted=submitted,
            workspace_review=_review(),
            task_handle_by_id={APPROVED_TASK_ID: "task-001"},
        )


def test_ai_new_task_level_stays_in_employee_metadata_until_acceptance() -> None:
    pending_task = _task(PENDING_TASK_ID, "AI 新工作", None)
    approved = ApprovedJobDocument(document_id=DOCUMENT_ID)
    current = approved.model_copy(update={"tasks": (pending_task,)})
    submitted = current.model_copy(
        update={
            "tasks": (pending_task.model_copy(update={"competency_level": 3}),)
        }
    )
    add_action = DocumentPatchAction(
        action_id=uuid4(),
        operation=DocumentPatchOperation.ADD,
        path="/tasks",
        target_key="task-002",
        before=None,
        after=pending_task.model_dump(mode="json"),
        source_ids=(SOURCE_ID,),
        read_set=(
            DocumentPathRead(path="/tasks", value_sha256="0" * 64),
        ),
    )

    plan = derive_current_document_edit(
        approved=approved,
        current=current,
        submitted=submitted,
        workspace_review=_review(add_action),
        task_handle_by_id={PENDING_TASK_ID: "task-002"},
    )

    assert plan.approved_after.tasks == ()
    assert plan.current_after.tasks[0].competency_level == 3
    assert plan.pending_task_competency_levels == PendingTaskCompetencyLevels(
        by_task_handle={"task-002": 3}
    )
    assert plan.pending_paths == (
        f"/tasks/{PENDING_TASK_ID}/competency_level",
    )


def test_employee_source_is_attached_only_to_the_edited_pending_opks_after_state() -> None:
    item_id = uuid4()
    employee_source_id = uuid4()
    approved = ApprovedJobDocument(
        document_id=DOCUMENT_ID,
        opks=(
            ApprovedOpksItem(
                item_id=item_id,
                kind=ApprovedOpksKind.ATTITUDE,
                text="原始內容",
                display_order=0,
                evidence_source_ids=(SOURCE_ID,),
            ),
        ),
    )
    current = approved.model_copy(
        update={
            "opks": (
                approved.opks[0].model_copy(update={"text": "AI 待審內容"}),
            )
        }
    )
    submitted = current.model_copy(
        update={
            "opks": (
                current.opks[0].model_copy(update={"text": "員工修改內容"}),
            )
        }
    )
    action = DocumentPatchAction(
        action_id=uuid4(),
        operation=DocumentPatchOperation.REVISE,
        path=f"/opks/{item_id}/text",
        target_key=str(item_id),
        before="原始內容",
        after="AI 待審內容",
        source_ids=(SOURCE_ID,),
        read_set=(
            DocumentPathRead(
                path=f"/opks/{item_id}/text",
                value_sha256="0" * 64,
            ),
        ),
    )

    plan = attach_employee_source_to_current_edit(
        derive_current_document_edit(
            approved=approved,
            current=current,
            submitted=submitted,
            workspace_review=_review(action),
            task_handle_by_id={},
        ),
        employee_source_id,
    )

    assert plan.approved_after.opks[0].evidence_source_ids == (SOURCE_ID,)
    assert plan.current_after.opks[0].evidence_source_ids == (
        SOURCE_ID,
        employee_source_id,
    )
