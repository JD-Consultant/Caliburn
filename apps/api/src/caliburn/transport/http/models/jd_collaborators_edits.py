"""協作對象 HTTP 意圖。"""

from typing import Annotated, Literal

from pydantic import Field

from caliburn.features.job_description.collaborators import CollaboratorField
from caliburn.transport.http.models.common import HttpModel, NonblankText, WireUuid


class CreateCollaborator(HttpModel):
    action: Literal["create_collaborator"]
    name: NonblankText | None
    scope_text: NonblankText | None


class CollaboratorFieldChange(HttpModel):
    field: CollaboratorField
    value: NonblankText | None


class ReviseCollaborator(HttpModel):
    action: Literal["revise_collaborator"]
    collaborator_id: WireUuid
    changes: list[CollaboratorFieldChange] = Field(min_length=1, max_length=2)


class DeleteCollaborator(HttpModel):
    action: Literal["delete_collaborator"]
    collaborator_id: WireUuid


class ReorderCollaborator(HttpModel):
    action: Literal["reorder_collaborator"]
    collaborator_id: WireUuid
    before_collaborator_id: WireUuid | None


class EditJdCollaboratorsRequest(HttpModel):
    command_id: WireUuid
    expected_revision_id: WireUuid
    change: Annotated[
        CreateCollaborator | ReviseCollaborator | DeleteCollaborator | ReorderCollaborator,
        Field(discriminator="action"),
    ]
