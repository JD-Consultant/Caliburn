"""Pure collaborator membership and content transformations."""

from dataclasses import replace
from uuid import uuid4

from caliburn.features.job_description.collaborators import (
    Collaborator,
    CollaboratorChange,
    CollaboratorField,
    CollaboratorNotFoundError,
    CreateCollaborator,
    DeleteCollaborator,
    ReorderCollaborator,
    ReviseCollaborator,
)


def apply_collaborator_change(
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
