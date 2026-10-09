"""Memory scheduling uses completed A sources, existing candidates and real PG commits."""

import asyncio
from collections.abc import Awaitable, Callable
from uuid import UUID, uuid4

import pytest
from pydantic import JsonValue

from caliburn.adapters.database import Database
from caliburn.adapters.memory_cpu import MemoryCpu
from caliburn.features.executions import history
from caliburn.features.executions import service as executions
from caliburn.features.executions.history_models import (
    AgentRole,
    ContextPosition,
    HistoryWindowKind,
    context_thread_id,
)
from caliburn.features.executions.models import (
    ExecutionKind,
    ExecutionScope,
    ExecutionStatus,
    ExecutionWriter,
)
from caliburn.features.interviews import service as interviews
from caliburn.features.interviews.models import SubmitInterviewInput
from caliburn.features.job_files import service as job_files
from caliburn.features.job_files.models import CreateJobFile
from caliburn.features.work_memory.candidates import CreateMemoryObject, MemoryBatchPosition
from caliburn.features.work_memory.models import MemoryContent
from caliburn.features.work_memory.revisions import MemoryLayer
from caliburn.settings import DatabaseSettings
from caliburn.workflows.interview_completion import record_formal_interview
from caliburn.workflows.memory_candidates import MemoryCandidateWorkflow

pytestmark = pytest.mark.postgres


def execute[T](settings: DatabaseSettings, action: Callable[[Database], Awaitable[T]]) -> T:
    async def run() -> T:
        database = Database(settings)
        try:
            return await action(database)
        finally:
            await database.close()

    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        return runner.run(run())


async def start_turn(database: Database, file_id: UUID | None = None) -> ExecutionWriter:
    async with database.sessions.begin() as session:
        if file_id is None:
            created = await job_files.create_job_file(
                session, CreateJobFile(uuid4(), "Memory 整理", "合成人員")
            )
            file_id = created.job_file.job_file_id
            await interviews.create_opening(session, file_id)
        scope = ExecutionScope(file_id, uuid4(), ExecutionKind.CONSULTANT_TURN)
        await executions.admit_execution(session, scope)
        await interviews.accept_input(
            session,
            SubmitInterviewInput(file_id, uuid4(), "每月盤點庫存。"),
            execution_id=scope.execution_id,
        )
        return await executions.claim_writer(session, scope, writer_id=uuid4())


async def complete_turn(database: Database, writer: ExecutionWriter) -> None:
    # Only source eligibility is under test here; full A completion is tested separately.
    async with database.sessions.begin() as session:
        await record_formal_interview(session, writer, reply_text="盤點發現異常怎麼處理？")
        await executions.finish_execution(session, writer, ExecutionStatus.COMPLETED)


async def role_context(
    database: Database, writer: ExecutionWriter, stage: MemoryBatchPosition
) -> ContextPosition:
    role = (
        AgentRole.WORK_SITUATION_ANALYST
        if stage.phase == MemoryLayer.WORK_SITUATION
        else AgentRole.WORK_UNDERSTANDING_ANALYST
    )
    async with database.sessions.begin() as session:
        binding = await history.bind_context_history(session, writer, role)
        if binding.prepared is None:
            await history.adopt_prepared_context(
                session,
                writer,
                role,
                ContextPosition(
                    context_thread_id(writer.scope, role, HistoryWindowKind.PREPARED_HISTORY),
                    "prepared",
                    HistoryWindowKind.PREPARED_HISTORY,
                ),
            )
    root = context_thread_id(writer.scope, role, HistoryWindowKind.COMPLETED_WORK)
    return ContextPosition(
        f"{root}:stage:{stage.generation_id}:{stage.stage_id}",
        "completed",
        HistoryWindowKind.COMPLETED_WORK,
    )


def test_intent_requires_success_and_frontier_is_employee_not_reply(
    database_settings: DatabaseSettings,
) -> None:
    async def scenario(database: Database) -> None:
        from caliburn.workflows.memory_consolidation import MemoryConsolidationWorkflow

        requests = MemoryConsolidationWorkflow(database.sessions)
        cancelled = await start_turn(database)
        command = uuid4()
        assert await requests.request(cancelled, command) == await requests.request(
            cancelled, command
        )
        assert (await requests.discover()).ready_file_ids == ()
        async with database.sessions.begin() as session:
            await executions.finish_execution(session, cancelled, ExecutionStatus.CANCELLED)
        assert (await requests.discover()).ready_file_ids == ()
        successful = await start_turn(database, cancelled.scope.job_file_id)
        await requests.request(successful, uuid4())
        await complete_turn(database, successful)
        # No completion hook/wakeup is necessary to recover a persisted intent.
        restarted = MemoryConsolidationWorkflow(database.sessions)
        pending = (await restarted.discover()).ready_file_ids
        assert len(pending) == 1
        work = await restarted.claim(pending[0], writer_id=uuid4())
        assert work is not None
        assert work.source_window.through_sequence == 2
        assert work.source_window.covered_through_sequence == 0
        later = await start_turn(database, cancelled.scope.job_file_id)
        await requests.request(later, uuid4())
        await complete_turn(database, later)
        assert (await restarted.read_work(work.writer.scope)).source_window.through_sequence == 2

    execute(database_settings, scenario)


