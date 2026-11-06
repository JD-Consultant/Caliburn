"""原生子圖有私有 scratch、條件 edge，直接交給主圖 add_node。"""

from collections.abc import Mapping
from typing import cast

from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from openai.types.responses.response_input_param import ResponseInputParam

from caliburn.modules.agent.plugins.contracts import (
    AgentBundle,
    AgentContext,
    AgentPlugin,
    PluginStep,
)
from caliburn.modules.agent.plugins.services import ServiceKey
from caliburn.modules.agent.state import AgentState, request_items

GRAPH_TRACE = ServiceKey[list[str]]("graph-trace")


class SummaryState(AgentState, total=False):
    summary: str


def summary_plugin(*, from_model_step: int = 1) -> AgentPlugin:
    async def inspect(
        state: SummaryState, *, runtime: Runtime[AgentContext]
    ) -> SummaryState:
        assert "summary" not in state
        runtime.context.services.require(GRAPH_TRACE).append("inspect")
        if state["model_step"] < from_model_step:
            return {}
        first = next(
            item
            for item in request_items(state["model_request"])
            if isinstance(item, dict) and item.get("role") == "user"
        )
        if first.get("content") == "old prefix":
            return {"summary": f"Summary for workspace {state['workspace_id'].int}"}
        return {}

    def route(state: SummaryState) -> str:
        return "adopt" if "summary" in state else "keep"

    async def adopt(
        state: SummaryState, *, runtime: Runtime[AgentContext]
    ) -> AgentState:
        runtime.context.services.require(GRAPH_TRACE).append("adopt")
        request = state["model_request"]
        # 合成壓縮會移除 Memory；後續一般 Memory hook 自己補回。
        items = [
            item
            for item in request_items(request)
            if not (isinstance(item, dict) and item.get("role") == "developer")
        ]
        return {
            "model_request": {
                **request,
                "input": cast(
                    ResponseInputParam,
                    [{"role": "user", "content": state["summary"]}, *items[1:]],
                ),
            }
        }

    async def keep(
        state: SummaryState, *, runtime: Runtime[AgentContext]
    ) -> AgentState:
        runtime.context.services.require(GRAPH_TRACE).append("keep")
        return {}

    graph = StateGraph(
        SummaryState,
        context_schema=AgentContext,
        input_schema=AgentState,
        output_schema=AgentState,
    )
    graph.add_node("inspect", inspect)
    graph.add_node("adopt", adopt)
    graph.add_node("keep", keep)
    graph.add_edge(START, "inspect")
    graph.add_conditional_edges("inspect", route, {"adopt": "adopt", "keep": "keep"})
    graph.add_edge("adopt", END)
    graph.add_edge("keep", END)
    return AgentPlugin(
        "summary",
        required_services=(GRAPH_TRACE,),
        before_model_step=(PluginStep("compact", graph.compile()),),
    )


def create_bundle(config: Mapping[str, object]) -> AgentBundle:
    return AgentBundle((summary_plugin(),))
