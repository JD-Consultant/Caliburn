"""Typed collaborator HTTP intents; no storage or transaction logic."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException

from caliburn.contracts.generated import edit_jd_collaborators_request as wire
from caliburn.contracts.generated.jd_collaborators_view import Collaborator, JdCollaboratorsView
from caliburn.features.job_description import collaborators
from caliburn.features.job_files.models import JobFileNotFoundError
from caliburn.transport.http.contracts import canonical_body
from caliburn.transport.http.jd_dependencies import JdEditing

router = APIRouter(prefix="/api/job-files/{job_file_id}/jd", tags=["job-description"])


def _change_from_wire(
    change: wire.CreateCollaborator
    | wire.ReviseCollaborator
    | wire.DeleteCollaborator
    | wire.ReorderCollaborator,
) -> collaborators.CollaboratorChange:
    match change:
        case wire.CreateCollaborator():
            return collaborators.CreateCollaborator(
                change.name.root if change.name else None,
                change.scope_text.root if change.scope_text else None,
            )
        case wire.ReviseCollaborator():
            return collaborators.ReviseCollaborator(
                change.collaborator_id,
                tuple(
                    collaborators.CollaboratorFieldChange(
                        collaborators.CollaboratorField(item.field.value),
                        item.value.root if item.value else None,
                    )
                    for item in change.changes
                ),
            )
        case wire.DeleteCollaborator():
            return collaborators.DeleteCollaborator(change.collaborator_id)
        case wire.ReorderCollaborator():
            return collaborators.ReorderCollaborator(
                change.collaborator_id, change.before_collaborator_id
            )


def collaborators_view(result: collaborators.JdCollaboratorsRevision) -> JdCollaboratorsView:
    return JdCollaboratorsView(
        revision_id=result.revision_id,
        collaborators=[
            Collaborator(
                collaborator_id=collaborator.collaborator_id,
                name=collaborator.name,
                scope_text=collaborator.scope_text,
            )
            for collaborator in result.collaborators
        ],
    )


@router.get("/collaborators", response_model=JdCollaboratorsView)
async def read_collaborators(job_file_id: UUID, workflow: JdEditing) -> JdCollaboratorsView:
    try:
        return collaborators_view(await workflow.read_collaborators(job_file_id))
    except JobFileNotFoundError as error:
        raise HTTPException(status_code=404, detail={"code": "job_file_not_found"}) from error


@router.post("/collaborators", response_model=JdCollaboratorsView)
async def edit_collaborators(
    job_file_id: UUID,
    body: Annotated[
        wire.EditJdCollaboratorsRequest, canonical_body(wire.EditJdCollaboratorsRequest)
    ],
    workflow: JdEditing,
) -> JdCollaboratorsView:
    try:
        command = collaborators.EditJdCollaborators(
            body.command_id, body.expected_revision_id, _change_from_wire(body.change)
        )
        return collaborators_view(await workflow.edit_collaborators(job_file_id, command))
    except JobFileNotFoundError as error:
        raise HTTPException(status_code=404, detail={"code": "job_file_not_found"}) from error
    except collaborators.CollaboratorNotFoundError as error:
        raise HTTPException(
            status_code=404, detail={"code": "jd_collaborator_not_found"}
        ) from error
    except collaborators.InvalidCollaboratorChangeError as error:
        raise HTTPException(
            status_code=422, detail={"code": "invalid_collaborator_change"}
        ) from error
