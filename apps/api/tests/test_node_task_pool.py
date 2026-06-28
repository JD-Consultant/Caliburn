import pytest
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from app.graph_v3.state import new_state, InterviewState
from app.graph_v3.nodes import build_task_pool, _pool_to_tasks
from app.graph_v3.deps import Deps
from app.core.knowledge_dto import OccupationTasks, UnitTasks, TaskRef
from tests.conftest_graph import FakeKnowledge, SpyPersist


def _graph():
    g = StateGraph(InterviewState)
    g.add_node("build_task_pool", build_task_pool)
    g.add_edge(START, "build_task_pool")
    g.add_edge("build_task_pool", END)
    return g.compile(checkpointer=MemorySaver())


def _occ(ocs, *tasks):
    return OccupationTasks(ocs_code=ocs, ocs_name="工程師", units=[
        UnitTasks(ocu_code="U1", ocu_name="巡檢類", urn=f"ocs:{ocs}:U:U1",
                  tasks=[TaskRef(task_code=tc, task_name=tn, urn=f"ocs:{ocs}:T:{tc}")
                         for tc, tn in tasks])])


@pytest.mark.asyncio
async def test_task_pool_interrupt_then_flush_edited():
    fake = FakeKnowledge()
    fake._occ_tasks = _occ("OC1", ("T1.1", "例行巡檢"))
    spy = SpyPersist()
    graph = _graph()
    s = new_state(job_profile_id="p1", job_title="工程師")
    s["profile"]["selected_ocs_code"] = "OC1"
    s["profile"]["selected_ocs_codes"] = ["OC1"]
    cfg = {"configurable": {"thread_id": "t1", "deps": Deps(knowledge=fake, persist=spy)}}

    out = await graph.ainvoke(s, cfg)
    intr = out["__interrupt__"][0].value
    assert intr["kind"] == "edit_tasks"
    assert intr["tasks"][0]["task_name"] == "例行巡檢" and intr["tasks"][0]["source"] == "catalog"
    assert intr["tasks"][0]["indexer_ref"] == {"ocs_code": "OC1", "task_code": "T1.1"}

    edited = [{"task_name": "例行巡檢", "source": "catalog",
               "indexer_ref": {"ocs_code": "OC1", "task_code": "T1.1"}},
              {"task_name": "公司自訂任務", "source": "company"}]
    out2 = await graph.ainvoke(Command(resume={"tasks": edited}), cfg)
    assert [t["task_name"] for t in out2["tasks"]] == ["例行巡檢", "公司自訂任務"]
    assert out2["current_step"] == "deep"


@pytest.mark.asyncio
async def test_task_pool_orders_tasks_by_ocs_priority():
    # FakeKnowledge returns the same _occ_tasks per call; use a per-code dict instead.
    by_code = {"OC1": _occ("OC1", ("T1", "巡檢A")), "OC2": _occ("OC2", ("T1", "保養B"))}

    class MultiFake(FakeKnowledge):
        async def occupation_tasks(self, ocs_code):
            self.calls.append(("occupation_tasks", ocs_code))
            return by_code[ocs_code]

    fake = MultiFake()
    graph = _graph()
    s = new_state(job_profile_id="p1", job_title="工程師")
    s["profile"]["selected_ocs_codes"] = ["OC2", "OC1"]
    cfg = {"configurable": {"thread_id": "tp", "deps": Deps(knowledge=fake, persist=SpyPersist())}}

    out = await graph.ainvoke(s, cfg)
    intr = out["__interrupt__"][0].value
    assert ("occupation_tasks", "OC2") in fake.calls and ("occupation_tasks", "OC1") in fake.calls
    assert [t["task_name"] for t in intr["tasks"]] == ["保養B", "巡檢A"]


def test_pool_tasks_carry_unit_info():
    tasks = _pool_to_tasks([_occ("OC1", ("T1.1", "巡檢"))])
    assert tasks[0]["ocu_code"] == "U1"
    assert tasks[0]["ocu_name"] == "巡檢類"
    assert tasks[0]["indexer_ref"] == {"ocs_code": "OC1", "task_code": "T1.1"}
