"""Memory 查讀及材料整理留在插件，Core 不理解內容。"""

from typing import TypedDict, cast

from langchain_core.tools import StructuredTool
from langgraph.prebuilt import ToolRuntime
from langgraph.runtime import Runtime
from openai.types.responses.response_input_param import ResponseInputParam

from caliburn.modules.agent.plugins.contracts import (
    AgentBundle,
    AgentContext,
    AgentPlugin,
    PluginStep,
)
from caliburn.modules.agent.state import AgentState, request_items
from tests.unit.modules.agent.bundle_fixtures.interview import read_interview


class MemoryFields(TypedDict, total=False):
    memory_source: str
    memory_label: str


class MemoryState(AgentState, MemoryFields):
    pass


async def read(item: str, runtime: ToolRuntime[AgentContext]) -> str:
    state = cast(MemoryState, runtime.state)
    return f"{state['memory_label']}/{item}"


def static_tool() -> StructuredTool:
    return StructuredTool.from_function(
        coroutine=read, name="read_alpha", description="Read item."
    )


def memory_bundle(label: str) -> AgentBundle:
    async def load(
        state: MemoryState, *, runtime: Runtime[AgentContext]
    ) -> MemoryFields:
        return {
            "memory_source": await read_interview(workspace_id=state["workspace_id"])
        }

    async def provide(
        state: MemoryState, *, runtime: Runtime[AgentContext]
    ) -> MemoryState:
        request = state["model_request"]
        items = [
            item
            for item in request_items(request)
            if not (
                isinstance(item, dict)
                and item.get("role") == "developer"
                and str(item.get("content", "")).startswith("alpha=")
            )
        ]
        stamp = f"{label}:{state['memory_source']}:items={len(items)}"
        return {
            "model_request": {
                **request,
                "instructions": f"Memory {stamp}; short id alpha.",
                "input": cast(
                    ResponseInputParam,
                    [{"role": "developer", "content": f"alpha={stamp}"}, *items],
                ),
            },
            "memory_label": stamp,
        }

    return AgentBundle(
        (
            AgentPlugin(
                "memory",
                tools=(static_tool(),),
                state_schema=MemoryFields,
                on_turn_start=(PluginStep("load", load, input_schema=MemoryState),),
                before_model_step=(
                    PluginStep("provide", provide, input_schema=MemoryState),
                ),
            ),
        )
    )
