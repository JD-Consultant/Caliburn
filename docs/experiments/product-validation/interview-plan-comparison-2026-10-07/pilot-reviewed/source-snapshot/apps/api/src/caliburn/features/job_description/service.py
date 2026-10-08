"""JD profile edits participate in the caller's scope, admission and short transaction."""

from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.features.job_description import persistence, revision_editing
from caliburn.features.job_description.candidates import JdCandidateScope
from caliburn.features.job_description.models import (
    JdCommandConflictError,
    JdProfile,
    JdProfileRevision,
    ReviseJdProfile,
    StaleJdRevisionError,
    apply_profile_changes,
    profile_change_payload,
)


async def create_empty_jd(session: AsyncSession, job_file_id: UUID) -> None:
    """Called exactly once within the new job-file creation transaction."""
    initial = JdProfileRevision(uuid4(), JdProfile())
    await persistence.insert_revision(session, job_file_id, initial, parent_revision_id=None)
    session.add(
        persistence.JobDescriptionRecord(
            job_file_id=job_file_id,
            initial_revision_id=initial.revision_id,
            current_revision_id=initial.revision_id,
        )
    )
    await session.flush()


async def recover_profile_result(
    session: AsyncSession,
    job_file_id: UUID,
    command: ReviseJdProfile,
    *,
    candidate: JdCandidateScope | None = None,
) -> JdProfileRevision | None:
    """Return the original result only; a replay does not require fresh write admission."""
    operation = await revision_editing.read_edit_operation(
        session, job_file_id, command.command_id, candidate
    )
    if operation is None:
        return None
    if (
        operation.kind != "revise_profile"
        or operation.expected_revision_id != command.expected_revision_id
        or operation.request_payload != profile_change_payload(command.changes)
    ):
        raise JdCommandConflictError("command_id was already used with different JD intent")
    return await persistence.read_revision(session, job_file_id, operation.result_revision_id)


async def revise_profile(
    session: AsyncSession,
    job_file_id: UUID,
    command: ReviseJdProfile,
    *,
    candidate: JdCandidateScope | None = None,
) -> JdProfileRevision:
    """Apply a new command after replay lookup, file lock and admission in this transaction.

    The workflow must call recover_profile_result first under the same lock. This function
    participates without committing; all specified fields and the result succeed together.
    """
    revision_id = await revision_editing.read_edit_revision(session, job_file_id, candidate)
    if revision_id != command.expected_revision_id:
        raise StaleJdRevisionError("Read the current JD before submitting a new edit")
    current = await persistence.read_revision(session, job_file_id, revision_id)
    profile = apply_profile_changes(current.profile, command.changes)
    result = current
    if profile != current.profile:
        result = JdProfileRevision(uuid4(), profile)
        await persistence.insert_revision(
            session, job_file_id, result, parent_revision_id=current.revision_id
        )
    await revision_editing.record_edit(
        session,
        job_file_id,
        command_id=command.command_id,
        kind="revise_profile",
        expected_revision_id=command.expected_revision_id,
        result_revision_id=result.revision_id,
        request_payload=profile_change_payload(command.changes),
        candidate=candidate,
    )
    return result
