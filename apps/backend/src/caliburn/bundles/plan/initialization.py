"""新輪固定恢復基準；原輪恢復沿原生 Task 與 Checkpoint 接續。"""

from langgraph.func import task
from langgraph.runtime import Runtime

from caliburn.bundles.plan.services import PLAN_UOW_FACTORY
from caliburn.bundles.plan.state import PlanState, PlanTurnState
from caliburn.modules.agent.plugins.contracts import AgentContext
from caliburn.modules.plan.application.plans import initialize_plan


async def initialize_turn_plan(
    state: PlanTurnState, *, runtime: Runtime[AgentContext]
) -> PlanState:
    uow_factory = runtime.context.services.require(PLAN_UOW_FACTORY)

    @task
    def initialize() -> int:
        plan = initialize_plan(
            workspace_id=state["workspace_id"], uow_factory=uow_factory
        )
        assert plan.version is not None
        return plan.version

    return {
        "plan_turn_id": state["turn_id"],
        "plan_turn_start_version": await initialize(),
        "plan_version": None,
    }
