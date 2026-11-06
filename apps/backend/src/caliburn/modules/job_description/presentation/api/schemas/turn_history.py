"""完成輪次固定 JD 前後版本與完整淨差異的 HTTP 回覆。"""

from uuid import UUID

from pydantic import Field

from caliburn.modules.job_description.presentation.api.schemas.common import (
    ExpectedVersion,
    ResponseModel,
)
from caliburn.modules.job_description.presentation.api.schemas.content import (
    JobDescriptionContentResponse,
)
from caliburn.modules.job_description.presentation.api.schemas.history import (
    JobDescriptionDifferenceResponse,
)


class JobDescriptionTurnChangesResponse(ResponseModel):
    workspace_id: UUID
    job_description_id: UUID
    turn_id: UUID
    before_version: ExpectedVersion = Field(description="該輪開始時固定的 JD 保存版")
    after_version: ExpectedVersion = Field(
        description=(
            "該輪正常完成時固定的模型已見 JD 保存版，無已見版則使用輪前版；"
            "不代表當時最新資料庫版本或模型必定讀過全文，"
            "版號可能小於 before_version"
        )
    )
    before: JobDescriptionContentResponse
    after: JobDescriptionContentResponse
    difference: JobDescriptionDifferenceResponse
