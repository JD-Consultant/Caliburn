import os
import uuid
import pytest
from typing import TypedDict
from langgraph.graph import StateGraph, START, END

from app.graph_v3.checkpointer import open_pg_checkpointer

PG = os.getenv("TEST_DATABASE_URL", "")


class _S(TypedDict):
    n: int


async def _inc(state: _S) -> dict:
    return {"n": state["n"] + 1}


@pytest.mark.skipif(not PG, reason="TEST_DATABASE_URL not set")
@pytest.mark.asyncio
async def test_pg_checkpointer_persists_thread_state():
    async with open_pg_checkpointer(PG) as saver:
        g = StateGraph(_S)
        g.add_node("inc", _inc); g.add_edge(START, "inc"); g.add_edge("inc", END)
        graph = g.compile(checkpointer=saver)
        cfg = {"configurable": {"thread_id": f"t-{uuid.uuid4()}"}}
        await graph.ainvoke({"n": 0}, cfg)
        snap = await graph.aget_state(cfg)
        assert snap.values["n"] == 1
