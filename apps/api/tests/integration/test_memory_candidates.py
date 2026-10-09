"""One mutable working set, fixed publication and original-operation recovery."""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import replace
from uuid import UUID, uuid4

import psycopg
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.adapters.database import Database
from caliburn.features.executions import service as executions
from caliburn.features.executions.models import (
    ExecutionKind,
    ExecutionScope,
    ExecutionStateError,
    ExecutionStatus,
    ExecutionWriter,
    StaleWriterError,
)
from caliburn.features.interviews.models import InterviewReadError
from caliburn.features.work_memory import candidate_lifecycle
from caliburn.features.work_memory.candidates import (
    CreateMemoryObject,
    DeleteMemoryObject,
    MemoryBatchPosition,
    MemoryCandidateStateError,
    MemoryCommandConflictError,
    MemoryPermissionError,
    ReviseMemoryObject,
)
from caliburn.features.work_memory.models import (
    MemoryContent,
    MemoryContentChanges,
)
from caliburn.features.work_memory.revisions import (
    MemoryLayer,
    MemoryRevisionNotFoundError,
    MemoryRevisionReference,
)
from caliburn.settings import DatabaseSettings
from caliburn.workflows.memory_candidates import (
    MemoryCandidateWorkflow,
    start_memory_candidate,
)
from tests.fixtures.memory_owner import publish_memory_owner_fixture

pytestmark = pytest.mark.postgres
SITUATION = MemoryLayer.WORK_SITUATION
UNDERSTANDING = MemoryLayer.WORK_UNDERSTANDING


def execute[T](settings: DatabaseSettings, operation: Callable[[Database], Awaitable[T]]) -> T:
    async def run() -> T:
        database = Database(settings)
        try:
            return await operation(database)
        finally:
            await database.close()

    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        return runner.run(run())


async def writer(session: AsyncSession, file_id: UUID) -> ExecutionWriter:
    scope = ExecutionScope(file_id, uuid4(), ExecutionKind.MEMORY_BATCH)
    await executions.admit_execution(session, scope)
    return await executions.claim_writer(session, scope, writer_id=uuid4())


@pytest.fixture
def source(database_connection: psycopg.Connection) -> tuple[UUID, UUID]:
    file_id, source_id = uuid4(), uuid4()
    database_connection.execute(
        "INSERT INTO job_files (job_file_id,initial_display_name,"
        "display_name,employee_name) VALUES (%s,'Memory','Memory','合成員工')",
        (file_id,),
    )
    add_interview(database_connection, file_id, uuid4(), 1, "app")
    add_interview(database_connection, file_id, source_id, 2, "employee")
    return file_id, source_id


def add_interview(
    connection: psycopg.Connection, file_id: UUID, source_id: UUID, sequence: int, speaker: str
) -> None:
    connection.execute(
        "INSERT INTO interview_texts (job_file_id,source_id,speaker,interview_text) "
        "VALUES (%s,%s,%s,'合成盤點訪談')",
        (file_id, source_id, speaker),
    )
    connection.execute(
        "INSERT INTO formal_interviews (job_file_id,interview_sequence,source_id) "
        "VALUES (%s,%s,%s)",
        (file_id, sequence, source_id),
    )


async def start(
    database: Database, source: tuple[UUID, UUID]
) -> tuple[MemoryCandidateWorkflow, ExecutionWriter, MemoryBatchPosition]:
    async with database.sessions.begin() as session:
        runner = await writer(session, source[0])
    workflow = MemoryCandidateWorkflow(database.sessions)
    position = await workflow.start(runner, source[1])
    assert position is not None
    return workflow, runner, position


async def build_pair(
    workflow: MemoryCandidateWorkflow,
    runner: ExecutionWriter,
    position: MemoryBatchPosition,
    source_id: UUID,
) -> tuple[MemoryBatchPosition, UUID, UUID]:
    case = await workflow.edit(
        runner,
        CreateMemoryObject(
            uuid4(),
            position,
            SITUATION,
            MemoryContent("每月盤點", "核對庫存", "每月核對實物。"),
            frozenset({source_id}),
        ),
    )
    understanding_stage = await workflow.handoff(runner, case.position, uuid4())
    understanding = await workflow.edit(
        runner,
        CreateMemoryObject(
            uuid4(),
            understanding_stage,
            UNDERSTANDING,
            MemoryContent("庫存管理", "盤點與回報", "依約定範圍盤點並回報異常。"),
            frozenset({case.object_id}),
        ),
    )
    return understanding.position, case.object_id, understanding.object_id


