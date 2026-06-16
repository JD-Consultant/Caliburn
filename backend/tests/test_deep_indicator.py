import pytest
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from app.graph_v3.state import new_state, InterviewState
from app.graph_v3.deep_nodes import indicator_node
from app.graph_v3.deps import Deps
from tests.conftest_graph import FakeKnowledge, SpyPersist, FakeLlm


def _graph():
    g = StateGraph(InterviewState)
    g.add_node("indicator", indicator_node)
    g.add_edge(START, "indicator")
    g.add_edge("indicator", END)
    return g.compile(checkpointer=MemorySaver())


def _full_task():
    return {
        "task_name": "例行設備巡檢", "source": "catalog",
        "indexer_ref": {"ocs_code": "OC1", "task_id": "T1.1"},
        "situation": "晨班", "purpose": "確保可用", "collaborators": ["作業員"],
        "stakeholders": ["產線主管"], "tools": ["ERP"], "workflow_steps": ["逐項點檢"],
        "outputs": ["點檢表"], "quality_standards": ["零漏檢"], "time_standards": ["當日完成"],
        "star_case": {"situation": "晨班", "task": "可用", "action": "點檢", "result": "下降"},
    }


def _state_with(task):
    s = new_state(job_profile_id="p1", job_title="X")
    s["tasks"] = [task]
    return s


_GOOD_DIMS = {"has_situation": True, "has_purpose": True, "has_collaborators": True,
              "has_tools": True, "has_action": True, "has_output": True, "has_standard": True}


@pytest.mark.asyncio
async def test_indicator_accepts_good_quality():
    results = [{"output_name": "點檢表", "indicator_5w2h": "在晨班…產出點檢表…",
                "indicator_abcd": "面對產線…", "quality_dims": _GOOD_DIMS}]
    llm = FakeLlm(json=results)
    graph = _graph()
    cfg = {"configurable": {"thread_id": "t1",
                            "deps": Deps(knowledge=FakeKnowledge(), persist=SpyPersist(), llm=llm)}}
    out = await graph.ainvoke(_state_with(_full_task()), cfg)
    inds = out["tasks"][0]["behavior_indicators"]
    assert inds and inds[0]["output_name"] == "點檢表"
    assert out["deep"]["missing_fields"] == []          # 無重試
    assert ("json", "indicator") in llm.calls           # 用 indicator 階


@pytest.mark.asyncio
async def test_indicator_none_llm_yields_force_accepted():
    """None llm must not crash; must write force_accepted placeholder and clear missing_fields."""
    graph = _graph()
    cfg = {"configurable": {"thread_id": "t_none_llm",
                            "deps": Deps(knowledge=FakeKnowledge(), persist=SpyPersist(), llm=None)}}
    out = await graph.ainvoke(_state_with(_full_task()), cfg)
    inds = out["tasks"][0]["behavior_indicators"]
    assert inds, "expected at least one placeholder indicator"
    assert inds[0]["quality_status"] == "force_accepted"
    assert out["deep"]["missing_fields"] == []


@pytest.mark.asyncio
async def test_indicator_low_quality_signals_retry_and_clears_weak():
    # 4 個維度為 False → 命中 3/7 ≈ 0.43 < 0.60 門檻 → 觸發重試
    bad_dims = dict(_GOOD_DIMS, has_tools=False, has_action=False,
                    has_output=False, has_standard=False)
    results = [{"output_name": "點檢表", "indicator_5w2h": "薄弱",
                "indicator_abcd": "薄弱", "quality_dims": bad_dims}]
    llm = FakeLlm(json=results)
    graph = _graph()
    cfg = {"configurable": {"thread_id": "t2",
                            "deps": Deps(knowledge=FakeKnowledge(), persist=SpyPersist(), llm=llm)}}
    out = await graph.ainvoke(_state_with(_full_task()), cfg)
    deep = out["deep"]
    assert deep["missing_fields"]            # 有重試訊號（→ route_after_indicator 會回 five_w2h）
    assert deep["retry"]["T1.1"] == 1        # 重試計數 +1（task_id 鍵）
    task = out["tasks"][0]
    # 弱欄位被清空（將由 five_w2h 重問）
    assert "tools" in deep["missing_fields"]
    assert not task.get("tools")
