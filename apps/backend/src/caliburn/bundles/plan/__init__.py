"""將工作計畫讀寫接入 Agent。"""

from collections.abc import Mapping

from caliburn.bundles.plan.cancellation import cancel_turn_plan
from caliburn.bundles.plan.context import create_context_plugin
from caliburn.bundles.plan.initialization import initialize_turn_plan
from caliburn.bundles.plan.planning_instructions import INTERVIEW_PLAN_INSTRUCTIONS
from caliburn.bundles.plan.services import PLAN_QUERIES, PLAN_UOW_FACTORY
from caliburn.bundles.plan.state import PlanState
from caliburn.bundles.plan.tools import create_plan_tools
from caliburn.modules.agent.plugins.contracts import (
    AgentBundle,
    AgentPlugin,
    PluginStep,
)


def create_bundle(config: Mapping[str, object]) -> AgentBundle:
    if config:
        raise ValueError("Plan Bundle 不接受 config；請以 plugins 選取能力")
    return AgentBundle(
        plugins=(
            AgentPlugin(
                name="plan_tools",
                required_plugins=("plan_lifecycle",),
                tools=create_plan_tools(),
                required_services=(PLAN_QUERIES, PLAN_UOW_FACTORY),
            ),
            AgentPlugin(
                name="plan_lifecycle",
                required_services=(PLAN_QUERIES, PLAN_UOW_FACTORY),
                state_schema=PlanState,
                on_turn_start=(
                    PluginStep(
                        "initialize_plan",
                        initialize_turn_plan,
                    ),
                ),
                on_turn_cancel=cancel_turn_plan,
            ),
            AgentPlugin(
                name="plan_prompt",
                required_plugins=("plan_tools",),
                prompt_sections=(INTERVIEW_PLAN_INSTRUCTIONS,),
            ),
            create_context_plugin(),
        )
    )
