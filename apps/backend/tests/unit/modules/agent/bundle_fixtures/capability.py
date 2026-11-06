"""固定 hook 由啟動服務與 Workspace 準備同一步的提示及工具資料。"""

from collections.abc import Mapping
from typing import TypedDict, cast

from langchain_core.tools import StructuredTool
from langgraph.prebuilt import ToolRuntime
from langgraph.runtime import Runtime

from caliburn.modules.agent.plugins.contracts import (
    AgentBundle,
    AgentContext,
    AgentPlugin,
    PluginStep,
)
from caliburn.modules.agent.state import AgentState, request_items
from tests.unit.modules.agent.bundle_fixtures.host_services import LABEL


class CapabilityFields(TypedDict, total=False):
    capability_stamps: dict[str, str]


class CapabilityState(AgentState, CapabilityFields):
    pass


def create_bundle(config: Mapping[str, object]) -> AgentBundle:
    name = str(config["tool_name"])

    async def read(item: str, runtime: ToolRuntime[AgentContext]) -> str:
        state = cast(CapabilityState, runtime.state)
        return f"{state['capability_stamps'][name]}/{item}"

    tool = StructuredTool.from_function(
        coroutine=read, name=name, description="Read item."
    )

    async def provide(
        state: CapabilityState, *, runtime: Runtime[AgentContext]
    ) -> CapabilityState:
        request = state["model_request"]
        stamp = (
            f"{config['label']}:{runtime.context.services.require(LABEL)}:"
            f"{state['workspace_id'].int}:{len(request_items(request))}"
        )
        sections = [
            section
            for section in (request.get("instructions") or "").split("\n\n")
            if section and not section.startswith(f"Use {name} for ")
        ]
        sections.append(f"Use {name} for {stamp}.")
        return {
            "model_request": {**request, "instructions": "\n\n".join(sections)},
            "capability_stamps": {**state.get("capability_stamps", {}), name: stamp},
        }

    return AgentBundle(
        (
            AgentPlugin(
                str(config["label"]),
                tools=(tool,),
                required_services=(LABEL,),
                state_schema=CapabilityFields,
                before_model_step=(
                    PluginStep("provide", provide, input_schema=CapabilityState),
                ),
            ),
        )
    )
