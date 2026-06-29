import pytest
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from app.authoring.state import new_state, InterviewState
from app.authoring.curate_nodes import fetch_ksa_pool, curate_ks, curate_attitudes
from app.authoring.deps import Deps
from app.core.knowledge_dto import CompetencyPool, CitableItem, SourceRef
from tests.conftest_graph import FakeKnowledge, SpyPersist


def _one(node):
    g = StateGraph(InterviewState)
    g.add_node("n", node)
    g.add_edge(START, "n"); g.add_edge("n", END)
    return g.compile(checkpointer=MemorySaver())


@pytest.mark.asyncio
async def test_fetch_ksa_pool_from_competencies():
    pool = CompetencyPool(ocs_code="OC1",
        knowledge=[CitableItem(id="ocs:OC1:K:K01", type="K", code="K01", name="PLC",
                               ocs_code="OC1", ocs_name="工程師",
                               sources=[SourceRef(task_code="T1.1")])],
        skills=[CitableItem(id="ocs:OC1:S:S01", type="S", code="S01", name="排障",
                            ocs_code="OC1", ocs_name="工程師", sources=[SourceRef(task_code="T1.1")])],
        attitudes=[CitableItem(id="ocs:OC1:A:A01", type="A", code="A01", name="細心",
                               ocs_code="OC1", ocs_name="工程師", sources=[])])
    fake = FakeKnowledge(); fake._competencies = pool
    s = new_state(job_profile_id="p1", job_title="工程師")
    s["profile"]["selected_ocs_code"] = "OC1"
    cfg = {"configurable": {"thread_id": "t", "deps": Deps(knowledge=fake, persist=SpyPersist())}}
    out = await _one(fetch_ksa_pool).ainvoke(s, cfg)
    assert out["ksa"]["pool"]["knowledge"][0]["content"] == "PLC"
    assert out["ksa"]["pool"]["knowledge"][0]["sources"] == ["T1.1"]
    assert out["ksa"]["pool"]["attitudes"][0]["content"] == "細心"
    assert out["current_step"] == "curate_ks"


@pytest.mark.asyncio
async def test_curate_ks_loops_per_task_then_routes_attitudes():
    s = new_state(job_profile_id="p1", job_title="工程師")
    s["tasks"] = [{"task_name": "巡檢", "indexer_ref": {"task_id": "T1"}},
                  {"task_name": "保養", "indexer_ref": {"task_id": "T2"}}]
    s["ksa"]["pool"] = {"knowledge": [{"content": "PLC", "source": "catalog", "icap_ref": "K01"}],
                        "skills": [], "attitudes": []}
    cfg = {"configurable": {"thread_id": "t", "deps": Deps(knowledge=FakeKnowledge(), persist=SpyPersist())}}
    graph = _one(curate_ks)
    out = await graph.ainvoke(s, cfg)
    assert out["__interrupt__"][0].value["kind"] == "curate_ks"
    assert out["__interrupt__"][0].value["task_name"] == "巡檢"
    out = await graph.ainvoke(Command(resume={"ks": {"knowledge": [{"content": "PLC", "source": "catalog", "icap_ref": "K01"}], "skills": []}}), cfg)
    assert out["__interrupt__"][0].value["task_name"] == "保養"   # 第二任務
    out = await graph.ainvoke(Command(resume={"ks": {"knowledge": [], "skills": []}}), cfg)
    assert out["ksa"]["by_task"]["T1"]["knowledge"][0]["content"] == "PLC"
    assert out["ksa"]["by_task"]["T2"] == {"knowledge": [], "skills": []}
    assert out["current_step"] == "curate_attitudes"


@pytest.mark.asyncio
async def test_curate_attitudes_interrupt_then_store():
    s = new_state(job_profile_id="p1", job_title="工程師")
    s["ksa"]["pool"] = {"knowledge": [], "skills": [],
                        "attitudes": [{"content": "細心", "source": "catalog", "icap_ref": "A01"}]}
    cfg = {"configurable": {"thread_id": "t", "deps": Deps(knowledge=FakeKnowledge(), persist=SpyPersist())}}
    graph = _one(curate_attitudes)
    out = await graph.ainvoke(s, cfg)
    assert out["__interrupt__"][0].value["kind"] == "curate_attitudes"
    out = await graph.ainvoke(Command(resume={"attitudes": [{"content": "細心", "source": "catalog", "icap_ref": "A01"}]}), cfg)
    assert out["ksa"]["attitudes"][0]["content"] == "細心"
    assert out["current_step"] == "build_doc"
