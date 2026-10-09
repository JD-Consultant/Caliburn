"""One create_jd_item intent owns both its content and precise sources, never the formal JD."""

from collections.abc import Awaitable, Callable
from dataclasses import replace
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.features.executions import service as executions
from caliburn.features.executions.models import (
    ExecutionKind,
    ExecutionScope,
    ExecutionStateError,
    ExecutionStatus,
    ExecutionWriter,
)
from caliburn.features.interviews import queries as interviews
from caliburn.features.interviews.models import InterviewScopeError
from caliburn.features.job_description import source_persistence, work_queries
from caliburn.features.job_description.areas import CreateArea, ResponsibilityArea
from caliburn.features.job_description.capabilities import CapabilityKind, CreateCapability
from caliburn.features.job_description.collaborators import CreateCollaborator
from caliburn.features.job_description.conditions import ConditionKind, CreateCondition
from caliburn.features.job_description.models import JdCommandConflictError, StaleJdRevisionError
from caliburn.features.job_description.navigation import jd_read_ref, resolve_jd_read_ref
from caliburn.features.job_description.sources import (
    InterviewSource,
    InvalidJdSourceError,
    SourceTargetKind,
)
from caliburn.workflows.consultant_completion import ConsultantCompletionWorkflow
from caliburn.workflows.jd_candidates import JdCandidateWorkflow
from caliburn.workflows.jd_item_creation import (
    CreateItemInput,
    ItemCreation,
    JdItemCreationWorkflow,
)
from caliburn.workflows.jd_sources import CurrentInputSourceSelection, InterviewSourceSelection
from caliburn.workflows.jd_task_writes import (
    CreateTaskInput,
    JdTaskWriteWorkflow,
    TaskCapabilityInput,
)
from caliburn.workflows.memory_reads import PublishedMemoryRead

pytestmark = pytest.mark.postgres


def transact[T](client: TestClient, operation: Callable[[AsyncSession], Awaitable[T]]) -> T:
    async def run() -> T:
        async with client.app.state.database.sessions.begin() as session:
            return await operation(session)

    return client.portal.call(run)


def start_turn(client: TestClient) -> tuple[ExecutionWriter, PublishedMemoryRead]:
    created = client.post(
        "/api/job-files",
        json={"command_id": str(uuid4()), "display_name": "分組來源", "employee_name": "合成人員"},
    ).json()
    file_id = UUID(created["job_file_id"])
    accepted = client.post(
        f"/api/job-files/{file_id}/inputs",
        json={
            "command_id": str(uuid4()),
            "text": "我負責網站交付，與設計師合作，使用介面知識與技能。",
        },
    ).json()
    scope = ExecutionScope(file_id, UUID(accepted["execution_id"]), ExecutionKind.CONSULTANT_TURN)
    writer = transact(client, lambda s: executions.claim_writer(s, scope, writer_id=uuid4()))
    candidates = JdCandidateWorkflow(client.app.state.database.sessions)
    client.portal.call(candidates.start, writer)
    return writer, PublishedMemoryRead(scope, None, 1)


