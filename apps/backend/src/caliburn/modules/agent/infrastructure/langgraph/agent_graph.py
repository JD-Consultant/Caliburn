"""新輪初始化、插件步驟、模型與逐工具保存的原生循環。"""

from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from openai import AsyncOpenAI

from caliburn.modules.agent.infrastructure.langgraph.plugin_steps import (
    add_plugin_steps,
)
from caliburn.modules.agent.infrastructure.openai.call_model import (
    OpenAIModelNode,
    classify_model_response,
)
from caliburn.modules.agent.infrastructure.openai.execute_tool import (
    OpenAIToolNode,
    has_pending_tools,
)
from caliburn.modules.agent.infrastructure.openai.request_initialization import (
    OpenAIRequestInitializer,
)
from caliburn.modules.agent.plugins.contracts import AgentContext, AgentPlugin
from caliburn.modules.agent.plugins.state_schema import (
    CORE_FIELDS,
    compose_state_schema,
)
from caliburn.modules.agent.state import (
    AgentInput,
    AgentLimitError,
    AgentOutput,
    AgentState,
)


def build_agent_graph(
    *,
    client: AsyncOpenAI,
    request_initialization: OpenAIRequestInitializer,
    plugins: tuple[AgentPlugin, ...],
    max_model_steps: int = 64,
    max_tool_calls_per_step: int = 32,
    checkpointer: BaseCheckpointSaver[Any],
) -> CompiledStateGraph[AgentState, AgentContext, AgentInput, AgentOutput]:
    if max_model_steps <= 0 or max_tool_calls_per_step <= 0:
        raise ValueError("Agent limits must be positive")
    state_schema = compose_state_schema(plugins)

    def begin_model_step(state: AgentState) -> AgentState:
        if state.get("model_step", 0) >= max_model_steps:
            raise AgentLimitError("Model step limit reached")
        return {"model_step": state.get("model_step", 0) + 1, "model_response": None}

    def finish_turn(state: AgentState) -> AgentState:
        return {"turn_completed": True}

    graph = StateGraph(
        state_schema,
        context_schema=AgentContext,
        input_schema=AgentInput,
        output_schema=AgentOutput,
    )
    graph.add_node(
        "initialize_turn", request_initialization.initialize, input_schema=state_schema
    )
    graph.add_node("begin_model_step", begin_model_step)
    graph.add_node("finish_turn", finish_turn)
    # 圖外取消只經公開 update_state 使用此 writer；正常流程沒有連入邊。
    graph.add_node("cancel_turn", lambda state: {}, input_schema=state_schema)
    graph.add_node(
        "validate_request_policy", request_initialization.validate_request_policy
    )
    graph.add_node("call_model", OpenAIModelNode(client))
    graph.add_node(
        "execute_tool",
        OpenAIToolNode(
            request_initialization.tools,
            max_tool_calls_per_step,
            set(state_schema.__annotations__) - CORE_FIELDS,
            wrap_tool_call=tuple(
                wrapper for plugin in plugins for wrapper in plugin.wrap_tool_call
            ),
        ),
        input_schema=state_schema,
    )
    on_start = add_plugin_steps(graph, plugins, "on_turn_start", state_schema)
    before = add_plugin_steps(graph, plugins, "before_model_step", state_schema)
    after = add_plugin_steps(graph, plugins, "after_model_step", state_schema)
    on_end = add_plugin_steps(graph, plugins, "on_turn_end", state_schema)

    graph.add_edge(START, "initialize_turn")
    graph.add_edge("initialize_turn", on_start[0] if on_start else "begin_model_step")
    if on_start:
        graph.add_edge(on_start[-1], "begin_model_step")
    graph.add_edge(
        "begin_model_step", before[0] if before else "validate_request_policy"
    )
    if before:
        graph.add_edge(before[-1], "validate_request_policy")
    graph.add_edge("validate_request_policy", "call_model")

    turn_end = on_end[0] if on_end else "finish_turn"
    graph.add_conditional_edges(
        "call_model",
        classify_model_response,
        {
            "tools": "execute_tool",
            "continue": after[0] if after else "begin_model_step",
            "finish": after[0] if after else turn_end,
        },
    )
    graph.add_conditional_edges(
        "execute_tool",
        has_pending_tools,
        {True: "execute_tool", False: after[0] if after else "begin_model_step"},
    )
    if after:
        graph.add_conditional_edges(
            after[-1],
            classify_model_response,
            {
                "tools": "begin_model_step",
                "continue": "begin_model_step",
                "finish": turn_end,
            },
        )
    if on_end:
        graph.add_edge(on_end[-1], "finish_turn")
    graph.add_edge("finish_turn", END)
    return graph.compile(checkpointer=checkpointer)
