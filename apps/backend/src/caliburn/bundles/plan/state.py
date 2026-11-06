"""Plan 自有持久版本；正文只由 Plan 模組保存。"""

from typing import TypedDict
from uuid import UUID


class PlanState(TypedDict):
    plan_turn_id: UUID
    plan_turn_start_version: int
    plan_version: int | None


class PlanTurnState(TypedDict):
    workspace_id: UUID
    turn_id: UUID


class PlanToolState(TypedDict):
    workspace_id: UUID
    plan_version: int | None
