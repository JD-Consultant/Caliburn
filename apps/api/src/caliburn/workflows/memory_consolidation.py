"""A's durable intent and system-only batch admission; no provider I/O or user controls."""

from dataclasses import dataclass
from uuid import UUID, uuid4, uuid5

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from caliburn.adapters.database import consistent_read_session
from caliburn.features.executions import service as executions
from caliburn.features.executions.models import (
    ExecutionKind,
    ExecutionScope,
    ExecutionStateError,
    ExecutionStatus,
    ExecutionWriter,
)
from caliburn.features.interviews import queries as interviews
from caliburn.features.job_files import service as job_files
from caliburn.features.work_memory import batch_persistence, candidate_lifecycle, candidate_queries
from caliburn.features.work_memory import consolidation_requests as requests
from caliburn.features.work_memory.batch_models import MemoryBatchWork
from caliburn.features.work_memory.candidates import MemoryCandidateStateError
from caliburn.features.work_memory.consolidation_models import (
    MemoryConsolidationIntent,
    MemoryEvidenceError,
    MemoryEvidenceIssue,
)
from caliburn.workflows.memory_candidates import start_memory_candidate
from caliburn.workflows.memory_consolidation_queries import (
    read_failure_reason,
    read_memory_qualification,
)


@dataclass(frozen=True, slots=True)
class MemoryReadyFile:
    job_file_id: UUID
    active_scope: ExecutionScope | None


@dataclass(frozen=True, slots=True)
class MemoryDiscovery:
    ready_files: tuple[MemoryReadyFile, ...]
    issues: tuple[MemoryEvidenceIssue, ...]

    @property
    def ready_file_ids(self) -> tuple[UUID, ...]:
        return tuple(entry.job_file_id for entry in self.ready_files)


