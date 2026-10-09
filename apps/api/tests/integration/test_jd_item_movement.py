"""Relative movement uses the existing candidate owner and preserves original results."""

from dataclasses import replace
from uuid import uuid4, uuid5

import pytest
from fastapi.testclient import TestClient
from pydantic import TypeAdapter

from caliburn.features.executions.models import ExecutionStateError
from caliburn.features.interviews import queries as interviews
from caliburn.features.job_description import persistence, source_persistence, work_queries
from caliburn.features.job_description.areas import (
    AreaField,
    AreaFieldChange,
    CreateArea,
    EditJdAreas,
    InvalidAreaChangeError,
    ReviseArea,
)
from caliburn.features.job_description.capabilities import (
    CapabilityKind,
    CreateCapability,
    EditJdCapabilities,
    SetTaskCapability,
)
from caliburn.features.job_description.collaborators import CreateCollaborator, EditJdCollaborators
from caliburn.features.job_description.conditions import (
    ConditionKind,
    CreateCondition,
    EditJdConditions,
)
from caliburn.features.job_description.navigation import JdReadTargetNotFoundError, jd_read_ref
from caliburn.features.job_description.sources import (
    AddJdSource,
    InterviewSource,
    JdSourceTarget,
    ReviseJdSources,
    SourceTargetKind,
)
from caliburn.features.job_description.tasks import (
    CreateTask,
    DetailKind,
    EditJdTasks,
    InvalidTaskChangeError,
)
from caliburn.workflows.jd_candidates import JdCandidateWorkflow
from caliburn.workflows.jd_item_movement import (
    CurrentItemContainer,
    InvalidItemMovementError,
    ItemPosition,
    JdItemMovementWorkflow,
    MoveItemInput,
    MovementDetailAddition,
    MovementTextChange,
    TaskParentDestination,
)
from caliburn.workflows.memory_reads import PublishedMemoryRead
from tests.fixtures.consultant_turn import start_consultant_turn as start
from tests.fixtures.consultant_turn import transact

pytestmark = pytest.mark.postgres


def setup_movement(client):
    writer = start(client)
    candidates = JdCandidateWorkflow(client.app.state.database.sessions)
    position = client.portal.call(candidates.start, writer)

    def edit(command):
        nonlocal position
        position = client.portal.call(candidates.edit, writer, position.scope, command)

    for title in ("原職責", "新職責", "無關職責"):
        edit(EditJdAreas(uuid4(), position.revision_id, CreateArea(title, "既有範圍")))
    preview = client.portal.call(candidates.read, writer.scope)
    first, second, _ = preview.work.areas
    for area, title in ((first, "移動任務"), (second, "前項"), (second, "後項")):
        edit(
            EditJdTasks(
                uuid4(),
                position.revision_id,
                CreateTask(area.area_id, title, "原敘述", ("成果一", "成果二"), ("要求",)),
            )
        )
    edit(
        EditJdCapabilities(
            uuid4(),
            position.revision_id,
            CreateCapability(CapabilityKind.SKILL, "操作", None),
        )
    )
    preview = client.portal.call(candidates.read, writer.scope)
    task, capability = preview.work.tasks[0], preview.work.capabilities[0]
    edit(
        EditJdCapabilities(
            uuid4(),
            position.revision_id,
            SetTaskCapability(task.task_id, capability.capability_id, True),
        )
    )
    source = transact(
        client,
        lambda session: interviews.read_execution_input(
            session,
            job_file_id=writer.scope.job_file_id,
            execution_id=writer.scope.execution_id,
        ),
    )
    for target in (
        JdSourceTarget(SourceTargetKind.TASK, task.task_id),
        JdSourceTarget(SourceTargetKind.DETAIL, task.details[0].detail_id, task_id=task.task_id),
        JdSourceTarget(
            SourceTargetKind.TASK_CAPABILITY, capability.capability_id, task_id=task.task_id
        ),
    ):
        edit(
            ReviseJdSources(
                uuid4(),
                position.revision_id,
                target,
                (AddJdSource(InterviewSource(source.source_id)),),
            )
        )
    return writer, candidates, client.portal.call(candidates.read, writer.scope)


def prepare(client, writer, intent):
    workflow = JdItemMovementWorkflow(client.app.state.database.sessions)

    async def run():
        return await workflow.prepare(
            PublishedMemoryRead(writer.scope, None, 1),
            command_id=uuid4(),
            intent=intent,
        )

    return workflow, client.portal.call(run)


def source_refs(client, writer, preview):
    return transact(
        client,
        lambda session: source_persistence.read_source_references(
            session,
            writer.scope.job_file_id,
            preview.position.revision_id,
        ),
    )


