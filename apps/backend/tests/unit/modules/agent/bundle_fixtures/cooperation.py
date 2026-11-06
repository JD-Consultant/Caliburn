"""插件內部原生子圖共用一次計算，沒有 Core registry。"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import TypedDict, cast

from langchain_core.tools import StructuredTool
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolRuntime
from langgraph.runtime import Runtime

from caliburn.modules.agent.plugins.contracts import (
    AgentBundle,
    AgentContext,
    AgentPlugin,
    PluginStep,
)
from caliburn.modules.agent.plugins.services import ServiceKey
from caliburn.modules.agent.state import AgentState, request_items


@dataclass(frozen=True)
class Projection:
    item_count: int
    label: str


@dataclass
class CooperationTrace:
    projection_counts: list[int] = field(default_factory=list)


class ProjectionFields(TypedDict, total=False):
    projection_label: str


class PublishedState(AgentState, ProjectionFields):
    pass


class ProjectionState(PublishedState, total=False):
    projection: Projection


COOPERATION_TRACE = ServiceKey[CooperationTrace]("cooperation")


async def read(item: str, runtime: ToolRuntime[AgentContext]) -> str:
    state = cast(PublishedState, runtime.state)
    return f"{state['projection_label']}/{item}"


def create_bundle(config: Mapping[str, object]) -> AgentBundle:
    async def project(
        state: ProjectionState, *, runtime: Runtime[AgentContext]
    ) -> ProjectionState:
        count = len(request_items(state["model_request"]))
        runtime.context.services.require(COOPERATION_TRACE).projection_counts.append(
            count
        )
        return {"projection": Projection(count, f"items={count}")}

    def publish(state: ProjectionState) -> PublishedState:
        projection = state["projection"]
        return {
            "model_request": {
                **state["model_request"],
                "instructions": f"Use projection {projection.label}.",
            },
            "projection_label": projection.label,
        }

    graph = StateGraph(
        ProjectionState,
        context_schema=AgentContext,
        input_schema=AgentState,
        output_schema=PublishedState,
    )
    graph.add_node("project", project)
    graph.add_node("publish", publish)
    graph.add_edge(START, "project")
    graph.add_edge("project", "publish")
    graph.add_edge("publish", END)
    return AgentBundle(
        (
            AgentPlugin(
                "cooperation",
                tools=(
                    StructuredTool.from_function(
                        coroutine=read, name="read_alpha", description="Read item."
                    ),
                ),
                required_services=(COOPERATION_TRACE,),
                state_schema=ProjectionFields,
                before_model_step=(PluginStep("project", graph.compile()),),
            ),
        )
    )