def test_understanding_stage_cannot_handoff_back_to_situations(
    database_settings: DatabaseSettings, source: tuple[UUID, UUID]
) -> None:
    async def scenario(database: Database) -> None:
        workflow, runner, initial = await start(database, source)
        command = uuid4()
        b2 = await workflow.handoff(runner, initial, command)
        assert await workflow.handoff(runner, initial, command) == b2
        with pytest.raises(MemoryCandidateStateError):
            await workflow.handoff(runner, b2, uuid4())
        snapshot = await publish_memory_owner_fixture(workflow.sessions, runner, b2, uuid4())
        assert snapshot.covered_through_sequence == 2

    execute(database_settings, scenario)


def test_publish_is_one_fixed_graph_and_replay_returns_original_snapshot(
    database_settings: DatabaseSettings, source: tuple[UUID, UUID]
) -> None:
    async def scenario(database: Database) -> None:
        workflow, runner, initial = await start(database, source)
        position, case_id, understanding_id = await build_pair(workflow, runner, initial, source[1])
        assert await workflow.read_latest_snapshot(source[0]) is None
        publication = uuid4()
        snapshot = await publish_memory_owner_fixture(
            workflow.sessions, runner, position, publication
        )
        assert snapshot.covered_through_sequence == 2
        assert (
            await publish_memory_owner_fixture(workflow.sessions, runner, position, publication)
            == snapshot
        )
        assert await workflow.read_latest_snapshot(source[0]) == snapshot
        case = await workflow.read_snapshot_object(source[0], snapshot.snapshot_id, case_id)
        understanding = await workflow.read_snapshot_object(
            source[0], snapshot.snapshot_id, understanding_id
        )
        assert understanding.work_situation_references == frozenset(
            {MemoryRevisionReference(case_id, case.revision_id)}
        )
        assert (await workflow.read_snapshot_map(source[0], snapshot.snapshot_id, SITUATION))[
            0
        ].title == "每月盤點"

    execute(database_settings, scenario)


def test_candidate_binding_tracks_new_situation_but_old_snapshot_never_changes(
    database_settings: DatabaseSettings,
    database_connection: psycopg.Connection,
    source: tuple[UUID, UUID],
) -> None:
    later = uuid4()
    add_interview(database_connection, source[0], uuid4(), 3, "consultant")
    add_interview(database_connection, source[0], later, 4, "employee")

    async def scenario(database: Database) -> None:
        workflow, runner, initial = await start(database, source)
        position, case_id, understanding_id = await build_pair(workflow, runner, initial, source[1])
        first = await publish_memory_owner_fixture(workflow.sessions, runner, position, uuid4())
        old_case = await workflow.read_snapshot_object(source[0], first.snapshot_id, case_id)
        old_understanding = await workflow.read_snapshot_object(
            source[0], first.snapshot_id, understanding_id
        )
        workflow, runner, initial = await start(database, (source[0], later))
        changed = await workflow.edit(
            runner,
            ReviseMemoryObject(
                uuid4(),
                initial,
                SITUATION,
                case_id,
                MemoryContentChanges(title="每季盤點", body="每季核對實物。"),
            ),
        )
        position = await workflow.handoff(runner, changed.position, uuid4())
        current = await workflow.read_object(
            runner.scope, stage=position, layer=UNDERSTANDING, object_id=understanding_id
        )
        latest_case = await workflow.read_object(
            runner.scope, stage=position, layer=SITUATION, object_id=case_id
        )
        assert current.work_situation_references == frozenset(
            {MemoryRevisionReference(case_id, latest_case.content_revision_id)}
        )
        assert current.content_revision_id == old_understanding.revision_id
        second = await publish_memory_owner_fixture(workflow.sessions, runner, position, uuid4())
        new_understanding = await workflow.read_snapshot_object(
            source[0], second.snapshot_id, understanding_id
        )
        assert new_understanding.revision_id != old_understanding.revision_id
        assert new_understanding.body_id == old_understanding.body_id
        assert new_understanding.work_situation_references == current.work_situation_references
        assert (
            await workflow.read_snapshot_object(source[0], first.snapshot_id, case_id) == old_case
        )
        assert (
            await workflow.read_snapshot_object(source[0], first.snapshot_id, understanding_id)
            == old_understanding
        )

    execute(database_settings, scenario)


