import pytest
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from app.graph_v3.state import new_state, InterviewState
from app.graph_v3.deep_nodes import star_node
from app.graph_v3.deps import Deps
from tests.conftest_graph import FakeKnowledge, SpyPersist, FakeLlm


def _star_graph():
    g = StateGraph(InterviewState)
    g.add_node("star", star_node)
    g.add_edge(START, "star")
    g.add_edge("star", END)
    return g.compile(checkpointer=MemorySaver())


def _state_with_one_task():
    s = new_state(job_profile_id="p1", job_title="設備維護工程師")
    s["tasks"] = [{"task_name": "例行設備巡檢", "source": "catalog",
                   "indexer_ref": {"ocs_code": "OC1", "task_id": "T1.1"}}]
    return s


@pytest.mark.asyncio
async def test_star_collects_four_slots_then_refines():
    refined = {"S": "產線A晨班", "T": "確保設備可用", "A": "依點檢表逐項檢查", "R": "停機率下降"}
    llm = FakeLlm(json=refined)
    graph = _star_graph()
    cfg = {"configurable": {"thread_id": "t1",
                            "deps": Deps(knowledge=FakeKnowledge(), persist=SpyPersist(), llm=llm)}}

    out = await graph.ainvoke(_state_with_one_task(), cfg)
    assert out["__interrupt__"][0].value["stage"] == "star"
    assert out["__interrupt__"][0].value["slot"] == "S"

    for raw in ["晨班巡檢", "設備可用", "逐項點檢", "停機下降"]:
        out = await graph.ainvoke(Command(resume=raw), cfg)

    star = out["tasks"][0]["star_case"]
    assert star == {"situation": "產線A晨班", "task": "確保設備可用",
                    "action": "依點檢表逐項檢查", "result": "停機率下降"}
    assert "T1.1" in out["deep"]["slots_by_task"]
    assert ("json", "deep") in llm.calls  # 用 deep 階整理


@pytest.mark.asyncio
async def test_star_keeps_raw_when_llm_fails():
    llm = FakeLlm(raises=True)
    graph = _star_graph()
    cfg = {"configurable": {"thread_id": "t2",
                            "deps": Deps(knowledge=FakeKnowledge(), persist=SpyPersist(), llm=llm)}}
    out = await graph.ainvoke(_state_with_one_task(), cfg)
    for raw in ["a原始", "b原始", "c原始", "d原始"]:
        out = await graph.ainvoke(Command(resume=raw), cfg)
    star = out["tasks"][0]["star_case"]
    assert star == {"situation": "a原始", "task": "b原始", "action": "c原始", "result": "d原始"}
