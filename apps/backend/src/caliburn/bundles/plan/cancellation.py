"""以目標輪自己的基準恢復 Plan；恢復相同內容時可安全重試。"""

import asyncio
from uuid import UUID

from caliburn.bundles.plan.services import PLAN_QUERIES, PLAN_UOW_FACTORY
from caliburn.bundles.plan.state import PlanState
from caliburn.modules.agent.plugins.contracts import AgentContext
from caliburn.modules.plan.application.errors import PlanNotInitializedError
from caliburn.modules.plan.application.plans import restore_plan


async def cancel_turn_plan(
    state: PlanState | None,
    *,
    workspace_id: UUID,
    turn_id: UUID,
    context: AgentContext,
) -> None:
    if state is None or state.get("plan_turn_id") != turn_id:
        return
    queries = context.services.require(PLAN_QUERIES)
    current = await asyncio.to_thread(queries.get_current, workspace_id=workspace_id)
    if current.version is None:
        raise PlanNotInitializedError("目標輪的 Plan 已不存在")
    await asyncio.to_thread(
        restore_plan,
        workspace_id=workspace_id,
        expected_version=current.version,
        target_version=state["plan_turn_start_version"],
        uow_factory=context.services.require(PLAN_UOW_FACTORY),
    )
