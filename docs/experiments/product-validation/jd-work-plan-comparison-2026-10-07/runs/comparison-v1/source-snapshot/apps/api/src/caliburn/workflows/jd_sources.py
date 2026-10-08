"""Qualify JD evidence through its source owner within A's fixed visible scope."""

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.features.executions import service as executions
from caliburn.features.executions.models import ExecutionStateError, ExecutionStatus
from caliburn.features.interviews import queries as interviews
from caliburn.features.interviews.models import InterviewReadScope
from caliburn.features.job_description.sources import (
    InterviewSource,
    InvalidJdSourceError,
    JdSource,
    MemorySource,
    MemorySourceLayer,
)
from caliburn.features.work_memory import candidate_queries as memory
from caliburn.features.work_memory.changes import resolve_title
from caliburn.features.work_memory.revisions import MemoryLayer
from caliburn.workflows.memory_reads import PublishedMemoryRead


@dataclass(frozen=True, slots=True)
class InterviewSourceSelection:
    interview_sequence: int


@dataclass(frozen=True, slots=True)
class CurrentInputSourceSelection:
    pass


@dataclass(frozen=True, slots=True)
class MemorySourceSelection:
    layer: MemorySourceLayer
    target_title: str


type JdSourceSelection = (
    InterviewSourceSelection | CurrentInputSourceSelection | MemorySourceSelection
)


async def resolve_jd_source(
    session: AsyncSession, binding: PublishedMemoryRead, selection: JdSourceSelection
) -> JdSource:
    """Resolve model choices to real immutable identities; do not accept model versions/IDs."""
    await _require_active(session, binding)
    job_file_id = binding.scope.job_file_id
    if isinstance(selection, CurrentInputSourceSelection):
        original = await interviews.read_execution_input(
            session, job_file_id=job_file_id, execution_id=binding.scope.execution_id
        )
        return InterviewSource(original.source_id)
    if isinstance(selection, InterviewSourceSelection):
        messages = await interviews.read_interview_messages(
            session,
            InterviewReadScope(job_file_id, binding.interview_through_sequence),
            sequences=(selection.interview_sequence,),
        )
        return InterviewSource(messages[0].source_id)
    await _require_snapshot(session, binding)
    assert binding.snapshot_id is not None
    entries = await memory.read_snapshot_map(
        session, job_file_id, binding.snapshot_id, MemoryLayer(selection.layer.value)
    )
    object_id = resolve_title(entries, selection.target_title)
    revision = await memory.read_snapshot_object(
        session, job_file_id, binding.snapshot_id, object_id
    )
    return MemorySource(selection.layer, binding.snapshot_id, object_id, revision.revision_id)


async def resolve_aligned_jd_source(
    session: AsyncSession, binding: PublishedMemoryRead, original: JdSource
) -> JdSource:
    """Align by the existing citation identity, never by a reused historical title."""
    await _require_active(session, binding)
    job_file_id = binding.scope.job_file_id
    if isinstance(original, InterviewSource):
        current = await interviews.read_execution_input(
            session, job_file_id=job_file_id, execution_id=binding.scope.execution_id
        )
        if original.source_id != current.source_id:
            await interviews.read_interview_sources(
                session,
                InterviewReadScope(job_file_id, binding.interview_through_sequence),
                source_ids=(original.source_id,),
            )
        return original
    await _require_snapshot(session, binding)
    assert binding.snapshot_id is not None
    selected = await memory.read_snapshot_object(
        session, job_file_id, binding.snapshot_id, original.object_id
    )
    if selected.layer.value != original.layer.value:
        raise InvalidJdSourceError("The original source is not in the selected layer")
    return MemorySource(
        original.layer, binding.snapshot_id, original.object_id, selected.revision_id
    )


async def _require_active(session: AsyncSession, binding: PublishedMemoryRead) -> None:
    if (await executions.read_execution(session, binding.scope)).status != ExecutionStatus.ACTIVE:
        raise ExecutionStateError("This Turn cannot qualify new JD evidence")


async def _require_snapshot(session: AsyncSession, binding: PublishedMemoryRead) -> None:
    if binding.snapshot_id is None:
        raise InvalidJdSourceError("No Memory snapshot was selected for this Turn")
    snapshot = await memory.read_snapshot(session, binding.scope.job_file_id, binding.snapshot_id)
    if snapshot.covered_through_sequence > binding.interview_through_sequence:
        raise InvalidJdSourceError("The Memory source exceeds this Turn's visible interviews")
