"""可序列化資料與 runtime 服務分開的合成插件；不實作正式業務。"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal, NotRequired, TypedDict, cast

from langchain_core.tools import StructuredTool
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolRuntime
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


class MemoryPin(TypedDict):
    version: str
    ids: dict[str, str]


class MemoryChannels(TypedDict, total=False):
    memory_pin: MemoryPin


class MemoryState(AgentState, MemoryChannels):
    pass


@dataclass
class MemorySource:
    current_version: str
    selections: list[str] = field(default_factory=list)
    versions: dict[str, dict[str, str]] = field(
        default_factory=lambda: {
            "v1": {"k1": "old-object"},
            "v2": {"k1": "different-object"},
        }
    )


MEMORY_SOURCE = ServiceKey[MemorySource]("checkpoint-memory-source")


def create_bundle(config: Mapping[str, object]) -> AgentBundle:
    if "role" in config:
        return role_bundle(str(config["role"]), fail_tool=bool(config.get("fail_tool")))
    if config.get("summary"):
        return summary_bundle(fail=bool(config.get("fail")))

    async def read_memory(item: str, runtime: ToolRuntime[AgentContext]) -> str:
        if fail_tool:
            raise RuntimeError("synthetic tool outage")
        pin = cast(MemoryPin, runtime.state["memory_pin"])
        return f"{pin['version']}:{pin['ids'][item]}"

    fail_tool = bool(config.get("fail_tool"))
    tool = StructuredTool.from_function(
        coroutine=read_memory, description="Read the pinned synthetic Memory item."
    )

    async def select(
        state: MemoryState, *, runtime: Runtime[AgentContext]
    ) -> Mapping[str, object]:
        source = runtime.context.services.require(MEMORY_SOURCE)
        source.selections.append(source.current_version)
        return {
            "memory_pin": {
                "version": source.current_version,
                "ids": dict(source.versions[source.current_version]),
            }
        }

    async def provide(
        state: MemoryState, *, runtime: Runtime[AgentContext]
    ) -> Mapping[str, object]:
        pin = state["memory_pin"]
        request = state["model_request"]
        items = [
            item
            for item in request_items(request)
            if not (
                isinstance(item, dict)
                and item.get("role") == "developer"
                and str(item.get("content", "")).startswith("Memory ")
            )
        ]
        return {
            "model_request": {
                **request,
                "input": cast(
                    ResponseInputParam,
                    [
                        {
                            "role": "developer",
                            "content": (
                                f"Memory {pin['version']}: k1={pin['ids']['k1']}"
                            ),
                        },
                        *items,
                    ],
                ),
            },
        }

    return AgentBundle(
        (
            AgentPlugin(
                "memory",
                tools=(tool,),
                required_services=(MEMORY_SOURCE,),
                state_schema=MemoryChannels,
                on_turn_start=(PluginStep("select", select),),
                before_model_step=(
                    PluginStep("provide", provide, input_schema=MemoryState),
                ),
            ),
        )
    )


class RoleScope(TypedDict):
    role: str
    cutoff: int


class SourceContext(RoleScope):
    interviews: dict[int, str]
    understanding: NotRequired[str]


class RoleChannels(TypedDict, total=False):
    role_scope: RoleScope
    source_context: SourceContext


class RoleState(AgentState, RoleChannels):
    pass


@dataclass(frozen=True)
class InterviewSource:
    cutoff: int
    interviews: tuple[str, ...] = ("first statement", "later statement")


INTERVIEW_SOURCE = ServiceKey[InterviewSource]("checkpoint-interview-source")


def role_bundle(role: str, *, fail_tool: bool) -> AgentBundle:
    async def read_source(
        kind: Literal["interview", "understanding"],
        index: int,
        runtime: ToolRuntime[AgentContext],
    ) -> str:
        if fail_tool:
            raise RuntimeError("synthetic tool outage")
        scope = cast(SourceContext, runtime.state["source_context"])
        if kind == "understanding":
            return scope.get("understanding", "denied:role")
        if not 1 <= index <= scope["cutoff"]:
            return "denied:outside_batch"
        return scope["interviews"][index]

    tool = StructuredTool.from_function(
        coroutine=read_source, description="Read a source within this role and batch."
    )

    async def provide(
        state: RoleState, *, runtime: Runtime[AgentContext]
    ) -> Mapping[str, object]:
        source = runtime.context.services.require(INTERVIEW_SOURCE)
        scope = state.get("role_scope")
        if scope is None:
            scope = {"role": role, "cutoff": source.cutoff}
        context: SourceContext = {
            "role": scope["role"],
            "cutoff": scope["cutoff"],
            "interviews": {
                index: text
                for index, text in enumerate(source.interviews, 1)
                if index <= scope["cutoff"]
            },
        }
        if scope["role"] == "B2":
            context["understanding"] = "synthetic understanding"
        request = state["model_request"]
        items = [
            item
            for item in request_items(request)
            if not (isinstance(item, dict) and item.get("role") == "developer")
        ]
        return {
            "role_scope": scope,
            "source_context": context,
            "model_request": {
                **request,
                "input": cast(
                    ResponseInputParam,
                    [
                        {
                            "role": "developer",
                            "content": (
                                f"Role {scope['role']}; interview through "
                                f"{scope['cutoff']}"
                            ),
                        },
                        *items,
                    ],
                ),
            },
        }

    return AgentBundle(
        (
            AgentPlugin(
                "role",
                tools=(tool,),
                required_services=(INTERVIEW_SOURCE,),
                state_schema=RoleChannels,
                before_model_step=(
                    PluginStep("provide", provide, input_schema=RoleState),
                ),
            ),
        )
    )


class SummaryChannels(TypedDict, total=False):
    summary_visits: int


class SummarySharedState(AgentState, SummaryChannels):
    pass


class SummaryPrivateState(SummarySharedState, total=False):
    scratch: str


SUMMARY_TRACE = ServiceKey[list[str]]("checkpoint-summary-trace")


def summary_bundle(*, fail: bool) -> AgentBundle:
    async def prepare(
        state: SummaryPrivateState, *, runtime: Runtime[AgentContext]
    ) -> SummaryPrivateState:
        assert "scratch" not in state
        visit = state.get("summary_visits", 0) + 1
        runtime.context.services.require(SUMMARY_TRACE).append(f"prepare:{visit}")
        return {
            "summary_visits": visit,
            "scratch": (f"Summary {visit} for workspace {state['workspace_id'].int}"),
        }

    async def adopt(
        state: SummaryPrivateState, *, runtime: Runtime[AgentContext]
    ) -> SummarySharedState:
        visit = state["summary_visits"]
        runtime.context.services.require(SUMMARY_TRACE).append(f"adopt:{visit}")
        if fail:
            raise RuntimeError("synthetic summary outage")
        request = state["model_request"]
        return {
            "summary_visits": visit,
            "model_request": {
                **request,
                "input": cast(
                    ResponseInputParam,
                    [
                        {"role": "user", "content": state["scratch"]},
                        *request_items(request)[1:],
                    ],
                ),
            },
        }

    graph = StateGraph(
        SummaryPrivateState,
        context_schema=AgentContext,
        input_schema=SummarySharedState,
        output_schema=SummarySharedState,
    )
    graph.add_node("prepare", prepare)
    graph.add_node("adopt", adopt)
    graph.add_edge(START, "prepare")
    graph.add_edge("prepare", "adopt")
    graph.add_edge("adopt", END)
    return AgentBundle(
        (
            AgentPlugin(
                "summary",
                required_services=(SUMMARY_TRACE,),
                state_schema=SummaryChannels,
                before_model_step=(
                    PluginStep(
                        "compact", graph.compile(), input_schema=SummarySharedState
                    ),
                ),
            ),
        )
    )