def test_task_move_preserves_ids_sources_formal_head_and_replay(client: TestClient):
    writer, candidates, before = setup_movement(client)
    task, first, last = before.work.tasks
    formal = transact(
        client, lambda session: work_queries.read_work(session, writer.scope.job_file_id)
    )
    workflow, prepared = prepare(
        client,
        writer,
        MoveItemInput(
            jd_read_ref(task),
            TaskParentDestination(jd_read_ref(before.work.areas[1])),
            ItemPosition("after", jd_read_ref(first)),
        ),
    )
    assert client.portal.call(workflow.execute, writer, prepared).effect == "moved"
    after = client.portal.call(candidates.read, writer.scope)
    assert [t.task_id for t in after.work.tasks] == [first.task_id, task.task_id, last.task_id]
    moved = after.work.tasks[1]
    assert moved.details == task.details
    assert moved.content_revision_id == task.content_revision_id
    assert after.work.task_links == before.work.task_links
    assert source_refs(client, writer, after) == source_refs(client, writer, before)
    assert (
        transact(client, lambda session: work_queries.read_work(session, writer.scope.job_file_id))
        == formal
    )

    workflow, unassign = prepare(
        client,
        writer,
        MoveItemInput(
            jd_read_ref(task),
            TaskParentDestination(None),
            ItemPosition("first"),
        ),
    )
    assert client.portal.call(workflow.execute, writer, unassign).detached_from_area
    latest = client.portal.call(candidates.read, writer.scope)
    assert latest.work.tasks[0].area_id is None
    checkpoint = TypeAdapter(type(prepared))
    restored = checkpoint.validate_json(checkpoint.dump_json(prepared), strict=True)
    assert restored == prepared
    assert client.portal.call(workflow.execute, writer, restored).effect == "moved"
    assert client.portal.call(candidates.read, writer.scope) == latest


def test_cross_parent_content_is_atomic_and_replay_does_not_add_details_twice(client: TestClient):
    writer, candidates, before = setup_movement(client)
    task = before.work.tasks[0]
    source_area, destination, _ = before.work.areas
    workflow, prepared = prepare(
        client,
        writer,
        MoveItemInput(
            jd_read_ref(task),
            TaskParentDestination(jd_read_ref(destination)),
            ItemPosition("last"),
            (
                MovementTextChange(jd_read_ref(task), "description", "必要限制保留在任務"),
                MovementTextChange(jd_read_ref(task.details[0]), "text", "更正成果"),
                MovementDetailAddition(DetailKind.REQUIREMENT, "跨組仍遵守限制"),
                MovementTextChange(jd_read_ref(source_area), "scope_text", "原職責新範圍"),
                MovementTextChange(jd_read_ref(destination), "scope_text", "目的職責新範圍"),
            ),
        ),
    )
    assert client.portal.call(workflow.execute, writer, prepared).effect == "moved"
    after = client.portal.call(candidates.read, writer.scope)
    revised = next(t for t in after.work.tasks if t.task_id == task.task_id)
    assert revised.description == "必要限制保留在任務"
    assert revised.details[0].detail_id == task.details[0].detail_id
    assert revised.details[0].text == "更正成果"
    assert len(revised.details) == len(task.details) + 1
    assert after.work.areas[0].scope_text == "原職責新範圍"
    assert after.work.areas[1].scope_text == "目的職責新範圍"
    assert len(source_refs(client, writer, after)) == 3
    assert client.portal.call(workflow.execute, writer, prepared).effect == "moved"
    assert client.portal.call(candidates.read, writer.scope) == after


def test_wrong_scope_neighbor_and_content_target_do_not_change_candidate(client: TestClient):
    writer, candidates, before = setup_movement(client)
    other_writer, _, foreign = setup_movement(client)
    task = before.work.tasks[0]
    destination = before.work.areas[1]
    for intent in (
        MoveItemInput(
            jd_read_ref(foreign.work.tasks[0]), CurrentItemContainer(), ItemPosition("first")
        ),
        MoveItemInput(
            jd_read_ref(task),
            TaskParentDestination(jd_read_ref(destination)),
            ItemPosition("before", jd_read_ref(foreign.work.tasks[0])),
        ),
        MoveItemInput(
            jd_read_ref(task),
            TaskParentDestination(jd_read_ref(destination)),
            ItemPosition("first"),
            (MovementTextChange(jd_read_ref(before.work.areas[2]), "scope_text", "不可改"),),
        ),
        MoveItemInput(
            jd_read_ref(task.details[0]),
            CurrentItemContainer(),
            ItemPosition("before", jd_read_ref(task.details[-1])),
        ),
    ):
        with pytest.raises((InvalidItemMovementError, JdReadTargetNotFoundError)):
            workflow, prepared = prepare(client, writer, intent)
            client.portal.call(workflow.execute, writer, prepared)
        assert client.portal.call(candidates.read, writer.scope) == before
    workflow, prepared = prepare(
        client,
        writer,
        MoveItemInput(
            jd_read_ref(task),
            CurrentItemContainer(),
            ItemPosition("last"),
        ),
    )
    with pytest.raises(ExecutionStateError):
        client.portal.call(workflow.execute, other_writer, prepared)