@pytest.mark.parametrize(
    ("item", "target_kind", "ref_prefix"),
    [
        (CreateArea("網站交付", "維護及交付網站"), SourceTargetKind.AREA, "area_"),
        (
            CreateCapability(CapabilityKind.KNOWLEDGE, "介面", "瀏覽器介面知識"),
            SourceTargetKind.CAPABILITY,
            "knowledge_",
        ),
        (
            CreateCapability(CapabilityKind.SKILL, "介面", "實作互動介面"),
            SourceTargetKind.CAPABILITY,
            "skill_",
        ),
        (
            CreateCollaborator("設計師", "核對互動設計"),
            SourceTargetKind.COLLABORATOR,
            "collaborator_",
        ),
        (
            CreateCondition(ConditionKind.WORK_ENVIRONMENT, "在辦公室工作"),
            SourceTargetKind.CONDITION,
            "condition_",
        ),
    ],
)
def test_item_and_own_source_are_private_and_replay_original_after_later_create(
    client: TestClient, item: ItemCreation, target_kind: SourceTargetKind, ref_prefix: str
) -> None:
    writer, binding = start_turn(client)
    sessions = client.app.state.database.sessions
    candidates = JdCandidateWorkflow(sessions)
    workflow = JdItemCreationWorkflow(sessions)
    formal_before = transact(client, lambda s: work_queries.read_work(s, writer.scope.job_file_id))

    async def prepare():
        return await workflow.prepare(
            binding,
            command_id=uuid4(),
            intent=CreateItemInput(item, (CurrentInputSourceSelection(),)),
        )

    prepared = client.portal.call(prepare)
    first_result = client.portal.call(workflow.execute, writer, prepared)
    first = client.portal.call(candidates.read, writer.scope)
    first_ref = jd_read_ref(first_result.created_item)
    assert first_ref.startswith(ref_prefix)
    original = resolve_jd_read_ref(first.work, first_ref)
    references = transact(
        client,
        lambda s: source_persistence.read_source_references(
            s, writer.scope.job_file_id, first.position.revision_id
        ),
    )
    original_input = transact(
        client,
        lambda s: interviews.read_execution_input(
            s, job_file_id=writer.scope.job_file_id, execution_id=writer.scope.execution_id
        ),
    )
    assert len(references) == 1
    assert references[0].target.kind == target_kind
    assert references[0].target.item_id.hex == first_ref.rsplit("_", 1)[1]
    assert references[0].source == InterviewSource(original_input.source_id)
    assert not references[0].needs_review
    assert (
        transact(client, lambda s: work_queries.read_work(s, writer.scope.job_file_id))
        == formal_before
    )

    # Same text in a new operation is a new identity, appended by the original owner.
    later_prepared = client.portal.call(prepare)
    later_result = client.portal.call(workflow.execute, writer, later_prepared)
    assert later_result != first_result
    latest = client.portal.call(candidates.read, writer.scope)
    assert resolve_jd_read_ref(latest.work, first_ref) == original
    collection = next(
        group
        for group in (
            latest.work.areas,
            latest.work.capabilities,
            latest.work.collaborators,
            latest.work.conditions,
        )
        if original in group
    )
    assert collection[0] == original
    assert collection[1] == resolve_jd_read_ref(latest.work, jd_read_ref(later_result.created_item))
    assert client.portal.call(workflow.execute, writer, prepared) == first_result
    assert client.portal.call(candidates.read, writer.scope) == latest
    with pytest.raises(JdCommandConflictError):
        client.portal.call(
            workflow.execute, writer, replace(prepared, item=CreateArea("不同意圖", None))
        )
    assert client.portal.call(candidates.read, writer.scope) == latest


