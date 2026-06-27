import pytest
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from app.graph_v3.state import new_state, InterviewState
from app.graph_v3.build_doc import build_doc
from app.graph_v3.deps import Deps
from tests.conftest_graph import FakeKnowledge, SpyPersist, FakeLlm


def _graph():
    g = StateGraph(InterviewState)
    g.add_node("build_doc", build_doc)
    g.add_edge(START, "build_doc")
    g.add_edge("build_doc", END)
    return g.compile(checkpointer=MemorySaver())


def _state():
    s = new_state(job_profile_id="p1", job_title="設備維護工程師", job_summary="維護產線設備")
    s["tasks"] = [
        {"task_name": "巡檢", "unit_id": "U1", "unit_title": "預防保養",
         "outputs": ["點檢表"],
         "behavior_indicators": [{"output_name": "點檢表", "indicator_5w2h": "每日晨班完成點檢表"}]},
        {"task_name": "排程", "unit_id": "U1", "unit_title": "預防保養",
         "outputs": ["保養排程"],
         "behavior_indicators": [{"output_name": "保養排程", "indicator_5w2h": "每週排定保養"}]},
        {"task_name": "通報", "unit_id": "U2", "unit_title": "異常處理",
         "outputs": [],
         "behavior_indicators": [{"output_name": "", "indicator_5w2h": "異常即時通報"}]},
    ]
    s["ksa"] = {
        "by_task": {},
        "attitudes": [{"content": "細心", "source": "company", "icap_ref": None}],
    }
    return s


@pytest.mark.asyncio
async def test_build_doc_deterministic_assembly_then_preview():
    spy = SpyPersist()
    graph = _graph()
    cfg = {"configurable": {"thread_id": "t1",
                            "deps": Deps(knowledge=FakeKnowledge(), persist=spy, llm=FakeLlm())}}
    out = await graph.ainvoke(_state(), cfg)

    payload = out["__interrupt__"][0].value
    assert payload["kind"] == "preview"
    doc = payload["document"]
    units = doc["ocs_content"]["ocu_units"]
    # U1 兩任務、U2 一任務，依出現序分組
    assert [u["ocu_code"] for u in units] == ["T1", "T2"]
    assert [t["task_code"] for t in units[0]["tasks"]] == ["T1.1", "T1.2"]
    assert units[0]["tasks"][0]["indicators"][0]["code"] == "P1.1.1"
    assert units[0]["tasks"][0]["indicators"][0]["text"] == "每日晨班完成點檢表"
    assert units[0]["tasks"][0]["outputs"][0]["code"] == "O1.1.1"
    assert units[1]["tasks"][0]["task_code"] == "T2.1"
    # ocs_ksa now only has attitudes (K/S are nested per task)
    assert "attitudes" in doc["ocs_ksa"]
    assert doc["ocs_ksa"]["attitudes"][0]["name"] == "細心"

    # preview 確認 → 結束 + save_document
    out = await graph.ainvoke(Command(resume="confirm"), cfg)
    assert out["current_step"] == "done"
    assert out["document"]["ocs_profile"]["occupation_name"] == "設備維護工程師"
    assert spy.doc_saved[0] == "p1"


def _one():
    g = StateGraph(InterviewState); g.add_node("n", build_doc)
    g.add_edge(START, "n"); g.add_edge("n", END)
    return g.compile(checkpointer=MemorySaver())


@pytest.mark.asyncio
async def test_build_doc_nests_ks_per_task_and_saves():
    s = new_state(job_profile_id="p1", job_title="工程師")
    s["tasks"] = [{"task_name": "巡檢", "indexer_ref": {"task_id": "T1"}, "unit_id": "U1", "unit_title": "保養"}]
    s["ksa"]["by_task"] = {"T1": {"knowledge": [{"content": "PLC", "source": "catalog", "icap_ref": "K01"}],
                                  "skills": [{"content": "排障", "source": "company", "icap_ref": None}]}}
    s["ksa"]["attitudes"] = [{"content": "細心", "source": "catalog", "icap_ref": "A01"}]
    spy = SpyPersist()
    cfg = {"configurable": {"thread_id": "t", "deps": Deps(knowledge=FakeKnowledge(), persist=spy)}}
    graph = _one()
    out = await graph.ainvoke(s, cfg)
    assert out["__interrupt__"][0].value["kind"] == "preview"
    out = await graph.ainvoke(Command(resume=True), cfg)
    task0 = out["document"]["ocs_content"]["ocu_units"][0]["tasks"][0]
    assert task0["knowledge"][0]["name"] == "PLC"
    assert task0["skills"][0]["name"] == "排障"
    assert out["document"]["ocs_ksa"]["attitudes"][0]["name"] == "細心"
    assert spy.doc_saved is not None
    assert out["current_step"] == "done"
