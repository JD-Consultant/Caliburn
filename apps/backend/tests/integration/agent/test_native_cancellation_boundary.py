"""只驗上層已取消並收尾後的原生排程接縫，不代表取消服務已實作。"""

import asyncio
from typing import TypedDict
from uuid import UUID, uuid4

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from caliburn.modules.agent.infrastructure.persistence.postgres_checkpointer import (
    open_postgres_checkpointer,
)


class CancelBoundaryState(TypedDict, total=False):
    turn_id: UUID
    turn_input: str
    plugin_scratch: str


def test_native_new_input_replaces_old_schedule_after_external_cancellation(
    checkpoint_conninfo: str,
) -> None:
    """不繞過 Agent 的 pending guard；獨立核對未來 Application 的原生接法。"""
    old_turn, new_turn = UUID(int=901), UUID(int=902)
    observed: list[tuple[str, UUID, str | None]] = []

    async def initialize(state: CancelBoundaryState) -> CancelBoundaryState:
        observed.append(("initialize", state["turn_id"], state.get("plugin_scratch")))
        return {"plugin_scratch": f"scratch:{state['turn_input']}"}

    async def perform(state: CancelBoundaryState) -> CancelBoundaryState:
        if state["turn_id"] == old_turn:
            interrupt("old question")
            raise AssertionError("Cancelled old work must not be resumed")
        observed.append(("perform", state["turn_id"], state["plugin_scratch"]))
        return {}

    async def run() -> None:
        builder = StateGraph(CancelBoundaryState)
        builder.add_node("initialize", initialize)
        builder.add_node("perform", perform)
        builder.add_edge(START, "initialize")
        builder.add_edge("initialize", "perform")
        builder.add_edge("perform", END)
        async with open_postgres_checkpointer(
            checkpoint_conninfo, initialize=True
        ) as saver:
            graph = builder.compile(checkpointer=saver)
            config: RunnableConfig = {
                "configurable": {"thread_id": "native-cancel-boundary"},
                "run_id": uuid4(),
            }
            await graph.ainvoke(
                {"turn_id": old_turn, "turn_input": "old"}, config, durability="sync"
            )
            waiting = await graph.aget_state(config)
            assert waiting.interrupts and waiting.next == ("perform",)
        # 上層取消資格、停止活動及補償在此測例的驗證範圍之外。
        async with open_postgres_checkpointer(checkpoint_conninfo) as saver:
            graph = builder.compile(checkpointer=saver)
            config = {
                "configurable": {"thread_id": "native-cancel-boundary"},
                "run_id": uuid4(),
            }
            await graph.ainvoke(
                {"turn_id": new_turn, "turn_input": "new"}, config, durability="sync"
            )
            completed = await graph.aget_state(config)
            assert not completed.next and not completed.interrupts
            assert completed.values["turn_id"] == new_turn
            assert completed.values["turn_input"] == "new"
            assert completed.values["plugin_scratch"] == "scratch:new"

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    assert observed == [
        ("initialize", old_turn, None),
        ("initialize", new_turn, "scratch:old"),
        ("perform", new_turn, "scratch:new"),
    ]
