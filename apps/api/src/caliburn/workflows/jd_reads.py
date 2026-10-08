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
from caliburn.workflows.jd_candidates import JdCandidateWorkflow
from caliburn.workflows.jd_source_queries import read_memory_source_title_batch
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
            memory_titles = await read_memory_source_title_batch(
                session,
                job_file_id=binding.scope.job_file_id,
                sources=tuple(
                    reference.source
                    for reference in selected
                    if isinstance(reference.source, MemorySource)
                ),
                snapshot_id=binding.snapshot_id,
                interview_through_sequence=binding.interview_through_sequence,
            )
            readings = []
            for reference in selected:
                source = reference.source
                if isinstance(source, InterviewSource):
                    readings.append(
                        JdSourceReading(reference, interview_sequence=sequences[source])
                    )
                    continue
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


def resolve_jd_citation_ref(
    references: tuple[JdSourceReference, ...], citation_ref: str
) -> JdSourceReference:
    """The caller supplies the scoped source tuple; an echoed ref grants no extra scope."""
    for reference in references:
        if citation_ref == f"citation_{reference.citation_id.hex}":
            return reference
    raise JdReadTargetNotFoundError("No such citation in the scoped JD references")
