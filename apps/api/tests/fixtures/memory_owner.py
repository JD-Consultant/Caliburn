"""Synthetic Memory owner state, deliberately without Agent context-history completion.

Use for fixed snapshots, JD sources and domain rules. Product completion/recovery tests
must use MemoryBatchWorkflow with saved B1/B2 contexts instead of this fixture.
"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from caliburn.features.executions import service as executions
from caliburn.features.executions.models import ExecutionStatus, ExecutionWriter
from caliburn.features.job_files import service as job_files
from caliburn.features.work_memory import candidate_lifecycle
from caliburn.features.work_memory.candidates import MemoryBatchPosition, MemorySnapshot


async def publish_memory_owner_fixture(
    sessions: async_sessionmaker[AsyncSession],
    writer: ExecutionWriter,
    position: MemoryBatchPosition,
    command_id: UUID,
) -> MemorySnapshot:
    """Publish owner data and retire the synthetic writer so another fixture batch can start."""
    assert writer.scope.job_file_id == position.job_file_id
    assert writer.scope.execution_id == position.execution_id
    async with sessions.begin() as session:
        await job_files.lock_job_file(session, position.job_file_id)
        original = await candidate_lifecycle.recover_publication(session, position, command_id)
        if original is not None:
            assert (await executions.read_execution(session, writer.scope)).status == (
                ExecutionStatus.COMPLETED
            )
            return original
        await executions.lock_active_writer(session, writer)
        snapshot = await candidate_lifecycle.publish(session, position, command_id)
        await executions.finish_execution(session, writer, ExecutionStatus.COMPLETED)
        return snapshot
