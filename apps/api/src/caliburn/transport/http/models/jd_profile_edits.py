"""Profile HTTP 意圖；欄名直接共用 JD 的值詞彙。"""

from typing import Annotated, Literal

from pydantic import Field

from caliburn.features.job_description.models import ProfileField
from caliburn.transport.http.models.common import HttpModel, NonblankText, WireUuid


class SetField(HttpModel):
    action: Literal["set_field"]
    field: ProfileField
    value: NonblankText


class ClearField(HttpModel):
    action: Literal["clear_field"]
    field: ProfileField


class ReviseJdProfileRequest(HttpModel):
    command_id: WireUuid
    expected_revision_id: WireUuid
    changes: list[Annotated[SetField | ClearField, Field(discriminator="action")]] = Field(
        min_length=1, max_length=4
    )
