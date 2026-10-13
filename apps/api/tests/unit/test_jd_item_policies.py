"""Item selection and related-change rules are testable without sessions or execution state."""

from dataclasses import replace
from uuid import uuid4

import pytest

from caliburn.features.job_description.areas import ResponsibilityArea
from caliburn.features.job_description.capabilities import (
    Capability,
    CapabilityInUseError,
    CapabilityKind,
    DeleteCapability,
    TaskCapabilityLink,
)
from caliburn.features.job_description.capability_changes import apply_capability_change
from caliburn.features.job_description.item_deletion import prepare_item_deletion
from caliburn.features.job_description.item_movement import (
    CurrentItemContainer,
    InvalidItemMovementError,
    ItemPosition,
    MoveItemInput,
    MovementTextChange,
    TaskParentDestination,
    prepare_item_movement,
)
from caliburn.features.job_description.item_revision import (
    InvalidItemRevisionError,
    RemoveItemDetail,
    ReviseItemDetail,
    ReviseItemInput,
    bind_item_sources,
    prepare_item_revision,
    select_item_citation,
)
from caliburn.features.job_description.navigation import jd_read_ref
from caliburn.features.job_description.sources import (
    AddJdSource,
    InterviewSource,
    InvalidJdSourceError,
    JdSourceReference,
    JdSourceTarget,
    SourceTargetKind,
)
from caliburn.features.job_description.tasks import DetailKind, MoveTask, TaskDetail, WorkTask
from caliburn.features.job_description.work_models import JdWorkRevision


@pytest.fixture
def work():
    first = ResponsibilityArea(uuid4(), uuid4(), "庫存", "管理庫存")
    second = ResponsibilityArea(uuid4(), uuid4(), "報表", "提供報表")
    tasks = tuple(
        WorkTask(
            uuid4(),
            uuid4(),
            area.area_id,
            title,
            None,
            (TaskDetail(uuid4(), DetailKind.OUTCOME, "清楚的成果"),),
        )
        for area, title in ((first, "盤點"), (second, "回報"))
    )
    capability = Capability(uuid4(), uuid4(), CapabilityKind.KNOWLEDGE, "庫存知識", None)
    return JdWorkRevision(
        uuid4(),
        (first, second),
        tasks,
        (capability,),
        (TaskCapabilityLink(tasks[0].task_id, capability.capability_id),),
        (),
        (),
    )


def test_move_to_new_parent_prepares_only_related_changes_and_destination_order(work):
    task, neighbor = work.tasks
    destination = work.areas[1]
    prepared = prepare_item_movement(
        work,
        MoveItemInput(
            jd_read_ref(task),
            TaskParentDestination(jd_read_ref(destination)),
            ItemPosition("before", jd_read_ref(neighbor)),
            (MovementTextChange(jd_read_ref(destination), "scope_text", "報表與盤點"),),
        ),
    )
    assert prepared.movement == MoveTask(task.task_id, destination.area_id, neighbor.task_id, ())
    assert prepared.area_revisions[0].area_id == destination.area_id
    assert prepared.area_revisions[0].changes[0].value == "報表與盤點"
    assert not prepared.detached_from_area


def test_move_rejects_a_neighbor_outside_the_destination_group(work):
    with pytest.raises(InvalidItemMovementError, match="same-kind neighbour"):
        prepare_item_movement(
            work,
            MoveItemInput(
                jd_read_ref(work.tasks[0]),
                CurrentItemContainer(),
                ItemPosition("before", jd_read_ref(work.tasks[1])),
            ),
        )


def test_move_rejects_unrelated_task_content_and_preserves_reorder_content(work):
    for destination, ref in (
        (TaskParentDestination(jd_read_ref(work.areas[1])), jd_read_ref(work.tasks[1])),
        (CurrentItemContainer(), jd_read_ref(work.tasks[0])),
    ):
        with pytest.raises(InvalidItemMovementError):
            prepare_item_movement(
                work,
                MoveItemInput(
                    jd_read_ref(work.tasks[0]),
                    destination,
                    ItemPosition("last"),
                    (MovementTextChange(ref, "title", "改名"),),
                ),
            )


def test_delete_preparation_and_owner_application_reject_the_same_used_capability(work):
    capability = work.capabilities[0]
    with pytest.raises(CapabilityInUseError, match="still linked"):
        prepare_item_deletion(work, command_id=uuid4(), read_ref=jd_read_ref(capability))
    with pytest.raises(CapabilityInUseError, match="still linked"):
        apply_capability_change(
            work.capabilities,
            work.task_links,
            tuple(t.task_id for t in work.tasks),
            DeleteCapability(capability.capability_id),
        )
    command, detached = prepare_item_deletion(
        replace(work, task_links=()), command_id=uuid4(), read_ref=jd_read_ref(capability)
    )
    assert command.change == DeleteCapability(capability.capability_id)
    assert detached == 0


def test_revision_rejects_another_tasks_detail_and_keeps_shared_evidence_after_detail_removal(work):
    task, other = work.tasks
    with pytest.raises(InvalidItemRevisionError, match="belong to the selected task"):
        prepare_item_revision(
            work,
            ReviseItemInput(
                jd_read_ref(task), (ReviseItemDetail(jd_read_ref(other.details[0]), "新成果"),)
            ),
        )
    detail = task.details[0]
    prepared = prepare_item_revision(
        work, ReviseItemInput(jd_read_ref(task), (RemoveItemDetail(jd_read_ref(detail)),))
    )
    target = JdSourceTarget(SourceTargetKind.TASK, task.task_id)
    changes = [AddJdSource(InterviewSource(uuid4()))]
    assert prepared.content is not None
    assert bind_item_sources({target: changes})[0].target == target


def test_existing_citation_is_selected_only_with_its_original_target(work):
    target = JdSourceTarget(SourceTargetKind.TASK, work.tasks[0].task_id)
    reference = JdSourceReference(uuid4(), target, InterviewSource(uuid4()))
    citation = f"citation_{reference.citation_id.hex}"
    assert select_item_citation((reference,), target, citation) == reference
    with pytest.raises(InvalidJdSourceError, match="selected source target"):
        select_item_citation(
            (reference,), JdSourceTarget(SourceTargetKind.TASK, work.tasks[1].task_id), citation
        )
