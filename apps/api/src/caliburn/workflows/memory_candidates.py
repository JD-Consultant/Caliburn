"""Memory business transactions; background scheduling and model execution attach later."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from caliburn.features.executions import service as executions
from caliburn.features.executions.models import (
    ExecutionKind,
    ExecutionScope,
    ExecutionStateError,
    ExecutionStatus,
    ExecutionWriter,
)
from caliburn.features.job_files import service as job_files
from caliburn.features.work_memory import candidate_lifecycle, candidate_queries, candidate_service
from caliburn.features.work_memory.candidates import (
    MemoryBatchPosition,
    MemoryCandidateObject,
    MemoryCandidateStateError,
    MemoryEdit,
    MemoryEditResult,
    MemorySnapshot,
)
from caliburn.features.work_memory.models import MemoryMapEntry
from caliburn.features.work_memory.revisions import MemoryLayer, MemoryObjectRevision


class MemoryCandidateWorkflow:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions

    async def start(
        self, writer: ExecutionWriter, through_source_id: UUID
    ) -> MemoryBatchPosition | None:
        async with self.sessions.begin() as session:
            return await start_memory_candidate(session, writer, through_source_id)

    async def edit(self, writer: ExecutionWriter, command: MemoryEdit) -> MemoryEditResult:
        _require_owner(writer.scope, command.position)
        async with self.sessions.begin() as session:
            await _lock_writer(session, writer)
            return await candidate_service.edit_candidate(session, command)

    async def handoff(
        self, writer: ExecutionWriter, position: MemoryBatchPosition, command_id: UUID
    ) -> MemoryBatchPosition:
        _require_owner(writer.scope, position)
        async with self.sessions.begin() as session:
            await _lock_writer(session, writer)
            return await candidate_lifecycle.handoff(session, position, command_id)

    async def restore(
        self,
        writer: ExecutionWriter,
        position: MemoryBatchPosition,
        target: MemoryBatchPosition,
        command_id: UUID,
    ) -> MemoryBatchPosition:
        _require_owner(writer.scope, position)
        async with self.sessions.begin() as session:
            await _lock_writer(session, writer)
            return await candidate_lifecycle.restore(session, position, target, command_id)

    async def publish(
        self, writer: ExecutionWriter, position: MemoryBatchPosition, command_id: UUID
    ) -> MemorySnapshot:
        async with self.sessions.begin() as session:
            return await publish_memory_candidate(session, writer, position, command_id)

    async def discard(
        self, writer: ExecutionWriter, position: MemoryBatchPosition, command_id: UUID
    ) -> None:
        _require_owner(writer.scope, position)
        async with self.sessions.begin() as session:
            await job_files.lock_job_file(session, writer.scope.job_file_id)
            execution = await executions.read_execution(session, writer.scope)
            if execution.status == ExecutionStatus.FAILED:
                # The prior system discard may have committed before its acknowledgement.
                if not await candidate_lifecycle.recover_discard(session, position, command_id):
                    raise ExecutionStateError("A failed execution cannot start a new discard")
                return
            await executions.lock_active_writer(session, writer)
            await candidate_lifecycle.discard(session, position, command_id)
            await executions.finish_execution(session, writer, ExecutionStatus.FAILED)

    async def read_map(
        self, scope: ExecutionScope, *, stage: MemoryBatchPosition, layer: MemoryLayer
    ) -> tuple[MemoryMapEntry, ...]:
        _require_owner(scope, stage)
        async with self.sessions() as session:
            await _require_active_read(session, scope)
            return await candidate_queries.read_candidate_map(session, stage, layer)

    async def read_object(
        self,
        scope: ExecutionScope,
        *,
        stage: MemoryBatchPosition,
        layer: MemoryLayer,
        object_id: UUID,
    ) -> MemoryCandidateObject:
        _require_owner(scope, stage)
        async with self.sessions() as session:
            await _require_active_read(session, scope)
            return await candidate_queries.read_candidate_object(session, stage, layer, object_id)

    async def read_snapshot_map(
        self, job_file_id: UUID, snapshot_id: UUID, layer: MemoryLayer
    ) -> tuple[MemoryMapEntry, ...]:
        async with self.sessions() as session:
            return await candidate_queries.read_snapshot_map(
                session, job_file_id, snapshot_id, layer
            )

    async def read_snapshot_object(
        self, job_file_id: UUID, snapshot_id: UUID, object_id: UUID
    ) -> MemoryObjectRevision:
        async with self.sessions() as session:
            return await candidate_queries.read_snapshot_object(
                session, job_file_id, snapshot_id, object_id
            )

    async def read_latest_snapshot(self, job_file_id: UUID) -> MemorySnapshot | None:
        async with self.sessions() as session:
            return await candidate_queries.read_latest_snapshot(session, job_file_id)


def _require_memory(scope: ExecutionScope) -> None:
    if scope.kind != ExecutionKind.MEMORY_BATCH:
        raise ExecutionStateError("Only Memory batches can manage Memory candidates")


def _require_owner(scope: ExecutionScope, position: MemoryBatchPosition) -> None:
    _require_memory(scope)
    if (scope.job_file_id, scope.execution_id) != (position.job_file_id, position.execution_id):
        raise MemoryCandidateStateError("The position belongs to a different Memory batch")


async def _lock_writer(session: AsyncSession, writer: ExecutionWriter) -> None:
    await job_files.lock_job_file(session, writer.scope.job_file_id)
    await executions.lock_active_writer(session, writer)


async def _require_active_read(session: AsyncSession, scope: ExecutionScope) -> None:
    if (await executions.read_execution(session, scope)).status != ExecutionStatus.ACTIVE:
        raise ExecutionStateError("This execution no longer has a live Memory candidate")


async def publish_memory_candidate(
    session: AsyncSession, writer: ExecutionWriter, position: MemoryBatchPosition, command_id: UUID
) -> MemorySnapshot:
    """Join completion transaction; scheduler/checkpoint acknowledgement is separate."""
    _require_owner(writer.scope, position)
    await job_files.lock_job_file(session, writer.scope.job_file_id)
    original = await candidate_lifecycle.recover_publication(session, position, command_id)
    if original is not None:
        execution = await executions.read_execution(session, writer.scope)
        if execution.status != ExecutionStatus.COMPLETED:
            raise ExecutionStateError("A published Memory must have completed its execution")
        return original
    await executions.lock_active_writer(session, writer)
    result = await candidate_lifecycle.publish(session, position, command_id)
    await executions.finish_execution(session, writer, ExecutionStatus.COMPLETED)
    return result


async def start_memory_candidate(
    session: AsyncSession, writer: ExecutionWriter, through_source_id: UUID
) -> MemoryBatchPosition | None:
    """Join batch preparation or an already-covered result to its completion transaction."""
    _require_memory(writer.scope)
    await job_files.lock_job_file(session, writer.scope.job_file_id)
    if await candidate_service.recover_covered_start(
        session, writer.scope.job_file_id, writer.scope.execution_id, through_source_id
    ):
        execution = await executions.read_execution(session, writer.scope)
        if execution.status != ExecutionStatus.COMPLETED:
            raise ExecutionStateError("A saved no-work result requires a completed execution")
        return None
    await executions.lock_active_writer(session, writer)
    position = await candidate_service.start_candidate(
        session, writer.scope.job_file_id, writer.scope.execution_id, through_source_id
    )
    if position is None:
        await executions.finish_execution(session, writer, ExecutionStatus.COMPLETED)
    return position
