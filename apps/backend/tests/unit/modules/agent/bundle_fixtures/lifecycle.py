"""共享服務在啟動取得；Workspace 由當次 State 提供。"""

from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager

from langgraph.runtime import Runtime

from caliburn.modules.agent.plugins.contracts import (
    AgentBundle,
    AgentContext,
    AgentPlugin,
    PluginStep,
)
from caliburn.modules.agent.plugins.services import PluginServices, ServiceBinding
from caliburn.modules.agent.state import AgentState
from tests.unit.modules.agent.bundle_fixtures.host_services import EVENTS


def create_bundle(config: Mapping[str, object]) -> AgentBundle:
    @asynccontextmanager
    async def open_services(
        dependencies: PluginServices,
    ) -> AsyncIterator[tuple[ServiceBinding[object], ...]]:
        events = dependencies.require(EVENTS)
        events.append("enter")
        try:
            yield ()
        finally:
            events.append("exit")

    async def provide(
        state: AgentState, *, runtime: Runtime[AgentContext]
    ) -> AgentState:
        return {
            "model_request": {
                **state["model_request"],
                "instructions": f"workspace={state['workspace_id'].int}",
            }
        }

    return AgentBundle(
        (
            AgentPlugin(
                "lifecycle",
                required_services=(EVENTS,),
                open_services=open_services,
                before_model_step=(PluginStep("provide", provide),),
            ),
        )
    )
