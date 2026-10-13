"""職責 HTTP 意圖；內容與排序規則由 JD 擁有者判定。"""

from typing import Annotated, Literal

from pydantic import Field

from caliburn.features.job_description.areas import AreaField
from caliburn.transport.http.models.common import HttpModel, NonblankText, WireUuid


class CreateArea(HttpModel):
    action: Literal["create_area"]
    title: NonblankText | None
    scope_text: NonblankText | None


class AreaFieldChange(HttpModel):
    field: AreaField
    value: NonblankText | None


class ReviseArea(HttpModel):
    action: Literal["revise_area"]
    area_id: WireUuid
    changes: list[AreaFieldChange] = Field(min_length=1, max_length=2)


class DeleteArea(HttpModel):
    action: Literal["delete_area"]
    area_id: WireUuid


class ReorderArea(HttpModel):
    action: Literal["reorder_area"]
    area_id: WireUuid
    before_area_id: WireUuid | None


class EditJdAreasRequest(HttpModel):
    command_id: WireUuid
    expected_revision_id: WireUuid
    change: Annotated[
        CreateArea | ReviseArea | DeleteArea | ReorderArea, Field(discriminator="action")
    ]