def test_delete_situation_removes_candidate_bindings_not_understandings_or_history(
    database_settings: DatabaseSettings,
    database_connection: psycopg.Connection,
    source: tuple[UUID, UUID],
) -> None:
    later = uuid4()
    add_interview(database_connection, source[0], uuid4(), 3, "consultant")
    add_interview(database_connection, source[0], later, 4, "employee")

    async def scenario(database: Database) -> None:
        workflow, runner, initial = await start(database, source)
        position, case_id, understanding_id = await build_pair(workflow, runner, initial, source[1])
        original = await publish_memory_owner_fixture(workflow.sessions, runner, position, uuid4())
        workflow, runner, situation_stage = await start(database, (source[0], later))
        deleted = await workflow.edit(
            runner, DeleteMemoryObject(uuid4(), situation_stage, SITUATION, case_id)
        )
        position = await workflow.handoff(runner, deleted.position, uuid4())
        current = await workflow.read_object(
            runner.scope, stage=position, layer=UNDERSTANDING, object_id=understanding_id
        )
        assert not current.work_situation_references
        assert not await workflow.read_map(runner.scope, stage=position, layer=SITUATION)
        snapshot = await publish_memory_owner_fixture(workflow.sessions, runner, position, uuid4())
        assert not (
            await workflow.read_snapshot_object(source[0], snapshot.snapshot_id, understanding_id)
        ).work_situation_references
        assert (
            await workflow.read_snapshot_object(source[0], original.snapshot_id, understanding_id)
        ).work_situation_references

    execute(database_settings, scenario)


def test_role_and_stage_permissions_are_enforced_beyond_tool_registration(
    database_settings: DatabaseSettings, source: tuple[UUID, UUID]
) -> None:
    async def scenario(database: Database) -> None:
        workflow, runner, initial = await start(database, source)
        with pytest.raises(MemoryPermissionError):
            await workflow.read_map(runner.scope, stage=initial, layer=UNDERSTANDING)
        with pytest.raises(MemoryPermissionError):
            await workflow.edit(
                runner,
                CreateMemoryObject(
                    uuid4(), initial, UNDERSTANDING, MemoryContent("理解", "描述", "正文")
                ),
            )
        second = await workflow.handoff(runner, initial, uuid4())
        with pytest.raises(MemoryPermissionError):
            await workflow.edit(
                runner,
                CreateMemoryObject(
                    uuid4(), second, SITUATION, MemoryContent("情境", "描述", "正文")
                ),
            )
        with pytest.raises(MemoryCandidateStateError):
            await workflow.read_map(runner.scope, stage=initial, layer=SITUATION)
        with pytest.raises(MemoryCandidateStateError):
            await publish_memory_owner_fixture(workflow.sessions, runner, initial, uuid4())

    execute(database_settings, scenario)


def test_replay_retains_original_identity_after_rename_and_title_reuse(
    database_settings: DatabaseSettings, source: tuple[UUID, UUID]
) -> None:
    async def scenario(database: Database) -> None:
        workflow, runner, initial = await start(database, source)
        create = CreateMemoryObject(
            uuid4(), initial, SITUATION, MemoryContent("盤點", "描述", "正文")
        )
        original = await workflow.edit(runner, create)
        renamed = await workflow.edit(
            runner,
            ReviseMemoryObject(
                uuid4(),
                original.position,
                SITUATION,
                original.object_id,
                MemoryContentChanges(title="月末盤點"),
            ),
        )
        other = await workflow.edit(
            runner, CreateMemoryObject(uuid4(), renamed.position, SITUATION, create.content)
        )
        assert other.object_id != original.object_id
        assert await workflow.edit(runner, create) == original
        with pytest.raises(MemoryCommandConflictError):
            await workflow.edit(
                runner, replace(create, content=MemoryContent("別項", "描述", "正文"))
            )
        assert {
            item.title
            for item in await workflow.read_map(runner.scope, stage=other.position, layer=SITUATION)
        } == {"月末盤點", "盤點"}

    execute(database_settings, scenario)


def test_restore_invalidates_late_branch_and_preserves_prior_candidate(
    database_settings: DatabaseSettings, source: tuple[UUID, UUID]
) -> None:
    async def scenario(database: Database) -> None:
        workflow, runner, initial = await start(database, source)
        position, case_id, understanding_id = await build_pair(workflow, runner, initial, source[1])
        command = uuid4()
        restored = await workflow.restore(runner, position, initial, command)
        assert restored.generation_id != initial.generation_id
        assert restored.phase == SITUATION
        assert not await workflow.read_map(runner.scope, stage=restored, layer=SITUATION)
        assert await workflow.restore(runner, position, initial, command) == restored
        with pytest.raises(MemoryCandidateStateError):
            await workflow.edit(
                runner,
                ReviseMemoryObject(
                    uuid4(),
                    position,
                    UNDERSTANDING,
                    understanding_id,
                    MemoryContentChanges(title="遲到修改"),
                ),
            )
        await workflow.discard(runner, restored, uuid4())
        assert await workflow.read_latest_snapshot(source[0]) is None

    execute(database_settings, scenario)