def test_parent_publishes_once_and_coalesces_next_frontier(
    database_settings: DatabaseSettings,
) -> None:
    async def scenario(database: Database) -> None:
        from caliburn.workflows.memory_analysis.results import (
            AnalysisComplete,
            MemoryAnalysisResult,
        )
        from caliburn.workflows.memory_batch import MemoryBatchWorkflow
        from caliburn.workflows.memory_consolidation import MemoryConsolidationWorkflow

        requests = MemoryConsolidationWorkflow(database.sessions)
        turn = await start_turn(database)
        await requests.request(turn, uuid4())
        await complete_turn(database, turn)
        work = await requests.claim(
            (await requests.discover()).ready_file_ids[0], writer_id=uuid4()
        )
        assert work is not None
        for _ in range(2):
            later = await start_turn(database, turn.scope.job_file_id)
            await requests.request(later, uuid4())
            await complete_turn(database, later)
        calls: list[MemoryLayer] = []
        candidates = MemoryCandidateWorkflow(database.sessions)

        async def run_role(
            writer: ExecutionWriter,
            stage: MemoryBatchPosition,
            *,
            situation_changes: list[dict[str, JsonValue]] | None = None,
        ) -> MemoryAnalysisResult:
            calls.append(stage.phase)
            if stage.phase == MemoryLayer.WORK_SITUATION:
                edited = await candidates.edit(
                    writer,
                    CreateMemoryObject(
                        uuid4(),
                        stage,
                        stage.phase,
                        MemoryContent("盤點", "每月盤點", "核對帳物。"),
                        frozenset({work.source_window.through_source_id}),
                    ),
                )
                stage = edited.position
                assert situation_changes is None
            else:
                assert situation_changes is not None and len(situation_changes) == 1
                assert situation_changes[0]["change"] == "added"
                assert situation_changes[0]["affected_understanding_titles"] == []
                assert "核對帳物" in situation_changes[0]["diff"]
            return MemoryAnalysisResult(
                stage,
                AnalysisComplete(status="complete"),
                await role_context(database, writer, stage),
            )

        parent = MemoryBatchWorkflow(database.sessions, run_role=run_role, cpu=MemoryCpu())
        published = await parent.run(work.writer)
        assert published is not None and published.covered_through_sequence == 2
        assert await parent.run(work.writer) == published
        assert calls == [MemoryLayer.WORK_SITUATION, MemoryLayer.WORK_UNDERSTANDING]
        pending = (await requests.discover()).ready_file_ids
        next_work = await requests.claim(pending[0], writer_id=uuid4())
        assert next_work is not None
        assert next_work.source_window.covered_through_sequence == 2
        assert next_work.source_window.through_sequence == 6

    execute(database_settings, scenario)


def test_final_failure_blocks_until_the_interview_has_advanced(
    database_settings: DatabaseSettings,
) -> None:
    async def scenario(database: Database) -> None:
        from caliburn.workflows.memory_consolidation import MemoryConsolidationWorkflow

        requests = MemoryConsolidationWorkflow(database.sessions)
        turn = await start_turn(database)
        file_id = turn.scope.job_file_id
        await requests.request(turn, uuid4())
        await complete_turn(database, turn)
        work = await requests.claim(
            (await requests.discover()).ready_file_ids[0], writer_id=uuid4()
        )
        assert work is not None
        await requests.fail(work.writer, reason="quota_exhausted")
        # One more request and exchange is a notification, not a changed condition.
        later = await start_turn(database, file_id)
        await requests.request(later, uuid4())
        await complete_turn(database, later)
        assert (await requests.discover()).ready_file_ids == ()
        assert await requests.failure_reason(file_id) == "quota_exhausted"
        assert (
            await MemoryCandidateWorkflow(database.sessions).read_latest_snapshot(file_id) is None
        )
        # Enough new interview (three completed exchanges) allows one new attempt, no skipping.
        for _ in range(2):
            await complete_turn(database, await start_turn(database, file_id))
        assert await requests.failure_reason(file_id) is None
        next_work = await requests.claim(
            (await requests.discover()).ready_file_ids[0], writer_id=uuid4()
        )
        assert next_work is not None
        assert next_work.source_window.covered_through_sequence == 0
        assert next_work.source_window.through_sequence == 4
        # A retry that fails again blocks again, measured from its own failure.
        await requests.fail(next_work.writer, reason="transient_service")
        assert (await requests.discover()).ready_file_ids == ()
        assert await requests.failure_reason(file_id) == "transient_service"

    execute(database_settings, scenario)


