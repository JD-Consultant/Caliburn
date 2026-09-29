"""Read one A candidate and its direct evidence through the original data owners."""

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from caliburn.features.executions import service as executions
from caliburn.features.executions.models import ExecutionStateError, ExecutionStatus
from caliburn.features.interviews import queries as interviews
from caliburn.features.interviews.models import InterviewInputNotFoundError, InterviewReadScope
from caliburn.features.job_description import source_persistence
from caliburn.features.job_description.candidate_service import JdCandidatePreview
from caliburn.features.job_description.navigation import JdReadTargetNotFoundError
from caliburn.features.job_description.sources import (
    InterviewSource,
    JdSourceReference,
    JdSourceTarget,
    MemorySource,
)
from caliburn.features.work_memory import candidate_queries, read_queries
from caliburn.features.work_memory.candidates import MemoryPermissionError
from caliburn.features.work_memory.revisions import MemoryLayer, MemoryRevisionNotFoundError
from caliburn.workflows.jd_candidates import JdCandidateWorkflow
from caliburn.workflows.memory_reads import PublishedMemoryRead


@dataclass(frozen=True, slots=True)
class JdSourceReading:
    """Qualified read hints only; no source bodies or replacement identities."""

    reference: JdSourceReference
    interview_sequence: int | None = None
    target_title: str | None = None
    historical_title: str | None = None
    needs_recheck: bool = False


class JdReadWorkflow:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions

    async def read_candidate(self, binding: PublishedMemoryRead) -> JdCandidatePreview:
        return await JdCandidateWorkflow(self.sessions).read(binding.scope)

    async def read_sources(
        self,
        binding: PublishedMemoryRead,
        candidate: JdCandidatePreview,
        targets: tuple[JdSourceTarget, ...],
    ) -> tuple[JdSourceReading, ...]:
        """Resolve only requested evidence from the candidate revision already read.

        Concurrent candidate edits cannot switch these references to a later head.
        Missing fixed source data is an error, not an empty evidence list or deletion.
        """
        if candidate.position.scope.execution_id != binding.scope.execution_id:
            raise ExecutionStateError("The candidate belongs to a different Turn")
        async with self.sessions() as session:
            execution = await executions.read_execution(session, binding.scope)
            if execution.status not in (ExecutionStatus.ACTIVE, ExecutionStatus.PAUSED):
                raise ExecutionStateError("This Turn no longer has a readable JD candidate")
            references = await source_persistence.read_source_references(
                session, binding.scope.job_file_id, candidate.position.revision_id
            )
            selected = tuple(reference for reference in references if reference.target in targets)
            sequences = await _interview_sequences(session, binding, selected)
            memory_titles: dict[MemorySource, tuple[str | None, str | None, bool]] = {}
            readings = []
            for reference in selected:
                source = reference.source
                if isinstance(source, InterviewSource):
                    readings.append(
                        JdSourceReading(reference, interview_sequence=sequences[source])
                    )
                    continue
                if source not in memory_titles:
                    memory_titles[source] = await _memory_titles(session, binding, source)
                title, historical_title, changed = memory_titles[source]
                readings.append(
                    JdSourceReading(
                        reference,
                        target_title=title,
                        historical_title=historical_title,
                        needs_recheck=reference.needs_review or changed,
                    )
                )
            return tuple(readings)


async def _interview_sequences(
    session: AsyncSession, binding: PublishedMemoryRead, references: tuple[JdSourceReference, ...]
) -> dict[InterviewSource, int | None]:
    selected = tuple(
        reference.source
        for reference in references
        if isinstance(reference.source, InterviewSource)
    )
    if not selected:
        return {}
    try:
        original = await interviews.read_execution_input(
            session, job_file_id=binding.scope.job_file_id, execution_id=binding.scope.execution_id
        )
    except InterviewInputNotFoundError:
        # Formal references do not require this Turn to have a pending input.
        original = None
    current_id = original.source_id if original is not None else None
    formal_ids = tuple(source.source_id for source in selected if source.source_id != current_id)
    messages = (
        await interviews.read_interview_sources(
            session,
            InterviewReadScope(binding.scope.job_file_id, binding.interview_through_sequence),
            source_ids=formal_ids,
        )
        if formal_ids
        else []
    )
    result: dict[InterviewSource, int | None] = {
        InterviewSource(message.source_id): message.interview_sequence for message in messages
    }
    if current_id is not None:
        result[InterviewSource(current_id)] = None
    return result


async def _memory_titles(
    session: AsyncSession, binding: PublishedMemoryRead, source: MemorySource
) -> tuple[str | None, str | None, bool]:
    """Return current/historical names and recheck state by fixed identity, never title lookup."""
    file_id = binding.scope.job_file_id
    original_snapshot = await candidate_queries.read_snapshot(session, file_id, source.snapshot_id)
    if original_snapshot.covered_through_sequence > binding.interview_through_sequence:
        raise MemoryPermissionError("The original source exceeds this Turn's interview scope")
    original_members = await candidate_queries.read_members(
        session, file_id, original_snapshot.position_id
    )
    original = await candidate_queries.read_selected(
        session, file_id, original_members, source.object_id
    )
    if original.revision_id != source.revision_id or original.layer.value != source.layer.value:
        raise MemoryRevisionNotFoundError("The citation does not match its original fixed snapshot")
    current_view = await read_queries.bind_published_view(
        session, file_id, binding.snapshot_id, MemoryLayer(source.layer.value)
    )
    if current_view.through_sequence > binding.interview_through_sequence:
        raise MemoryPermissionError("The pinned Memory exceeds this Turn's interview scope")
    current_members = (
        await candidate_queries.read_members(session, file_id, current_view.position_id)
        if current_view.position_id is not None
        else {}
    )
    if source.object_id not in current_members:
        # Absence is proven against complete fixed membership, not a failed body lookup.
        return None, original.content.title, True
    current = await candidate_queries.read_selected(
        session, file_id, current_members, source.object_id
    )
    if current.layer != original.layer:
        raise MemoryRevisionNotFoundError("The fixed source changed its Memory layer")
    historical_title = (
        original.content.title if original.content.title != current.content.title else None
    )
    return current.content.title, historical_title, current.revision_id != original.revision_id


def resolve_jd_citation_ref(
    references: tuple[JdSourceReference, ...], citation_ref: str
) -> JdSourceReference:
    """The caller supplies the scoped source tuple; an echoed ref grants no extra scope."""
    for reference in references:
        if citation_ref == f"citation_{reference.citation_id.hex}":
            return reference
    raise JdReadTargetNotFoundError("No such citation in the scoped JD references")