def test_batch_reentry_keeps_original_source_boundary(
    database_settings: DatabaseSettings,
    database_connection: psycopg.Connection,
    source: tuple[UUID, UUID],
) -> None:
    later = uuid4()
    add_interview(database_connection, source[0], uuid4(), 3, "consultant")
    add_interview(database_connection, source[0], later, 4, "employee")

    async def scenario(database: Database) -> None:
        workflow, runner, initial = await start(database, source)
        assert await workflow.start(runner, source[1]) == initial
        with pytest.raises(MemoryCommandConflictError):
            await workflow.start(runner, later)
        with pytest.raises(InterviewReadError):
            await workflow.edit(
                runner,
                CreateMemoryObject(
                    uuid4(),
                    initial,
                    SITUATION,
                    MemoryContent("超界訪談", "描述", "正文"),
                    frozenset({later}),
                ),
            )
        assert not await workflow.read_map(runner.scope, stage=initial, layer=SITUATION)

    execute(database_settings, scenario)


def test_owner_publication_rolls_back_with_the_caller_transaction(
    database_settings: DatabaseSettings, source: tuple[UUID, UUID]
) -> None:
    async def scenario(database: Database) -> None:
        workflow, runner, initial = await start(database, source)
        position, _, _ = await build_pair(workflow, runner, initial, source[1])
        command_id = uuid4()
        with pytest.raises(RuntimeError, match="before commit"):
            async with database.sessions.begin() as session:
                await candidate_lifecycle.publish(session, position, command_id)
                raise RuntimeError("simulated interruption before commit")
        assert await workflow.read_latest_snapshot(source[0]) is None
        async with database.sessions() as session:
            assert (
                await executions.read_execution(session, runner.scope)
            ).status == ExecutionStatus.ACTIVE
        assert await workflow.read_map(runner.scope, stage=position, layer=UNDERSTANDING)
        result = await publish_memory_owner_fixture(workflow.sessions, runner, position, command_id)
        assert (
            await publish_memory_owner_fixture(workflow.sessions, runner, position, command_id)
            == result
        )

    execute(database_settings, scenario)


def test_concurrent_reentry_has_one_effect_and_competing_position_is_rejected(
    database_settings: DatabaseSettings, source: tuple[UUID, UUID]
) -> None:
    async def scenario(database: Database) -> None:
        workflow, runner, initial = await start(database, source)
        command = CreateMemoryObject(
            uuid4(), initial, SITUATION, MemoryContent("盤點", "描述", "正文")
        )
        first, replay = await asyncio.gather(
            workflow.edit(runner, command), workflow.edit(runner, command)
        )
        assert first == replay
        results = await asyncio.gather(
            *(
                workflow.edit(
                    runner,
                    CreateMemoryObject(
                        uuid4(), first.position, SITUATION, MemoryContent(title, "描述", "正文")
                    ),
                )
                for title in ("接貨", "出貨")
            ),
            return_exceptions=True,
        )
        assert sum(isinstance(result, MemoryCandidateStateError) for result in results) == 1
        assert (
            len(await workflow.read_map(runner.scope, stage=first.position, layer=SITUATION)) == 2
        )

    execute(database_settings, scenario)


def test_new_writer_rejects_late_worker_and_can_continue_same_candidate(
    database_settings: DatabaseSettings, source: tuple[UUID, UUID]
) -> None:
    async def scenario(database: Database) -> None:
        workflow, old_writer, initial = await start(database, source)
        async with database.sessions.begin() as session:
            current_writer = await executions.claim_writer(
                session,
                old_writer.scope,
                writer_id=uuid4(),
                replaces_writer_id=old_writer.writer_id,
            )
        command = CreateMemoryObject(
            uuid4(), initial, SITUATION, MemoryContent("盤點", "描述", "正文")
        )
        with pytest.raises(StaleWriterError):
            await workflow.edit(old_writer, command)
        result = await workflow.edit(current_writer, command)
        assert (
            await workflow.read_map(current_writer.scope, stage=result.position, layer=SITUATION)
        )[0].object_id == result.object_id

    execute(database_settings, scenario)


