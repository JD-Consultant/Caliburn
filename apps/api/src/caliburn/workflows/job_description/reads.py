"""Read one A candidate and its direct evidence through the original data owners."""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from caliburn.adapters.database import consistent_read_session
from caliburn.features.executions import service as executions
from caliburn.features.executions.models import ExecutionStateError, ExecutionStatus
from caliburn.features.interviews import queries as interviews
from caliburn.features.interviews.models import InterviewReadScope
from caliburn.features.job_description import source_persistence
from caliburn.features.job_description.candidate_service import JdCandidatePreview
from caliburn.features.job_description.navigation import JdReadTargetNotFoundError
from caliburn.features.job_description.sources import (
    InterviewSource,
    JdSourceReference,
    JdSourceTarget,
    MemorySource,
)
from caliburn.workflows.job_description.candidates import JdCandidateWorkflow
from caliburn.workflows.job_description.source_queries import (
    MemorySourceVersion,
    read_memory_source_metadata_batch,
)
from caliburn.workflows.work_memory.reads import PublishedMemoryRead


@dataclass(frozen=True, slots=True)
class JdSourceReading:
    """Qualified read hints only; no source bodies or replacement identities."""

    reference: JdSourceReference
    interview_sequence: int | None = None
    target_title: str | None = None
    historical_title: str | None = None
    source_changed: bool = False
    source_version: MemorySourceVersion | None = None
    comparison_version: MemorySourceVersion | None = None

    @property
    def jd_changed(self) -> bool:
        return self.reference.needs_review

    @property
    def needs_recheck(self) -> bool:
        return self.jd_changed or self.source_changed


class JdReadWorkflow:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions

    async def read_candidate(self, binding: PublishedMemoryRead) -> JdCandidatePreview:
        return await JdCandidateWorkflow(self.sessions).read(binding.scope)

    async def read_sources(
        self,
        binding: PublishedMemoryRead,
        candidate: JdCandidatePreview,
        targets: tuple[JdSourceTarget, ...] | None = None,
    ) -> tuple[JdSourceReading, ...]:
        """Resolve only requested evidence from the candidate revision already read.

        Concurrent candidate edits cannot switch these references to a later head.
        Missing fixed source data is an error, not an empty evidence list or deletion.
        """
        if candidate.position.scope.execution_id != binding.scope.execution_id:
            raise ExecutionStateError("The candidate belongs to a different Turn")
        async with consistent_read_session(self.sessions) as session:
            execution = await executions.read_execution(session, binding.scope)
            if execution.status not in (ExecutionStatus.ACTIVE, ExecutionStatus.PAUSED):
                raise ExecutionStateError("This Turn no longer has a readable JD candidate")
            current_id = await interviews.read_execution_input_source_id(
                session,
                job_file_id=binding.scope.job_file_id,
                execution_id=binding.scope.execution_id,
            )
            return await read_jd_source_readings(
                session,
                job_file_id=binding.scope.job_file_id,
                revision_id=candidate.position.revision_id,
                snapshot_id=binding.snapshot_id,
                interview_through_sequence=binding.interview_through_sequence,
                current_input_source_id=current_id,
                targets=targets,
            )


async def read_jd_source_readings(
    session: AsyncSession,
    *,
    job_file_id: UUID,
    revision_id: UUID,
    snapshot_id: UUID | None,
    interview_through_sequence: int,
    current_input_source_id: UUID | None,
    targets: tuple[JdSourceTarget, ...] | None = None,
) -> tuple[JdSourceReading, ...]:
    """在 caller 已准入的同一交易組裝標頭；不擴權、不讀正文或逐項 diff。"""
    references = await source_persistence.read_source_references(session, job_file_id, revision_id)
    selected = tuple(
        reference for reference in references if targets is None or reference.target in targets
    )
    sequences = await _interview_sequences(
        session, job_file_id, interview_through_sequence, current_input_source_id, selected
    )
    metadata = await read_memory_source_metadata_batch(
        session,
        job_file_id=job_file_id,
        sources=tuple(ref.source for ref in selected if isinstance(ref.source, MemorySource)),
        snapshot_id=snapshot_id,
        interview_through_sequence=interview_through_sequence,
    )
    readings = []
    for reference in selected:
        source = reference.source
        if isinstance(source, InterviewSource):
            readings.append(JdSourceReading(reference, interview_sequence=sequences[source]))
        else:
            item = metadata[source]
            readings.append(
                JdSourceReading(
                    reference,
                    target_title=item.target_title,
                    historical_title=item.historical_title,
                    source_changed=item.source_changed,
                    source_version=item.source_version,
                    comparison_version=item.comparison_version,
                )
            )
    return tuple(readings)


async def _interview_sequences(
    session: AsyncSession,
    job_file_id: UUID,
    interview_through_sequence: int,
    current_id: UUID | None,
    references: tuple[JdSourceReference, ...],
) -> dict[InterviewSource, int]:
    selected = tuple(
        reference.source
        for reference in references
        if isinstance(reference.source, InterviewSource)
    )
    if not selected:
        return {}
    formal_ids = tuple(source.source_id for source in selected if source.source_id != current_id)
    messages = (
        await interviews.read_interview_source_headers(
            session,
            InterviewReadScope(job_file_id, interview_through_sequence),
            source_ids=formal_ids,
        )
        if formal_ids
        else []
    )
    result = {
        InterviewSource(message.source_id): message.interview_sequence for message in messages
    }
    if current_id is not None:
        result[InterviewSource(current_id)] = interview_through_sequence + 1
    return result


def resolve_jd_citation_ref(
    references: tuple[JdSourceReference, ...], citation_ref: str
) -> JdSourceReference:
    """The caller supplies the scoped source tuple; an echoed ref grants no extra scope."""
    for reference in references:
        if citation_ref == f"citation_{reference.citation_id.hex}":
            return reference
    raise JdReadTargetNotFoundError("No such citation in the scoped JD references")