def test_source_write_exception_rolls_back_content_sources_and_original_operations(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from caliburn.features.job_description import source_persistence

    writer, binding = start_turn(client)
    sessions = client.app.state.database.sessions
    candidates = JdCandidateWorkflow(sessions)
    workflow = JdItemCreationWorkflow(sessions)
    before = client.portal.call(candidates.read, writer.scope)

    async def prepare():
        return await workflow.prepare(
            binding,
            command_id=uuid4(),
            intent=CreateItemInput(CreateArea("網站交付", None), (CurrentInputSourceSelection(),)),
        )

    prepared = client.portal.call(prepare)
    real_revise = source_persistence.insert_source_references

    async def fail_after_real_source_write(*args, **kwargs):
        await real_revise(*args, **kwargs)
        raise RuntimeError("synthetic failure after source insert")

    with monkeypatch.context() as patch:
        patch.setattr(source_persistence, "insert_source_references", fail_after_real_source_write)
        with pytest.raises(RuntimeError, match="synthetic failure"):
            client.portal.call(workflow.execute, writer, prepared)
    assert client.portal.call(candidates.read, writer.scope) == before
    result = client.portal.call(workflow.execute, writer, prepared)
    assert result.effect == "created" and isinstance(result.created_item, ResponsibilityArea)
    assert len(client.portal.call(candidates.read, writer.scope).work.areas) == 1


def test_cancel_and_replaced_writer_cannot_create_or_replay_a_candidate_item(
    client: TestClient,
) -> None:
    writer, binding = start_turn(client)
    sessions = client.app.state.database.sessions
    candidates = JdCandidateWorkflow(sessions)
    workflow = JdItemCreationWorkflow(sessions)
    before = client.portal.call(candidates.read, writer.scope)

    async def prepare():
        return await workflow.prepare(
            binding,
            command_id=uuid4(),
            intent=CreateItemInput(CreateArea("網站交付", None), (CurrentInputSourceSelection(),)),
        )

    prepared = client.portal.call(prepare)
    other_writer, _ = start_turn(client)
    with pytest.raises(ExecutionStateError):
        client.portal.call(workflow.execute, other_writer, prepared)
    replacement = transact(
        client,
        lambda s: executions.claim_writer(
            s, writer.scope, writer_id=uuid4(), replaces_writer_id=writer.writer_id
        ),
    )
    with pytest.raises(ExecutionStateError):
        client.portal.call(workflow.execute, writer, prepared)
    assert client.portal.call(candidates.read, writer.scope) == before
    result = client.portal.call(workflow.execute, replacement, prepared)
    assert result.effect == "created" and isinstance(result.created_item, ResponsibilityArea)
    completion = ConsultantCompletionWorkflow(sessions)
    client.portal.call(completion.stop, replacement, ExecutionStatus.CANCELLED)
    with pytest.raises(ExecutionStateError):
        client.portal.call(workflow.execute, replacement, prepared)
    with pytest.raises(ExecutionStateError):
        client.portal.call(prepare)
    formal = transact(client, lambda s: work_queries.read_work(s, writer.scope.job_file_id))
    assert formal.areas == ()
    assert (
        transact(
            client,
            lambda s: source_persistence.read_source_references(
                s, writer.scope.job_file_id, formal.revision_id
            ),
        )
        == ()
    )


def test_invalid_source_or_stale_preparation_never_partially_creates(client: TestClient) -> None:
    writer, binding = start_turn(client)
    sessions = client.app.state.database.sessions
    candidates = JdCandidateWorkflow(sessions)
    workflow = JdItemCreationWorkflow(sessions)
    before = client.portal.call(candidates.read, writer.scope)

    async def prepare(sources=()):
        return await workflow.prepare(
            binding,
            command_id=uuid4(),
            intent=CreateItemInput(CreateArea("網站交付", None), sources),
        )

    with pytest.raises(InterviewScopeError):
        client.portal.call(prepare, (CurrentInputSourceSelection(), InterviewSourceSelection(2)))
    with pytest.raises(InvalidJdSourceError):
        client.portal.call(prepare, (CurrentInputSourceSelection(), CurrentInputSourceSelection()))
    assert client.portal.call(candidates.read, writer.scope) == before
    first, stale = client.portal.call(prepare), client.portal.call(prepare)
    client.portal.call(workflow.execute, writer, first)
    latest = client.portal.call(candidates.read, writer.scope)
    with pytest.raises(StaleJdRevisionError):
        client.portal.call(workflow.execute, writer, stale)
    assert client.portal.call(candidates.read, writer.scope) == latest


def test_created_area_and_shared_skill_refs_work_with_existing_task_creation(
    client: TestClient,
) -> None:
    writer, binding = start_turn(client)
    sessions = client.app.state.database.sessions
    items = JdItemCreationWorkflow(sessions)
    tasks = JdTaskWriteWorkflow(sessions)

    async def create(item: ItemCreation):
        prepared = await items.prepare(binding, command_id=uuid4(), intent=CreateItemInput(item))
        return jd_read_ref((await items.execute(writer, prepared)).created_item)

    area_ref = client.portal.call(create, CreateArea("網站交付", None))
    skill_ref = client.portal.call(create, CreateCapability(CapabilityKind.SKILL, "介面實作", None))

    async def create_task():
        prepared = await tasks.prepare(
            binding,
            command_id=uuid4(),
            intent=CreateTaskInput(
                area_ref,
                "製作網站頁面",
                None,
                required_skills=(TaskCapabilityInput(skill_ref),),
            ),
        )
        return await tasks.execute(writer, prepared)

    result = client.portal.call(create_task)
    preview = client.portal.call(JdCandidateWorkflow(sessions).read, writer.scope)
    assert len(preview.work.areas) == len(preview.work.capabilities) == len(preview.work.tasks) == 1
    assert result.effect == "created" and result.created_item == preview.work.tasks[0]
    assert preview.work.tasks[0].area_id == preview.work.areas[0].area_id
    assert preview.work.task_links[0].capability_id == preview.work.capabilities[0].capability_id
