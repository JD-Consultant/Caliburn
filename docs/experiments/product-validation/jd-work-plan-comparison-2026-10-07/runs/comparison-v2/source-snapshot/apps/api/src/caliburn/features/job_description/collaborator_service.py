"""Collaborator commands share fixed JD revisions and a caller-selected editing scope."""

from dataclasses import replace
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.features.job_description import (
    collaborator_persistence,
    persistence,
    revision_editing,
)
from caliburn.features.job_description.candidates import JdCandidateScope
from caliburn.features.job_description.collaborators import (
    Collaborator,
    CollaboratorChange,
    CollaboratorField,
    CollaboratorNotFoundError,
    CreateCollaborator,
    DeleteCollaborator,
    EditJdCollaborators,
    JdCollaboratorsRevision,
    ReorderCollaborator,
    ReviseCollaborator,
    collaborator_change_payload,
)
from caliburn.features.job_description.models import (
    JdCommandConflictError,
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
    if (
        operation.kind != "edit_collaborators"
        or operation.expected_revision_id != command.expected_revision_id
        or operation.request_payload != collaborator_change_payload(command.change)
    ):
        raise JdCommandConflictError("command_id was already used with different JD intent")
    return JdCollaboratorsRevision(
        operation.result_revision_id,
        await collaborator_persistence.read_collaborators(
            session, job_file_id, operation.result_revision_id
        ),
    )


def _apply_change(
    collaborators: tuple[Collaborator, ...], change: CollaboratorChange
) -> tuple[tuple[Collaborator, ...], Collaborator | None]:
    """Return ordered membership and, only for changed text, one new fixed content revision."""
    if isinstance(change, CreateCollaborator):
        created = Collaborator(uuid4(), uuid4(), change.name, change.scope_text)
        return (*collaborators, created), created
    target = next(
        (
            collaborator
            for collaborator in collaborators
            if collaborator.collaborator_id == change.collaborator_id
        ),
        None,
    )
    if target is None:
        raise CollaboratorNotFoundError("Collaborator is not in the selected JD")
    if isinstance(change, ReviseCollaborator):
        name, scope_text = target.name, target.scope_text
        for item in change.changes:
            if item.field is CollaboratorField.NAME:
                name = item.value
            else:
                scope_text = item.value
        revised = replace(target, name=name, scope_text=scope_text)
        if revised == target:
            return collaborators, None
        revised = replace(revised, content_revision_id=uuid4())
        return tuple(
            revised if collaborator.collaborator_id == target.collaborator_id else collaborator
            for collaborator in collaborators
        ), revised
    remaining = tuple(
        collaborator
        for collaborator in collaborators
        if collaborator.collaborator_id != target.collaborator_id
    )
    if isinstance(change, DeleteCollaborator):
        return remaining, None
    if isinstance(change, ReorderCollaborator):
        if change.before_collaborator_id == target.collaborator_id:
            return collaborators, None
        if change.before_collaborator_id is None:
            return (*remaining, target), None
        for index, neighbour in enumerate(remaining):
            if neighbour.collaborator_id == change.before_collaborator_id:
                return (*remaining[:index], target, *remaining[index:]), None
        raise CollaboratorNotFoundError("Ordering neighbour is not in this JD")
    raise TypeError("Unsupported collaborator change")


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
    collaborators, new_content = _apply_change(current.collaborators, command.change)
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
