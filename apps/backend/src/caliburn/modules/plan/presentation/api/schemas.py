"""Plan 目前內容的 HTTP 投影；初始化與寫入不開放 HTTP。"""

from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from caliburn.modules.plan.domain.snapshot import MAX_PLAN_VERSION


class PlanResponse(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    workspace_id: UUID
    version: Annotated[int, Field(ge=1, le=MAX_PLAN_VERSION)] | None
    body: str | None
