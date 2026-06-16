import pytest
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from app.graph_v3.state import new_state, InterviewState
from app.graph_v3.deep_nodes import star_node, five_w2h_node, indicator_node, route_after_indicator
from app.graph_v3.deps import Deps
from app.services.knowledge.models import TasksByIdResult, TaskDetail, Pair
from tests.conftest_graph import FakeKnowledge, SpyPersist, FakeLlm

_GOOD = {"has_situation": True, "has_purpose": True, "has_collaborators": True,
         "has_tools": True, "has_action": True, "has_output": True, "has_standard": True}


def _deep_graph():
    g = StateGraph(InterviewState)
    g.add_node("star", star_node)
    g.add_node("five_w2h", five_w2h_node)
    g.add_node("indicator", indicator_node)
    g.add_edge(START, "star")
    g.add_edge("star", "five_w2h")
    g.add_edge("five_w2h", "indicator")
    g.add_conditional_edges("indicator", route_after_indicator,
                            {"five_w2h": "five_w2h", "advance": END})
    return g.compile(checkpointer=MemorySaver())


@pytest.mark.asyncio
async def test_single_task_deep_interview_completes():
    detail = TaskDetail(id="T1.1", ocs_code="OC1", task_id="T1.1", task_title="例行設備巡檢",
                        output_pairs=[Pair(code="O1", name="點檢表")])
    star_refine = {"S": "晨班A線", "T": "確保可用", "A": "逐項點檢、記錄", "R": "停機下降"}
    indicators = [{"output_name": "點檢表", "indicator_5w2h": "在晨班…點檢表…",
                   "indicator_abcd": "面對…", "quality_dims": _GOOD}]

    def _json(prompt):
        return star_refine if "STAR 四槽" in prompt else indicators
    llm = FakeLlm(json=_json)
    fake = FakeKnowledge(tasks=TasksByIdResult(tasks=[detail]))

    s = new_state(job_profile_id="p1", job_title="設備維護工程師")
    s["tasks"] = [{"task_name": "例行設備巡檢", "source": "catalog",
                   "indexer_ref": {"ocs_code": "OC1", "task_id": "T1.1"}}]
    graph = _deep_graph()
    cfg = {"configurable": {"thread_id": "t1",
                            "deps": Deps(knowledge=fake, persist=SpyPersist(), llm=llm)}}

    out = await graph.ainvoke(s, cfg)
    # 一路回答所有 interrupt 直到完成
    guard = 0
    while "__interrupt__" in out:
        out = await graph.ainvoke(Command(resume="作業員、ERP、零漏檢、當日完成"), cfg)
        guard += 1
        assert guard < 20, "interrupt 迴圈未收斂"

    task = out["tasks"][0]
    assert task["star_case"]["situation"] == "晨班A線"
    assert task["outputs"] == ["點檢表"]
    assert task["behavior_indicators"][0]["output_name"] == "點檢表"
    assert out["deep"]["missing_fields"] == []
