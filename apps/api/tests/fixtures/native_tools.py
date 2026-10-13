"""透過正式 ToolNode 與原生子圖測工具接線，不另寫 dispatch。"""

from uuid import uuid4, uuid5

from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from caliburn.adapters.graph_checkpointer import create_graph_serializer
from caliburn.agent_execution.native_agent import NativeAgentState
from tests.fixtures.response_loop import response_at


async def ensure_active():
    pass


async def invoke_tool(tools, call, seed=None, allowed_types=()):
    saver = InMemorySaver(serde=create_graph_serializer(allowed_types=allowed_types))
    graph = (
        StateGraph(NativeAgentState)
        .add_node("tools", ToolNode(tools, handle_tool_errors=False))
        .add_edge(START, "tools")
        .add_edge("tools", END)
        .compile(checkpointer=saver)
    )
    raw = response_at(1, tools=0).model_dump(mode="json", exclude_unset=True)
    raw["output"] = [call.model_dump(mode="json", exclude_unset=True)]
    seed = seed or uuid4()
    state = await graph.ainvoke(
        {
            "messages": [
                AIMessage(
                    id=raw["id"],
                    content="",
                    tool_calls=[
                        {
                            "name": call.name,
                            "id": call.call_id,
                            "args": {},
                            "type": "tool_call",
                        }
                    ],
                )
            ],
            "request_id": uuid4(),
            "response_snapshot": raw,
            "operation_seed": seed,
        },
        {"configurable": {"thread_id": str(uuid4())}},
        durability="sync",
    )
    saved = [row async for row in saver.alist(None)]
    commands = [
        row.checkpoint["channel_values"]["prepared"]
        for row in saved
        if "prepared" in row.checkpoint["channel_values"]
    ]
    return (
        state["messages"][-1].content,
        commands[0] if commands else None,
        uuid5(seed, call.call_id),
    )
