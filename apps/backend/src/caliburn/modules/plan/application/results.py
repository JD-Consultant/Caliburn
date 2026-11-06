"""目前 Plan 的不可變投影與 patch 實際效果。"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class PlanView:
    workspace_id: UUID
    version: int | None
    body: str | None


@dataclass(frozen=True)
class PatchPlanResult:
    plan: PlanView
    changed: bool
    diff: str | None
