from __future__ import annotations

from uuid import UUID

import pytest
from langgraph.store.memory import InMemoryStore

from app.consultant.state import ApprovedJobDocument, ApprovedTask, initial_thread_state
from app.consultant.views import snapshot_from_state
from app.consultant.workspace_resources import (
    apply_pending_task_competency_levels,
)
from app.consultant.workspace_state import (
    PendingTaskCompetencyLevels,
    StoreBackedWorkspace,
)


DOCUMENT_ID = UUID("00000000-0000-0000-0000-000000000701")
APPROVED_TASK_ID = UUID("00000000-0000-0000-0000-000000000702")
PENDING_TASK_ID = UUID("00000000-0000-0000-0000-000000000703")


def _task(task_id: UUID, statement: str, level: int | None) -> ApprovedTask:
    return ApprovedTask(
        task_id=task_id,
        statement=statement,
        action="整理",
        object="資料",
        display_order=0,
        competency_level=level,
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
