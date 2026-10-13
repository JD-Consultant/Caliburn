"""Typed collaborator HTTP intents; no storage or transaction logic."""

from uuid import UUID

from fastapi import APIRouter, HTTPException

from caliburn.features.job_description import collaborators
from caliburn.features.job_files.models import JobFileNotFoundError
from caliburn.transport.http.jd_dependencies import JdEditing
from caliburn.transport.http.models import jd_collaborators_edits as wire
from caliburn.transport.http.models.jd_views import Collaborator, JdCollaboratorsView

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
                change.name,
                change.scope_text,
            )
        case wire.ReviseCollaborator():
            return collaborators.ReviseCollaborator(
                change.collaborator_id,
                tuple(
                    collaborators.CollaboratorFieldChange(
                        item.field,
                        item.value,
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


@router.get(
    "/collaborators", response_model=JdCollaboratorsView, operation_id="read_jd_collaborators"
)
async def read_collaborators(job_file_id: UUID, workflow: JdEditing) -> JdCollaboratorsView:
    try:
        return collaborators_view(await workflow.read_collaborators(job_file_id))
    except JobFileNotFoundError as error:
        raise HTTPException(status_code=404, detail={"code": "job_file_not_found"}) from error


@router.post(
    "/collaborators", response_model=JdCollaboratorsView, operation_id="edit_jd_collaborators"
)
async def edit_collaborators(
    job_file_id: UUID,
    body: wire.EditJdCollaboratorsRequest,
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
