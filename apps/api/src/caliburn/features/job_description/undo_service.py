"""Conditionally reverse an adopted JD to its retained base, with one original result.

The caller owns the file lock, completed-Turn qualification and manual-edit admission.
This participant never commits and never rewinds an existing revision or other owners.
"""

from uuid import UUID, uuid4, uuid5

from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.features.job_description import (
    candidate_persistence,
    persistence,
    revision_editing,
    source_persistence,
    work_queries,
)
from caliburn.features.job_description.candidates import CandidateStateError
from caliburn.features.job_description.models import (
    JdCommandConflictError,
    JdProfileRevision,
    StaleJdRevisionError,
)


def _command_id(execution_id: UUID) -> UUID:
    # One immutable undo intent per completed Turn; HTTP retries cannot change its base.
    return uuid5(execution_id, "job_description.undo_completed_turn")


async def recover_undo(
    session: AsyncSession, job_file_id: UUID, execution_id: UUID
) -> JdProfileRevision | None:
    operation = await revision_editing.read_edit_operation(
        session, job_file_id, _command_id(execution_id), None
    )
    if operation is None:
        return None
    if operation.kind != "undo_completed_turn" or operation.request_payload != {
        "execution_id": str(execution_id)
    }:
        raise JdCommandConflictError("The undo identity has different saved intent")
    return await persistence.read_revision(session, job_file_id, operation.result_revision_id)


async def undo_completed_turn(
    session: AsyncSession, job_file_id: UUID, execution_id: UUID
) -> JdProfileRevision:
    """After replay lookup and admission, apply only to the exact adopted formal revision.

    A later revision, even on another field or changed back to the same text, conflicts.
    A fresh revision retains ancestry and avoids reviving stale pre-Turn write commands.
    """
    candidate = await candidate_persistence.read_candidate(session, job_file_id, execution_id)
    if candidate is None or candidate.status != "adopted":
        raise CandidateStateError("Undo requires this Turn's retained adopted JD candidate")
    document = await persistence.read_document(session, job_file_id)
    if document.current_revision_id != candidate.current_revision_id:
        raise StaleJdRevisionError("The formal JD has changed since this Turn completed")
    base = await persistence.read_revision(session, job_file_id, candidate.base_revision_id)
    result = base
    references = await source_persistence.read_source_references(
        session, job_file_id, base.revision_id
    )
    if candidate.base_revision_id != candidate.current_revision_id:
        work = await work_queries.read_work_at(session, job_file_id, base.revision_id)
        result = JdProfileRevision(uuid4(), base.profile)
        await persistence.insert_revision(
            session,
            job_file_id,
            result,
            parent_revision_id=candidate.current_revision_id,
            areas=work.areas,
            tasks=work.tasks,
            capabilities=work.capabilities,
            task_links=work.task_links,
            collaborators=work.collaborators,
            conditions=work.conditions,
        )
    await revision_editing.record_edit(
        session,
        job_file_id,
        command_id=_command_id(execution_id),
        kind="undo_completed_turn",
        expected_revision_id=candidate.current_revision_id,
        result_revision_id=result.revision_id,
        request_payload={"execution_id": str(execution_id)},
        candidate=None,
        source_references=references,
    )
    return result
