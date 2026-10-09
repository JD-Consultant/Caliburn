"""Collaborator commands share fixed JD revisions and a caller-selected editing scope."""

from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.features.job_description import (
    collaborator_persistence,
    persistence,
    revision_editing,
)
from caliburn.features.job_description.candidates import JdCandidateScope
from caliburn.features.job_description.collaborator_changes import apply_collaborator_change
from caliburn.features.job_description.collaborators import (
    EditJdCollaborators,
    JdCollaboratorsRevision,
    collaborator_change_payload,
)
from caliburn.features.job_description.models import (
    JdProfileRevision,
    StaleJdRevisionError,
)


async def read_collaborators(session: AsyncSession, job_file_id: UUID) -> JdCollaboratorsRevision:
    head = await persistence.read_document(session, job_file_id)
    return JdCollaboratorsRevision(
        head.current_revision_id,
        await collaborator_persistence.read_collaborators(
            session, job_file_id, head.current_revision_id
        ),
    )


async def recover_collaborator_result(
    session: AsyncSession,
    job_file_id: UUID,
    command: EditJdCollaborators,
    *,
    candidate: JdCandidateScope | None = None,
) -> JdCollaboratorsRevision | None:
    operation = await revision_editing.read_edit_operation(
        session, job_file_id, command.command_id, candidate
    )
    if operation is None:
        return None
    revision_editing.require_matching_edit_intent(
        operation,
        kind="edit_collaborators",
        expected_revision_id=command.expected_revision_id,
        request_payload=collaborator_change_payload(command.change),
    )
    return JdCollaboratorsRevision(
        operation.result_revision_id,
        await collaborator_persistence.read_collaborators(
            session, job_file_id, operation.result_revision_id
        ),
    )


async def edit_collaborators(
    session: AsyncSession,
    job_file_id: UUID,
    command: EditJdCollaborators,
    *,
    candidate: JdCandidateScope | None = None,
) -> JdCollaboratorsRevision:
    """Call after original-result lookup, file lock and scope admission; do not commit."""
    revision_id = await revision_editing.read_edit_revision(session, job_file_id, candidate)
    current = JdCollaboratorsRevision(
        revision_id,
        await collaborator_persistence.read_collaborators(session, job_file_id, revision_id),
    )
    if current.revision_id != command.expected_revision_id:
        raise StaleJdRevisionError("Read the current JD before submitting a new edit")
    collaborators, new_content = apply_collaborator_change(current.collaborators, command.change)
    result = current
    if collaborators != current.collaborators:
        if new_content is not None:
            await collaborator_persistence.insert_collaborator_content(
                session, job_file_id, new_content
            )
        profile = await persistence.read_revision(session, job_file_id, current.revision_id)
        result = JdCollaboratorsRevision(uuid4(), collaborators)
        await persistence.insert_revision(
            session,
            job_file_id,
            JdProfileRevision(result.revision_id, profile.profile),
            parent_revision_id=current.revision_id,
            collaborators=collaborators,
        )
    await revision_editing.record_edit(
        session,
        job_file_id,
        command_id=command.command_id,
        kind="edit_collaborators",
        expected_revision_id=command.expected_revision_id,
        result_revision_id=result.revision_id,
        request_payload=collaborator_change_payload(command.change),
        candidate=candidate,
    )
    return result
