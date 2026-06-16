import pytest
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from app.graph_v3.graph import build_graph_v3
from app.graph_v3.state import new_state
from app.graph_v3.deps import Deps
from app.services.knowledge.models import SearchResult, Hit, TaskPool, PoolGroup, PoolUnit, PoolTask
from tests.conftest_graph import FakeKnowledge, SpyPersist, FakeLlm


@pytest.mark.asyncio
async def test_full_two_node_slice():
    fake = FakeKnowledge(
        search=SearchResult(mode="dense", hits=[Hit(id="p1", ocs_code="OC1", chunk_level="profile")]),
        pool=TaskPool(groups=[PoolGroup(ocs_code="OC1", units=[
            PoolUnit(tasks=[PoolTask(id="x", task_id="T1.1", task_title="巡檢")])])]))
    spy = SpyPersist()
    graph = build_graph_v3(checkpointer=MemorySaver())
    cfg = {"configurable": {"thread_id": "t1", "deps": Deps(knowledge=fake, persist=spy, llm=FakeLlm())}}

    out = await graph.ainvoke(new_state(job_profile_id="p1", job_title="工程師"), cfg)
    assert out["__interrupt__"][0].value["kind"] == "select_profile"

    out = await graph.ainvoke(Command(resume={"ocs_code": "OC1"}), cfg)
    assert out["__interrupt__"][0].value["kind"] == "edit_tasks"

    out = await graph.ainvoke(Command(resume={"tasks": [{"task_name": "巡檢", "source": "catalog"}]}), cfg)
    # Phase ③：task_pool 後直接進深問，停在第一個 STAR 提問
    assert out["__interrupt__"][0].value["stage"] == "star"
    assert spy.selected == ("p1", "OC1") and spy.flushed[0] == "p1"
