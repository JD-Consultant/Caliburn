"""工作條件 HTTP 意圖。"""

from typing import Annotated, Literal

from pydantic import Field

from caliburn.features.job_description.conditions import ConditionKind
from caliburn.transport.http.models.common import HttpModel, NonblankText, WireUuid


class CreateCondition(HttpModel):
    action: Literal["create_condition"]
    kind: ConditionKind
    text: NonblankText


class ConditionTextChange(HttpModel):
    field: Literal["text"]
    value: NonblankText


class ConditionKindChange(HttpModel):
    field: Literal["kind"]
    value: ConditionKind


class ReviseCondition(HttpModel):
    action: Literal["revise_condition"]
    condition_id: WireUuid
    changes: list[
        Annotated[ConditionTextChange | ConditionKindChange, Field(discriminator="field")]
    ] = Field(min_length=1, max_length=2)


class DeleteCondition(HttpModel):
    action: Literal["delete_condition"]
    condition_id: WireUuid


class ReorderCondition(HttpModel):
    action: Literal["reorder_condition"]
    condition_id: WireUuid
    before_condition_id: WireUuid | None


class EditJdConditionsRequest(HttpModel):
    command_id: WireUuid
    expected_revision_id: WireUuid
    change: Annotated[
        CreateCondition | ReviseCondition | DeleteCondition | ReorderCondition,
        Field(discriminator="action"),
    ]