class MemoryConsolidationWorkflow:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def request(self, writer: ExecutionWriter, command_id: UUID) -> MemoryConsolidationIntent:
        """Tool hook: request only; its effect becomes eligible with atomic A completion.

        No source/sequence/version parameter is model-supplied. Multiple tool calls in
        the same Turn remain one effective frontier. Cancelled/failed A never qualifies.
        """
        if writer.scope.kind != ExecutionKind.CONSULTANT_TURN:
            raise ExecutionStateError("Only the consultant may request consolidation")
        async with self._sessions.begin() as session:
            await job_files.lock_job_file(session, writer.scope.job_file_id)
            await executions.lock_active_writer(session, writer)
            source_id = await interviews.read_execution_input_source_id(
                session,
                job_file_id=writer.scope.job_file_id,
                execution_id=writer.scope.execution_id,
            )
            if source_id is None:
                raise ExecutionStateError("The consultant Turn has no accepted input")
            await requests.record_intent(
                session,
                job_file_id=writer.scope.job_file_id,
                execution_id=writer.scope.execution_id,
                command_id=command_id,
                source_id=source_id,
            )
            return MemoryConsolidationIntent(source_id)

    async def discover(self) -> MemoryDiscovery:
        """Read eligible files and damaged evidence without authorizing any execution retry."""
        async with consistent_read_session(self._sessions) as session:
            qualification = await read_memory_qualification(session)
            scopes = {file_id: info.scope for file_id, info in qualification.active.items()}
            return MemoryDiscovery(
                tuple(
                    MemoryReadyFile(file_id, scopes.get(file_id))
                    for file_id in sorted(scopes.keys() | qualification.source_ids.keys())
                ),
                qualification.issues,
            )

    async def claim(self, job_file_id: UUID, *, writer_id: UUID) -> MemoryBatchWork | None:
        """Leader-only admission/recovery; retain writer_id across an unknown COMMIT.

        Caller MUST hold the local deployment's supervision fence before replacing a
        writer, and ensure its previous task is gone. SQL fencing is not liveness proof.
        """
        async with self._sessions.begin() as session:
            await job_files.lock_job_file(session, job_file_id)
            qualification = await read_memory_qualification(session, job_file_id)
            if qualification.issues:
                raise MemoryEvidenceError(qualification.issues[0])
            active = qualification.active.get(job_file_id)
            if active is None:
                source_id = qualification.source_ids.get(job_file_id)
                if source_id is None:
                    return None
                scope = ExecutionScope(job_file_id, uuid4(), ExecutionKind.MEMORY_BATCH)
                await executions.admit_execution(session, scope)
                writer = await executions.claim_writer(session, scope, writer_id=writer_id)
                position = await start_memory_candidate(session, writer, source_id)
                if position is None:
                    return None
            else:
                writer = await executions.claim_writer(
                    session, active.scope, writer_id=writer_id, replaces_writer_id=active.writer_id
                )
            return await self._read_work(session, writer)

    async def read_work(self, scope: ExecutionScope) -> MemoryBatchWork:
        async with self._sessions() as session:
            execution = await executions.read_execution(session, scope)
            if execution.writer_id is None or execution.status != ExecutionStatus.ACTIVE:
                raise ExecutionStateError("Memory work is not active")
            return await self._read_work(session, ExecutionWriter(scope, execution.writer_id))

    async def failure_reason(self, job_file_id: UUID) -> str | None:
        async with self._sessions() as session:
            return await read_failure_reason(session, job_file_id)

    async def fail(self, writer: ExecutionWriter, *, reason: str) -> None:
        """Settle abandoned work, preserving any publication that already committed.

        An unknown commit is reconciled under the same job lock; query or settlement
        failure still propagates and never proves the candidate was discarded. The failure
        keeps new batches blocked until the interview has advanced past the frontier recorded
        here (`RETRY_AFTER_NEW_MESSAGES`): only progress, never a notification or the clock,
        allows one new attempt, and the work stays unskipped from the published coverage.
        """
        if writer.scope.kind != ExecutionKind.MEMORY_BATCH or not reason or len(reason) > 100:
            raise ValueError("A Memory failure requires a short classified reason code")
        async with self._sessions.begin() as session:
            await job_files.lock_job_file(session, writer.scope.job_file_id)
            execution = await executions.read_execution(session, writer.scope)
            if execution.status == ExecutionStatus.COMPLETED:
                return  # A committed publication wins over an acknowledgement failure.
            if execution.status != ExecutionStatus.FAILED:
                await executions.lock_active_writer(session, writer)
                work = await self._read_work(session, writer)
                await candidate_lifecycle.discard(
                    session, work.position, uuid5(writer.scope.execution_id, "memory.discard")
                )
                await executions.finish_execution(session, writer, ExecutionStatus.FAILED)
            else:
                await executions.finish_execution(session, writer, ExecutionStatus.FAILED)
            command_id = uuid5(writer.scope.execution_id, "memory.failure")
            original = await requests.recover_failure(
                session,
                job_file_id=writer.scope.job_file_id,
                execution_id=writer.scope.execution_id,
                command_id=command_id,
                reason=reason,
            )
            if original is None:
                frontier = await interviews.read_history_frontier(session, writer.scope.job_file_id)
                await requests.record_failure(
                    session,
                    job_file_id=writer.scope.job_file_id,
                    execution_id=writer.scope.execution_id,
                    command_id=command_id,
                    reason=reason,
                    frontier=frontier,
                )

    async def _read_work(self, session: AsyncSession, writer: ExecutionWriter) -> MemoryBatchWork:
        if writer.scope.kind != ExecutionKind.MEMORY_BATCH:
            raise ExecutionStateError("Expected a Memory batch")
        record = await batch_persistence.read_batch(
            session, writer.scope.job_file_id, writer.scope.execution_id
        )
        if record is None or record.status != "open":
            raise MemoryCandidateStateError("No open Memory batch")
        return MemoryBatchWork(
            writer,
            candidate_queries.batch_position(record),
            candidate_queries.source_window(record),
        )
