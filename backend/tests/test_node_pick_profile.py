import pytest
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from app.graph_v3.state import new_state, InterviewState
from app.graph_v3.nodes import pick_profile
from app.graph_v3.deps import Deps
from app.services.knowledge.models import SearchResult, Hit
from tests.conftest_graph import FakeKnowledge, SpyPersist


def _one_node_graph():
    g = StateGraph(InterviewState)
    g.add_node("pick_profile", pick_profile)
    g.add_edge(START, "pick_profile")
    g.add_edge("pick_profile", END)
    return g.compile(checkpointer=MemorySaver())


@pytest.mark.asyncio
async def test_pick_profile_interrupts_then_persists_selection():
    fake = FakeKnowledge(search=SearchResult(mode="dense", hits=[
        Hit(id="p1", ocs_code="OC1", chunk_level="profile", job_title="工程師")]))
    spy = SpyPersist()
    graph = _one_node_graph()
    cfg = {"configurable": {"thread_id": "t1", "deps": Deps(knowledge=fake, persist=spy)}}

    out = await graph.ainvoke(new_state(job_profile_id="p1", job_title="工程師"), cfg)
    intr = out["__interrupt__"][0].value
    assert intr["kind"] == "select_profile" and intr["candidates"][0]["ocs_code"] == "OC1"

    out2 = await graph.ainvoke(Command(resume={"ocs_code": "OC1"}), cfg)
    assert out2["profile"]["selected_ocs_code"] == "OC1"
    assert out2["profile"]["selected_ocs_codes"] == ["OC1"]
    assert out2["current_step"] == "task_pool"
    assert spy.selected == ("p1", ["OC1"])


@pytest.mark.asyncio
async def test_pick_profile_multi_select_keeps_order_as_priority():
    fake = FakeKnowledge(search=SearchResult(mode="dense", hits=[
        Hit(id="p1", ocs_code="OC1", chunk_level="profile", job_title="工程師"),
        Hit(id="p2", ocs_code="OC2", chunk_level="profile", job_title="技術員")]))
    spy = SpyPersist()
    graph = _one_node_graph()
    cfg = {"configurable": {"thread_id": "t2", "deps": Deps(knowledge=fake, persist=spy)}}

    await graph.ainvoke(new_state(job_profile_id="p1", job_title="工程師"), cfg)
    # 使用者依優先度依序勾選 OC2 → OC1
    out2 = await graph.ainvoke(Command(resume={"ocs_codes": ["OC2", "OC1"]}), cfg)
    assert out2["profile"]["selected_ocs_codes"] == ["OC2", "OC1"]
    assert out2["profile"]["selected_ocs_code"] == "OC2"   # primary = 第一個
    assert spy.selected == ("p1", ["OC2", "OC1"])
    assert out2["current_step"] == "task_pool"