def test_restore_rejects_forged_stage_and_abandoned_descendant(
    database_settings: DatabaseSettings, source: tuple[UUID, UUID]
) -> None:
    async def scenario(database: Database) -> None:
        workflow, runner, initial = await start(database, source)
        position, _, _ = await build_pair(workflow, runner, initial, source[1])
        with pytest.raises(MemoryCandidateStateError):
            await workflow.restore(runner, position, replace(initial, phase=UNDERSTANDING), uuid4())
        restored = await workflow.restore(runner, position, initial, uuid4())
        with pytest.raises(MemoryCandidateStateError):
            await workflow.restore(runner, restored, position, uuid4())
        assert not await workflow.read_map(runner.scope, stage=restored, layer=SITUATION)

    execute(database_settings, scenario)


def test_failed_execution_only_recovers_original_discard_not_new_effect(
    database_settings: DatabaseSettings, source: tuple[UUID, UUID]
) -> None:
    async def scenario(database: Database) -> None:
        workflow, runner, initial = await start(database, source)
        async with database.sessions.begin() as session:
            await executions.finish_execution(session, runner, ExecutionStatus.FAILED)
        with pytest.raises(ExecutionStateError):
            await workflow.discard(runner, initial, uuid4())

    execute(database_settings, scenario)


def test_system_discard_reentry_returns_original_without_reactivating(
    database_settings: DatabaseSettings, source: tuple[UUID, UUID]
) -> None:
    async def scenario(database: Database) -> None:
        workflow, runner, initial = await start(database, source)
        command_id = uuid4()
        await workflow.discard(runner, initial, command_id)
        await workflow.discard(runner, initial, command_id)
        with pytest.raises(ExecutionStateError):
            await workflow.start(runner, source[1])
        assert await workflow.read_latest_snapshot(source[0]) is None

    execute(database_settings, scenario)


def test_new_snapshot_reuses_unchanged_objects_and_keeps_file_scope(
    database_settings: DatabaseSettings,
    database_connection: psycopg.Connection,
    source: tuple[UUID, UUID],
) -> None:
    later = uuid4()
    add_interview(database_connection, source[0], uuid4(), 3, "consultant")
    add_interview(database_connection, source[0], later, 4, "employee")

    async def scenario(database: Database) -> None:
        workflow, runner, initial = await start(database, source)
        position, case_id, understanding_id = await build_pair(workflow, runner, initial, source[1])
        first = await publish_memory_owner_fixture(workflow.sessions, runner, position, uuid4())
        workflow, runner, initial = await start(database, (source[0], later))
        unchanged = await workflow.edit(
            runner,
            ReviseMemoryObject(
                uuid4(), initial, SITUATION, case_id, MemoryContentChanges(title="每月盤點")
            ),
        )
        assert unchanged.position == initial
        position = await workflow.handoff(runner, unchanged.position, uuid4())
        second = await publish_memory_owner_fixture(workflow.sessions, runner, position, uuid4())
        assert second.snapshot_id != first.snapshot_id
        assert second.position_id == first.position_id
        assert second.covered_through_sequence == 4
        for identity in (case_id, understanding_id):
            assert await workflow.read_snapshot_object(
                source[0], first.snapshot_id, identity
            ) == await workflow.read_snapshot_object(source[0], second.snapshot_id, identity)
        with pytest.raises(MemoryRevisionNotFoundError):
            await workflow.read_snapshot_object(uuid4(), second.snapshot_id, case_id)

    execute(database_settings, scenario)


def test_restore_retains_understanding_safe_point_and_rejects_abandoned_branch(
    database_settings: DatabaseSettings, source: tuple[UUID, UUID]
) -> None:
    async def scenario(database: Database) -> None:
        workflow, runner, initial = await start(database, source)
        safe_point, case_id, understanding_id = await build_pair(
            workflow, runner, initial, source[1]
        )
        before = await workflow.read_object(
            runner.scope, stage=safe_point, layer=UNDERSTANDING, object_id=understanding_id
        )
        change = await workflow.edit(
            runner,
            ReviseMemoryObject(
                uuid4(),
                safe_point,
                UNDERSTANDING,
                understanding_id,
                MemoryContentChanges(body="尚未確認的新理解"),
            ),
        )
        after = await workflow.read_object(
            runner.scope, stage=change.position, layer=UNDERSTANDING, object_id=understanding_id
        )
        assert after.content.body == "尚未確認的新理解"
        assert after.work_situation_references == before.work_situation_references
        restored = await workflow.restore(runner, change.position, safe_point, uuid4())
        assert restored.phase == UNDERSTANDING
        assert (
            await workflow.read_object(
                runner.scope, stage=restored, layer=UNDERSTANDING, object_id=understanding_id
            )
            == before
        )
        with pytest.raises(MemoryCandidateStateError):
            await publish_memory_owner_fixture(workflow.sessions, runner, change.position, uuid4())
        snapshot = await publish_memory_owner_fixture(workflow.sessions, runner, restored, uuid4())
        assert (
            await workflow.read_snapshot_object(source[0], snapshot.snapshot_id, case_id)
        ).content.title == "每月盤點"

    execute(database_settings, scenario)


