import pytest
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from app.graph_v3.state import new_state, InterviewState
from app.graph_v3.nodes import build_task_pool
from app.graph_v3.deps import Deps
from app.services.knowledge.models import TaskPool, PoolGroup, PoolUnit, PoolTask
from tests.conftest_graph import FakeKnowledge, SpyPersist


def _graph():
    g = StateGraph(InterviewState)
    g.add_node("build_task_pool", build_task_pool)
    g.add_edge(START, "build_task_pool")
    g.add_edge("build_task_pool", END)
    return g.compile(checkpointer=MemorySaver())


@pytest.mark.asyncio
async def test_task_pool_interrupt_then_flush_edited():
    pool = TaskPool(groups=[PoolGroup(ocs_code="OC1", job_title="工程師", units=[
        PoolUnit(unit_id="U1", unit_title="巡檢類", tasks=[
            PoolTask(id="OC1-T1.1", task_id="T1.1", task_title="例行巡檢")])])])
    fake = FakeKnowledge(pool=pool)
    spy = SpyPersist()
    graph = _graph()
    s = new_state(job_profile_id="p1", job_title="工程師")
    s["profile"]["selected_ocs_code"] = "OC1"
    cfg = {"configurable": {"thread_id": "t1", "deps": Deps(knowledge=fake, persist=spy)}}

    out = await graph.ainvoke(s, cfg)
    intr = out["__interrupt__"][0].value
    assert intr["kind"] == "edit_tasks"
    assert intr["tasks"][0]["task_name"] == "例行巡檢" and intr["tasks"][0]["source"] == "catalog"

    edited = [{"task_name": "例行巡檢", "source": "catalog",
               "indexer_ref": {"ocs_code": "OC1", "task_id": "T1.1"}},
              {"task_name": "公司自訂任務", "source": "company"}]
    out2 = await graph.ainvoke(Command(resume={"tasks": edited}), cfg)
    assert [t["task_name"] for t in out2["tasks"]] == ["例行巡檢", "公司自訂任務"]
    assert out2["current_step"] == "deep"
    assert spy.flushed[0] == "p1" and len(spy.flushed[1]) == 2


@pytest.mark.asyncio
async def test_task_pool_orders_tasks_by_ocs_priority():
    # indexer 回傳順序 OC1, OC2；但使用者優先度是 OC2 > OC1 → 任務應依 OC2 先
    pool = TaskPool(groups=[
        PoolGroup(ocs_code="OC1", job_title="工程師", units=[
            PoolUnit(unit_id="U1", unit_title="巡檢類", tasks=[
                PoolTask(id="OC1-T1", task_id="T1", task_title="巡檢A")])]),
        PoolGroup(ocs_code="OC2", job_title="技術員", units=[
            PoolUnit(unit_id="U2", unit_title="保養類", tasks=[
                PoolTask(id="OC2-T1", task_id="T1", task_title="保養B")])]),
    ])
    fake = FakeKnowledge(pool=pool)
    spy = SpyPersist()
    graph = _graph()
    s = new_state(job_profile_id="p1", job_title="工程師")
    s["profile"]["selected_ocs_codes"] = ["OC2", "OC1"]
    cfg = {"configurable": {"thread_id": "tp", "deps": Deps(knowledge=fake, persist=spy)}}

    out = await graph.ainvoke(s, cfg)
    intr = out["__interrupt__"][0].value
    # task_pool 應收到有序清單
    assert ("task_pool", ["OC2", "OC1"]) in fake.calls
    # 任務依優先度排序：OC2 的「保養B」在前
    assert [t["task_name"] for t in intr["tasks"]] == ["保養B", "巡檢A"]


@pytest.mark.asyncio
async def test_pool_tasks_carry_unit_info():
    from app.services.knowledge.models import TaskPool, PoolGroup, PoolUnit, PoolTask
    from app.graph_v3.nodes import _pool_to_tasks
    pool = TaskPool(groups=[PoolGroup(ocs_code="OC1", units=[
        PoolUnit(unit_id="U1", unit_title="預防保養", tasks=[
            PoolTask(id="x", task_id="T1.1", task_title="巡檢")])])])
    tasks = _pool_to_tasks(pool)
    assert tasks[0]["unit_id"] == "U1"
    assert tasks[0]["unit_title"] == "預防保養"
