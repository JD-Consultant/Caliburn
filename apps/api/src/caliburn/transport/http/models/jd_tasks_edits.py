"""任務 HTTP 意圖；不以 RootModel 再包一層文字或單項變更。"""

from typing import Annotated, Literal

from pydantic import Field

from caliburn.features.job_description.tasks import DetailKind, TaskField
from caliburn.transport.http.models.common import HttpModel, NonblankText, WireUuid


class CreateTask(HttpModel):
    action: Literal["create_task"]
    area_id: WireUuid | None
    title: NonblankText | None
    description: NonblankText | None
    outcomes: list[NonblankText]
    requirements: list[NonblankText]


class SetField(HttpModel):
    action: Literal["set_field"]
    field: TaskField
    value: NonblankText | None


class AddDetail(HttpModel):
    action: Literal["add_detail"]
    kind: DetailKind
    text: NonblankText


class ReviseDetail(HttpModel):
    action: Literal["revise_detail"]
    detail_id: WireUuid
    text: NonblankText


class RemoveDetail(HttpModel):
    action: Literal["remove_detail"]
    detail_id: WireUuid


type TaskChange = Annotated[
    SetField | AddDetail | ReviseDetail | RemoveDetail, Field(discriminator="action")
]


class ReviseTask(HttpModel):
    action: Literal["revise_task"]
    task_id: WireUuid
    changes: list[TaskChange] = Field(min_length=1)


class MoveTask(HttpModel):
    action: Literal["move_task"]
    task_id: WireUuid
    area_id: WireUuid | None
    before_task_id: WireUuid | None
    changes: list[TaskChange]


class ReorderDetail(HttpModel):
    action: Literal["reorder_detail"]
    task_id: WireUuid
    detail_id: WireUuid
    before_detail_id: WireUuid | None


class DeleteTask(HttpModel):
    action: Literal["delete_task"]
    task_id: WireUuid


class EditJdTasksRequest(HttpModel):
    command_id: WireUuid
    expected_revision_id: WireUuid
    change: Annotated[
        CreateTask | ReviseTask | MoveTask | ReorderDetail | DeleteTask,
        Field(discriminator="action"),
    ]