def test_failure_without_typed_frontier_is_rejected(database_settings: DatabaseSettings) -> None:
    """The retired legacy fallback is replaced by a mandatory typed frontier."""
    from sqlalchemy.exc import IntegrityError

    from caliburn.features.work_memory.batch_persistence import MemoryOperationRecord

    async def scenario(database: Database) -> None:
        turn = await start_turn(database)
        with pytest.raises(IntegrityError, match="evidence_shape"):
            async with database.sessions.begin() as session:
                session.add(
                    MemoryOperationRecord(
                        job_file_id=turn.scope.job_file_id,
                        execution_id=turn.scope.execution_id,
                        command_id=uuid4(),
                        kind="batch_failure",
                        failure_reason="synthetic",
                    )
                )

    execute(database_settings, scenario)


def test_reentry_after_b1_handoff_skips_b1_and_preserves_work(
    database_settings: DatabaseSettings,
) -> None:
    async def scenario(database: Database) -> None:
        from caliburn.workflows.memory_analysis.results import (
            AnalysisComplete,
            MemoryAnalysisResult,
        )
        from caliburn.workflows.memory_batch import MemoryBatchWorkflow
        from caliburn.workflows.memory_consolidation import MemoryConsolidationWorkflow

        requests = MemoryConsolidationWorkflow(database.sessions)
        turn = await start_turn(database)
        await requests.request(turn, uuid4())
        await complete_turn(database, turn)
        work = await requests.claim(
            (await requests.discover()).ready_file_ids[0], writer_id=uuid4()
        )
        assert work is not None
        calls: list[MemoryLayer] = []
        interrupted = False

        async def role(
            writer: ExecutionWriter,
            stage: MemoryBatchPosition,
            *,
            situation_changes: list[dict[str, JsonValue]] | None = None,
        ) -> MemoryAnalysisResult:
            nonlocal interrupted
            calls.append(stage.phase)
            if stage.phase == MemoryLayer.WORK_UNDERSTANDING and not interrupted:
                interrupted = True
                raise ConnectionError("Synthetic worker interruption before B2")
            return MemoryAnalysisResult(
                stage,
                AnalysisComplete(status="complete"),
                await role_context(database, writer, stage),
            )

        with pytest.raises(ConnectionError):
            await MemoryBatchWorkflow(database.sessions, run_role=role, cpu=MemoryCpu()).run(
                work.writer
            )
        resumed = await requests.claim(turn.scope.job_file_id, writer_id=uuid4())
        assert resumed is not None and resumed.position.phase == MemoryLayer.WORK_UNDERSTANDING
        result = await MemoryBatchWorkflow(database.sessions, run_role=role, cpu=MemoryCpu()).run(
            resumed.writer
        )
        assert result.covered_through_sequence == 2
        assert calls.count(MemoryLayer.WORK_SITUATION) == 1
        assert (await requests.discover()).ready_file_ids == ()

    execute(database_settings, scenario)


def test_b2_can_publish_understanding_with_explicit_unknown_without_rework(
    database_settings: DatabaseSettings,
) -> None:
    async def scenario(database: Database) -> None:
        from caliburn.workflows.memory_analysis.results import (
            AnalysisComplete,
            MemoryAnalysisResult,
        )
        from caliburn.workflows.memory_batch import MemoryBatchWorkflow
        from caliburn.workflows.memory_consolidation import MemoryConsolidationWorkflow

        requests = MemoryConsolidationWorkflow(database.sessions)
        turn = await start_turn(database)
        await requests.request(turn, uuid4())
        await complete_turn(database, turn)
        work = await requests.claim(
            (await requests.discover()).ready_file_ids[0], writer_id=uuid4()
        )
        assert work is not None
        candidates = MemoryCandidateWorkflow(database.sessions)
        calls: list[MemoryLayer] = []
        understanding_id = None

        async def role(
            writer: ExecutionWriter,
            stage: MemoryBatchPosition,
            *,
            situation_changes: list[dict[str, JsonValue]] | None = None,
        ) -> MemoryAnalysisResult:
            nonlocal understanding_id
            calls.append(stage.phase)
            context = await role_context(database, writer, stage)
            if stage.phase == MemoryLayer.WORK_UNDERSTANDING:
                edited = await candidates.edit(
                    writer,
                    CreateMemoryObject(
                        uuid4(),
                        stage,
                        stage.phase,
                        MemoryContent("庫存管理", "盤點與回報", "頻率待確認。"),
                    ),
                )
                stage = edited.position
                understanding_id = edited.object_id
            return MemoryAnalysisResult(stage, AnalysisComplete(status="complete"), context)

        result = await MemoryBatchWorkflow(database.sessions, run_role=role, cpu=MemoryCpu()).run(
            work.writer
        )
        assert result.covered_through_sequence == 2
        assert calls == [MemoryLayer.WORK_SITUATION, MemoryLayer.WORK_UNDERSTANDING]
        assert understanding_id is not None
        published = await candidates.read_snapshot_object(
            turn.scope.job_file_id, result.snapshot_id, understanding_id
        )
        assert published.content.body == "頻率待確認。"

    execute(database_settings, scenario)
