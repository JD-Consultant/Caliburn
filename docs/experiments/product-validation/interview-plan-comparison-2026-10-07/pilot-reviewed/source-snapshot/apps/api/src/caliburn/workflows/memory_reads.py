"""App-bound Memory reads shared by the consultant and both analysis roles."""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from caliburn.features.executions import service as executions
from caliburn.features.executions.models import (
    ExecutionKind,
    ExecutionScope,
    ExecutionStateError,
    ExecutionStatus,
)
from caliburn.features.interviews import queries as interviews
from caliburn.features.interviews.models import InterviewMessage, InterviewReadScope
from caliburn.features.work_memory import candidate_queries, read_queries
from caliburn.features.work_memory.candidates import MemoryBatchPosition, MemoryPermissionError
from caliburn.features.work_memory.changes import resolve_title
from caliburn.features.work_memory.models import MemoryMapEntry
from caliburn.features.work_memory.read_models import MemoryObjectDetails, MemoryReadView
from caliburn.features.work_memory.revisions import MemoryLayer


@dataclass(frozen=True, slots=True)
class PublishedMemoryRead:
    """Restored from A's original Turn binding, never recalculated from latest."""

    scope: ExecutionScope
    snapshot_id: UUID | None
    interview_through_sequence: int

    def __post_init__(self) -> None:
        if self.scope.kind != ExecutionKind.CONSULTANT_TURN:
            raise MemoryPermissionError("Published model reads require a consultant Turn")
        InterviewReadScope(self.scope.job_file_id, self.interview_through_sequence)


@dataclass(frozen=True, slots=True)
class CandidateMemoryRead:
    """Stage stays fixed; each call sees that stage's latest valid candidate position."""

    scope: ExecutionScope
    stage: MemoryBatchPosition

    def __post_init__(self) -> None:
        if self.scope.kind != ExecutionKind.MEMORY_BATCH or (
            self.scope.job_file_id,
            self.scope.execution_id,
        ) != (self.stage.job_file_id, self.stage.execution_id):
            raise MemoryPermissionError("Candidate reads require the owning Memory batch")


type MemoryReadBinding = PublishedMemoryRead | CandidateMemoryRead


class MemoryReadWorkflow:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions

    async def read_map(
        self, binding: MemoryReadBinding, layer: MemoryLayer
    ) -> tuple[MemoryMapEntry, ...]:
        async with self.sessions() as session:
            view = await _bind_view(session, binding, layer)
            return await read_queries.read_map(session, view)

    async def read_object(
        self, binding: MemoryReadBinding, layer: MemoryLayer, target_title: str
    ) -> MemoryObjectDetails:
        async with self.sessions() as session:
            view = await _bind_view(session, binding, layer)
            entries = await read_queries.read_map(session, view)
            object_id = resolve_title(entries, target_title)
            reading = await read_queries.read_object(session, view, object_id)
            messages = (
                await interviews.read_interview_sources(
                    session,
                    InterviewReadScope(view.job_file_id, view.through_sequence),
                    source_ids=tuple(reading.interview_source_ids),
                )
                if reading.interview_source_ids
                else []
            )
            return MemoryObjectDetails(
                reading.content,
                tuple(message.interview_sequence for message in messages),
                reading.work_situation_references,
            )

    async def read_interview_messages(
        self, binding: MemoryReadBinding, sequences: tuple[int, ...]
    ) -> tuple[InterviewMessage, ...]:
        async with self.sessions() as session:
            scope = await resolve_interview_scope(session, binding)
            return tuple(
                await interviews.read_interview_messages(session, scope, sequences=sequences)
            )

    async def read_interview_range(
        self, binding: MemoryReadBinding, *, start_sequence: int, end_sequence: int
    ) -> tuple[InterviewMessage, ...]:
        async with self.sessions() as session:
            scope = await resolve_interview_scope(session, binding)
            return tuple(
                await interviews.read_interview_range(
                    session, scope, start_sequence=start_sequence, end_sequence=end_sequence
                )
            )


async def _require_active(session: AsyncSession, scope: ExecutionScope) -> None:
    if (await executions.read_execution(session, scope)).status != ExecutionStatus.ACTIVE:
        raise ExecutionStateError("This execution cannot make new model tool reads")


async def _bind_view(
    session: AsyncSession, binding: MemoryReadBinding, layer: MemoryLayer
) -> MemoryReadView:
    await _require_active(session, binding.scope)
    if isinstance(binding, CandidateMemoryRead):
        return await read_queries.bind_candidate_view(session, binding.stage, layer)
    view = await read_queries.bind_published_view(
        session, binding.scope.job_file_id, binding.snapshot_id, layer
    )
    if view.through_sequence > binding.interview_through_sequence:
        raise MemoryPermissionError("Memory coverage exceeds this Turn's fixed interview scope")
    return view


async def resolve_interview_scope(
    session: AsyncSession, binding: MemoryReadBinding
) -> InterviewReadScope:
    """Validate the live App binding and retain its original Turn or batch frontier."""
    await _require_active(session, binding.scope)
    if isinstance(binding, CandidateMemoryRead):
        record = await candidate_queries.require_stage(session, binding.stage)
        return InterviewReadScope(binding.scope.job_file_id, record.through_sequence)
    return InterviewReadScope(binding.scope.job_file_id, binding.interview_through_sequence)