def test_invalid_final_task_content_keeps_original_parent_and_sources(client: TestClient):
    writer, candidates, before = setup_movement(client)
    task = before.work.tasks[0]
    with pytest.raises(InvalidTaskChangeError):
        workflow, prepared = prepare(
            client,
            writer,
            MoveItemInput(
                jd_read_ref(task),
                TaskParentDestination(None),
                ItemPosition("last"),
                (
                    MovementTextChange(jd_read_ref(task), "title", None),
                    MovementTextChange(jd_read_ref(task), "description", None),
                ),
            ),
        )
        client.portal.call(workflow.execute, writer, prepared)
    assert client.portal.call(candidates.read, writer.scope) == before


def test_late_area_rejection_rolls_back_move_content_and_receipts(client: TestClient):
    writer, candidates, before = setup_movement(client)
    task = before.work.tasks[0]
    destination = before.work.areas[1]
    workflow, prepared = prepare(
        client,
        writer,
        MoveItemInput(
            jd_read_ref(task),
            TaskParentDestination(jd_read_ref(destination)),
            ItemPosition("last"),
            (
                MovementDetailAddition(DetailKind.OUTCOME, "不可殘留成果"),
                MovementTextChange(jd_read_ref(destination), "scope_text", "   "),
            ),
        ),
    )
    with pytest.raises(InvalidAreaChangeError):
        client.portal.call(workflow.execute, writer, prepared)
    assert client.portal.call(candidates.read, writer.scope) == before
    assert (
        transact(
            client,
            lambda session: persistence.read_operation(
                session,
                writer.scope.job_file_id,
                uuid5(prepared.command_id, "move"),
            ),
        )
        is None
    )
    fixed = replace(
        prepared,
        area_revisions=(
            ReviseArea(destination.area_id, (AreaFieldChange(AreaField.SCOPE_TEXT, "有效範圍"),)),
        ),
    )
    assert client.portal.call(workflow.execute, writer, fixed).effect == "moved"
    after = client.portal.call(candidates.read, writer.scope)
    assert len(next(t for t in after.work.tasks if t.task_id == task.task_id).details) == 4
    assert client.portal.call(workflow.execute, writer, fixed).effect == "moved"
    assert client.portal.call(candidates.read, writer.scope) == after


@pytest.mark.parametrize("kind", ["area", "detail", "capability", "collaborator", "condition"])
def test_each_collection_reorders_only_its_own_group(client: TestClient, kind: str):
    writer, candidates, before = setup_movement(client)
    for label in ("一", "二"):
        position = client.portal.call(candidates.read, writer.scope).position
        if kind == "capability":
            command = EditJdCapabilities(
                uuid4(),
                position.revision_id,
                CreateCapability(CapabilityKind.KNOWLEDGE, label, None),
            )
        elif kind == "collaborator":
            command = EditJdCollaborators(
                uuid4(), position.revision_id, CreateCollaborator(label, None)
            )
        elif kind == "condition":
            command = EditJdConditions(
                uuid4(), position.revision_id, CreateCondition(ConditionKind.SCHEDULE_TRAVEL, label)
            )
        else:
            continue
        client.portal.call(candidates.edit, writer, position.scope, command)
    before = client.portal.call(candidates.read, writer.scope)

    def collection(work):
        if kind == "area":
            return work.areas
        if kind == "detail":
            return tuple(d for d in work.tasks[0].details if d.kind == DetailKind.OUTCOME)
        if kind == "capability":
            return tuple(c for c in work.capabilities if c.kind == CapabilityKind.KNOWLEDGE)
        if kind == "collaborator":
            return work.collaborators
        return work.conditions

    original = collection(before.work)
    workflow, prepared = prepare(
        client,
        writer,
        MoveItemInput(
            jd_read_ref(original[-1]),
            CurrentItemContainer(),
            ItemPosition("before", jd_read_ref(original[0])),
        ),
    )
    assert client.portal.call(workflow.execute, writer, prepared).effect == "moved"
    after = client.portal.call(candidates.read, writer.scope)
    assert collection(after.work) == (original[-1], *original[:-1])
    unchanged_refs = source_refs(client, writer, before)
    actual_refs = source_refs(client, writer, after)
    assert [(r.citation_id, r.target, r.source) for r in actual_refs] == [
        (r.citation_id, r.target, r.source) for r in unchanged_refs
    ]
    workflow, no_op = prepare(
        client,
        writer,
        MoveItemInput(
            jd_read_ref(original[-1]),
            CurrentItemContainer(),
            ItemPosition("first"),
        ),
    )
    assert client.portal.call(workflow.execute, writer, no_op).effect == "unchanged"
    assert client.portal.call(candidates.read, writer.scope) == after
