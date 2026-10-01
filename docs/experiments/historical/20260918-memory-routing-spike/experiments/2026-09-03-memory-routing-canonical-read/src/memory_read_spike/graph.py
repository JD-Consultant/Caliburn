"""Bounded, non-persistent LangGraph for Memory read tool execution."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode
from langgraph.store.base import BaseStore

from memory_read_spike.scope import TrustedReadScope
from memory_read_spike.state import MemoryReadContext, MemoryReadState
from memory_read_spike.tools import MEMORY_READ_TOOLS, handle_memory_read_error


MEMORY_READ_RECURSION_LIMIT = 6


class MultipleToolCallsError(RuntimeError):
    pass


class ToolBudgetExceededError(RuntimeError):
    pass


async def rebuild_memory_guide(
    store: BaseStore,
    scope: TrustedReadScope,
) -> str:
    rows = await store.asearch(scope.semantic_namespace, limit=100)
    titles = sorted(
        {
            str(row.value["title"])
            for row in rows
            if row.namespace == scope.semantic_namespace and "title" in row.value
        }
    )
    entries = "\n".join(f"- {title}" for title in titles) if titles else "- （無）"
    return f"目前文件可搜尋的工作記憶主題：\n{entries}"


def build_transient_input(
    *,
    system_instructions: str,
    user_request: str,
    canonical_messages: tuple[BaseMessage, ...],
    memory_guide: str,
) -> MemoryReadState:
    return {
        "messages": [
            SystemMessage(content=system_instructions),
            SystemMessage(content=memory_guide),
            *canonical_messages[-6:],
            HumanMessage(content=user_request),
        ],
        "disclosed_message_refs": set(),
        "model_steps": 0,
    }


def build_memory_read_graph(model: Any, *, store: BaseStore):
    async def call_model(state: MemoryReadState) -> dict[str, object]:
        response = await model.ainvoke(state["messages"])
        if len(response.tool_calls) > 1:
            raise MultipleToolCallsError("model emitted parallel tool calls")
        return {"messages": [response], "model_steps": 1}

    def route_after_model(state: MemoryReadState) -> str:
        response = state["messages"][-1]
        if not getattr(response, "tool_calls", None):
            return END
        if state["model_steps"] >= 3:
            raise ToolBudgetExceededError("model requested a third tool call")
        return "tools"

    builder = StateGraph(MemoryReadState, context_schema=MemoryReadContext)
    builder.add_node("model", call_model)
    builder.add_node(
        "tools",
        ToolNode(
            MEMORY_READ_TOOLS,
            handle_tool_errors=handle_memory_read_error,
        ),
    )
    builder.add_edge(START, "model")
    builder.add_conditional_edges("model", route_after_model, ["tools", END])
    builder.add_edge("tools", "model")
    graph = builder.compile(store=store, checkpointer=None)
    return graph.with_config({"recursion_limit": MEMORY_READ_RECURSION_LIMIT})
