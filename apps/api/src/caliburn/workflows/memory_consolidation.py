"""A's durable intent and system-only batch admission; no provider I/O or user controls."""

from uuid import UUID, uuid4, uuid5

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from caliburn.features.executions import memory_discovery
from caliburn.features.executions import service as executions
from caliburn.features.executions.models import (
    ExecutionKind,
    ExecutionScope,
    ExecutionStateError,
    ExecutionStatus,
    ExecutionWriter,
)
from caliburn.features.interviews import queries as interviews
from caliburn.features.interviews import service as interview_service
from caliburn.features.job_files import service as job_files
from caliburn.features.work_memory import batch_persistence, candidate_lifecycle, candidate_queries
from caliburn.features.work_memory import consolidation_requests as requests
from caliburn.features.work_memory.batch_models import MemoryBatchWork
from caliburn.features.work_memory.candidates import MemoryCandidateStateError
from caliburn.workflows.memory_candidates import start_memory_candidate


class MemoryConsolidationWorkflow:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions

    async def request(self, writer: ExecutionWriter, command_id: UUID) -> dict[str, object]:
        """Tool hook: request only; its effect becomes eligible with atomic A completion.

        No source/sequence/version parameter is model-supplied. Multiple tool calls in
        the same Turn remain one effective frontier. Cancelled/failed A never qualifies.
        """
        if writer.scope.kind != ExecutionKind.CONSULTANT_TURN:
            raise ExecutionStateError("Only the consultant may request consolidation")
        async with self.sessions.begin() as session:
            await job_files.lock_job_file(session, writer.scope.job_file_id)
            await executions.lock_active_writer(session, writer)
            source = await interviews.read_execution_input(
                session,
                job_file_id=writer.scope.job_file_id,
                execution_id=writer.scope.execution_id,
            )
            # Existing operation identity guarantees replay of the original observation.
            payload: dict[str, object] = {"source_id": str(source.source_id)}
            result = await requests.record_operation(
                session,
                job_file_id=writer.scope.job_file_id,
                execution_id=writer.scope.execution_id,
                command_id=command_id,
                kind="consolidation_intent",
                payload=payload,
                result={
                    "source_id": str(source.source_id),
                    "message": "已記錄整理要求；本輪成功完成後由系統處理。",
                },
            )
            return {"message": result["message"]}

    async def discover(self) -> tuple[UUID, ...]:
        """Return job files needing system work; a lost in-memory wakeup loses no intent."""
        async with self.sessions() as session:
            active = await memory_discovery.list_active_memory(session)
            file_ids = {entry.scope.job_file_id for entry in active}
            file_ids.update(intent.job_file_id for intent in await requests.list_intents(session))
            ready = []
            for file_id in sorted(file_ids):
                if await requests.read_block(session, file_id) is not None:
                    continue
                if (
                    any(entry.scope.job_file_id == file_id for entry in active)
                    or await self._pending_source(session, file_id) is not None
                ):
                    ready.append(file_id)
            return tuple(ready)

    async def claim(self, job_file_id: UUID, *, writer_id: UUID) -> MemoryBatchWork | None:
        """Leader-only admission/recovery; retain writer_id across an unknown COMMIT.

        Caller MUST hold the local deployment's supervision fence before replacing a
        writer, and ensure its previous task is gone. SQL fencing is not liveness proof.
        """
        async with self.sessions.begin() as session:
            await job_files.lock_job_file(session, job_file_id)
            if await requests.read_block(session, job_file_id) is not None:
                return None
            active = await memory_discovery.read_active_memory(session, job_file_id)
            if active is None:
                source_id = await self._pending_source(session, job_file_id)
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
        async with self.sessions() as session:
            execution = await executions.read_execution(session, scope)
            if execution.writer_id is None or execution.status != ExecutionStatus.ACTIVE:
                raise ExecutionStateError("Memory work is not active")
            return await self._read_work(session, ExecutionWriter(scope, execution.writer_id))

    async def failure_reason(self, job_file_id: UUID) -> str | None:
        async with self.sessions() as session:
            return await requests.read_block(session, job_file_id)

    async def fail(self, writer: ExecutionWriter, *, reason: str) -> None:
        """Known terminal failure only; unknown saves/COMMIT propagate for reconciliation."""
        if writer.scope.kind != ExecutionKind.MEMORY_BATCH or not reason or len(reason) > 100:
            raise ValueError("A Memory failure requires a short classified reason code")
        async with self.sessions.begin() as session:
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
            await requests.record_operation(
                session,
                job_file_id=writer.scope.job_file_id,
                execution_id=writer.scope.execution_id,
                command_id=uuid5(writer.scope.execution_id, "memory.failure"),
                kind="batch_failure",
                payload={"reason": reason},
                result={"reason": reason},
            )

    async def release_block(self, scope: ExecutionScope, *, condition_change_id: UUID) -> None:
        """System hook ONLY after verified external condition change; never a UI retry endpoint.

        New notifications cannot call this or reset budgets. The abandoned work stays failed;
        subsequent admission starts from the still-published coverage, without skipping inputs.
        """
        if scope.kind != ExecutionKind.MEMORY_BATCH:
            raise ExecutionStateError("Only a failed Memory batch can release a block")
        async with self.sessions.begin() as session:
            await job_files.lock_job_file(session, scope.job_file_id)
            if (await executions.read_execution(session, scope)).status != ExecutionStatus.FAILED:
                raise ExecutionStateError("The Memory batch is not failed")
            await requests.record_operation(
                session,
                job_file_id=scope.job_file_id,
                execution_id=scope.execution_id,
                command_id=uuid5(scope.execution_id, "memory.release_block"),
                kind="batch_block_released",
                payload={"condition_change_id": str(condition_change_id)},
                result={},
            )

    async def _pending_source(self, session: AsyncSession, job_file_id: UUID) -> UUID | None:
        head = await candidate_queries.read_latest_snapshot(session, job_file_id)
        frontier = head.covered_through_sequence if head is not None else 0
        selected = None
        for intent in await requests.list_intents(session, job_file_id):
            scope = ExecutionScope(job_file_id, intent.execution_id, ExecutionKind.CONSULTANT_TURN)
            if (
                await executions.read_execution(session, scope)
            ).status != ExecutionStatus.COMPLETED:
                continue
            exchange = await interview_service.read_formal_exchange(
                session, job_file_id=job_file_id, execution_id=intent.execution_id
            )
            if exchange is None or exchange.employee_input.source_id != intent.source_id:
                raise MemoryCandidateStateError(
                    "Completed intent has no matching formal employee source"
                )
            if exchange.employee_input.interview_sequence > frontier:
                frontier = exchange.employee_input.interview_sequence
                selected = intent.source_id
        return selected

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