def test_delete_shared_source_removes_only_its_bindings_and_preserves_publication(
    database_settings: DatabaseSettings,
    database_connection: psycopg.Connection,
    source: tuple[UUID, UUID],
) -> None:
    later = uuid4()
    add_interview(database_connection, source[0], uuid4(), 3, "consultant")
    add_interview(database_connection, source[0], later, 4, "employee")

    async def scenario(database: Database) -> None:
        workflow, runner, initial = await start(database, source)
        keep = await workflow.edit(
            runner,
            CreateMemoryObject(uuid4(), initial, SITUATION, MemoryContent("收貨", "描述", "正文")),
        )
        position, remove_id, first_understanding = await build_pair(
            workflow, runner, keep.position, source[1]
        )
        second = await workflow.edit(
            runner,
            CreateMemoryObject(
                uuid4(),
                position,
                UNDERSTANDING,
                MemoryContent("收貨盤點", "描述", "正文"),
                frozenset({remove_id, keep.object_id}),
            ),
        )
        published = await publish_memory_owner_fixture(
            workflow.sessions, runner, second.position, uuid4()
        )
        workflow, runner, initial = await start(database, (source[0], later))
        removed = await workflow.edit(
            runner, DeleteMemoryObject(uuid4(), initial, SITUATION, remove_id)
        )
        b2 = await workflow.handoff(runner, removed.position, uuid4())
        one = await workflow.read_object(
            runner.scope, stage=b2, layer=UNDERSTANDING, object_id=first_understanding
        )
        two = await workflow.read_object(
            runner.scope, stage=b2, layer=UNDERSTANDING, object_id=second.object_id
        )
        assert not one.work_situation_references
        assert {ref.object_id for ref in two.work_situation_references} == {keep.object_id}
        latest = await publish_memory_owner_fixture(workflow.sessions, runner, b2, uuid4())
        with pytest.raises(MemoryRevisionNotFoundError):
            await workflow.read_snapshot_object(source[0], latest.snapshot_id, remove_id)
        assert (
            await workflow.read_snapshot_object(source[0], published.snapshot_id, remove_id)
        ).content.title == "每月盤點"
        old = await workflow.read_snapshot_object(
            source[0], published.snapshot_id, second.object_id
        )
        assert {ref.object_id for ref in old.work_situation_references} == {
            remove_id,
            keep.object_id,
        }

    execute(database_settings, scenario)


def test_already_covered_start_reentry_keeps_original_no_work_result(
    database_settings: DatabaseSettings, source: tuple[UUID, UUID]
) -> None:
    async def scenario(database: Database) -> None:
        workflow, runner, initial = await start(database, source)
        b2 = await workflow.handoff(runner, initial, uuid4())
        snapshot = await publish_memory_owner_fixture(workflow.sessions, runner, b2, uuid4())
        async with database.sessions.begin() as session:
            redundant = await writer(session, source[0])
        with pytest.raises(RuntimeError, match="before commit"):
            async with database.sessions.begin() as session:
                assert await start_memory_candidate(session, redundant, source[1]) is None
                raise RuntimeError("interrupted before commit")
        async with database.sessions() as session:
            assert (
                await executions.read_execution(session, redundant.scope)
            ).status == ExecutionStatus.ACTIVE
        assert await workflow.start(redundant, source[1]) is None
        # Retry after commit acknowledgement loss, not a new batch or publication.
        assert await workflow.start(redundant, source[1]) is None
        with pytest.raises(MemoryCommandConflictError):
            await workflow.start(redundant, uuid4())
        assert await workflow.read_latest_snapshot(source[0]) == snapshot
        async with database.sessions() as session:
            assert (
                await executions.read_execution(session, redundant.scope)
            ).status == ExecutionStatus.COMPLETED

    execute(database_settings, scenario)
