"""能力及任務關係的 HTTP 意圖。"""

from typing import Annotated, Literal, Self

from pydantic import ConfigDict, Field, StrictBool, model_validator

from caliburn.features.job_description.capabilities import (
    CapabilityField,
    CapabilityKind,
    validate_capability_text,
)
from caliburn.transport.http.models.common import HttpModel, NonblankText, WireUuid


class CreateCapability(HttpModel):
    model_config = ConfigDict(
        json_schema_extra={
            "anyOf": [
                {"properties": {"name": {"type": "string"}}},
                {"properties": {"description": {"type": "string"}}},
            ]
        }
    )
    action: Literal["create_capability"]
    kind: CapabilityKind
    name: NonblankText | None
    description: NonblankText | None

    @model_validator(mode="after")
    def meaningful_content(self) -> Self:
        validate_capability_text(self.name, self.description)
        return self


class FieldChange(HttpModel):
    field: CapabilityField
    value: NonblankText | None


class ReviseCapability(HttpModel):
    action: Literal["revise_capability"]
    capability_id: WireUuid
    changes: list[FieldChange] = Field(min_length=1, max_length=2)


class DeleteCapability(HttpModel):
    action: Literal["delete_capability"]
    capability_id: WireUuid


class ReorderCapability(HttpModel):
    action: Literal["reorder_capability"]
    capability_id: WireUuid
    before_capability_id: WireUuid | None


class SetTaskCapability(HttpModel):
    action: Literal["set_task_capability"]
    task_id: WireUuid
    capability_id: WireUuid
    linked: StrictBool


class ReorderTaskCapability(HttpModel):
    action: Literal["reorder_task_capability"]
    task_id: WireUuid
    capability_id: WireUuid
    before_capability_id: WireUuid | None


class EditJdCapabilitiesRequest(HttpModel):
    command_id: WireUuid
    expected_revision_id: WireUuid
    change: Annotated[
        CreateCapability
        | ReviseCapability
        | DeleteCapability
        | ReorderCapability
        | SetTaskCapability
        | ReorderTaskCapability,
        Field(discriminator="action"),
    ]
