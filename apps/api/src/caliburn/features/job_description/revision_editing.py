"""Route the same JD edit rules to a formal head or one private candidate position.

The workflow owns admission and locking. This module never commits, admits a writer,
publishes a Turn, or changes the formal head as a shortcut for editing a candidate.
"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.features.job_description import candidate_persistence, persistence, source_persistence
from caliburn.features.job_description.candidates import CandidateStateError, JdCandidateScope
from caliburn.features.job_description.models import JdCommandConflictError, StaleJdRevisionError
from caliburn.features.job_description.source_inheritance import inherited_source_references
from caliburn.features.job_description.sources import JdSourceReference


async def require_open_candidate(
    session: AsyncSession, job_file_id: UUID, scope: JdCandidateScope
) -> candidate_persistence.JdCandidateRecord:
    candidate = await candidate_persistence.read_candidate(session, job_file_id, scope.execution_id)
    if (
        candidate is None
        or candidate.status != "open"
        or candidate.generation_id != scope.generation_id
    ):
        raise CandidateStateError("Candidate position is unavailable or superseded")
    formal = await persistence.read_document(session, job_file_id)
    if formal.current_revision_id != candidate.base_revision_id:
        raise StaleJdRevisionError("The formal JD no longer matches this candidate's base")
    return candidate


async def read_edit_revision(
    session: AsyncSession, job_file_id: UUID, candidate: JdCandidateScope | None
) -> UUID:
    if candidate is None:
        return (await persistence.read_document(session, job_file_id)).current_revision_id
    return (await require_open_candidate(session, job_file_id, candidate)).current_revision_id


async def read_edit_operation(
    session: AsyncSession, job_file_id: UUID, command_id: UUID, candidate: JdCandidateScope | None
) -> persistence.JdOperationRecord | None:
    operation = await persistence.read_operation(session, job_file_id, command_id)
    if operation is not None and (
        operation.candidate_execution_id != (candidate.execution_id if candidate else None)
        or operation.candidate_generation_id != (candidate.generation_id if candidate else None)
    ):
        raise JdCommandConflictError("command_id belongs to a different JD editing scope")
    return operation


async def record_edit(
    session: AsyncSession,
    job_file_id: UUID,
    *,
    command_id: UUID,
    kind: str,
    expected_revision_id: UUID,
    result_revision_id: UUID,
    request_payload: object,
    candidate: JdCandidateScope | None,
    source_references: tuple[JdSourceReference, ...] | None = None,
) -> None:
    if result_revision_id != expected_revision_id:
        references = source_references
        if references is None:
            references = await inherited_source_references(
                session, job_file_id, expected_revision_id, result_revision_id
            )
        await source_persistence.insert_source_references(
            session, job_file_id, result_revision_id, references
        )
    if candidate is None:
        document = await persistence.read_document(session, job_file_id)
        document.current_revision_id = result_revision_id
    else:
        draft = await require_open_candidate(session, job_file_id, candidate)
        draft.current_revision_id = result_revision_id
    session.add(
        persistence.JdOperationRecord(
            job_file_id=job_file_id,
            command_id=command_id,
            kind=kind,
            expected_revision_id=expected_revision_id,
            result_revision_id=result_revision_id,
            request_payload=request_payload,
            candidate_execution_id=candidate.execution_id if candidate else None,
            candidate_generation_id=candidate.generation_id if candidate else None,
        )
    )
    await session.flush()
