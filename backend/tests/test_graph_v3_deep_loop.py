import pytest
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from app.graph_v3.graph import build_graph_v3
from app.graph_v3.state import new_state
from app.graph_v3.deps import Deps
from app.services.knowledge.models import (
    SearchResult, Hit, TaskPool, PoolGroup, PoolUnit, PoolTask, TasksByIdResult)
from tests.conftest_graph import FakeKnowledge, SpyPersist, FakeLlm

_GOOD = {"has_situation": True, "has_purpose": True, "has_collaborators": True,
         "has_tools": True, "has_action": True, "has_output": True, "has_standard": True}


@pytest.mark.asyncio
async def test_two_task_deep_loop_reaches_assemble():
    indicators = [{"output_name": "", "indicator_5w2h": "x", "indicator_abcd": "y",
                   "quality_dims": _GOOD}]
    star_refine = {"S": "s", "T": "t", "A": "a", "R": "r"}

    def _json(prompt):
        return star_refine if "STAR 四槽" in prompt else indicators
    llm = FakeLlm(json=_json)
    fake = FakeKnowledge(
        search=SearchResult(mode="dense", hits=[Hit(id="p1", ocs_code="OC1", chunk_level="profile")]),
        pool=TaskPool(groups=[PoolGroup(ocs_code="OC1", units=[PoolUnit(tasks=[
            PoolTask(id="x1", task_id="T1.1", task_title="任務一"),
            PoolTask(id="x2", task_id="T1.2", task_title="任務二")])])]),
        tasks=TasksByIdResult(tasks=[]),  # 無 catalog outputs → 5W2H 全問
    )
    graph = build_graph_v3(checkpointer=MemorySaver())
    cfg = {"configurable": {"thread_id": "t1",
                            "deps": Deps(knowledge=fake, persist=SpyPersist(), llm=llm)}}

    out = await graph.ainvoke(new_state(job_profile_id="p1", job_title="工程師"), cfg)
    assert out["__interrupt__"][0].value["kind"] == "select_profile"

    out = await graph.ainvoke(Command(resume={"ocs_code": "OC1"}), cfg)
    assert out["__interrupt__"][0].value["kind"] == "edit_tasks"
    edited = [{"task_name": "任務一", "source": "catalog",
               "indexer_ref": {"ocs_code": "OC1", "task_id": "T1.1"}},
              {"task_name": "任務二", "source": "catalog",
               "indexer_ref": {"ocs_code": "OC1", "task_id": "T1.2"}}]
    out = await graph.ainvoke(Command(resume={"tasks": edited}), cfg)

    # 深問所有 interrupt：固定 answer 餵到結束
    guard = 0
    while "__interrupt__" in out:
        out = await graph.ainvoke(Command(resume="作業員、ERP、零漏檢、當日完成"), cfg)
        guard += 1
        assert guard < 60, "深問迴圈未收斂"

    assert out["current_step"] == "done"
    assert all(t.get("behavior_indicators") for t in out["tasks"])
    assert len(out["tasks"]) == 2
    assert out["tasks"][0]["behavior_indicators"][0]["task_id"] == "T1.1"
    assert out["tasks"][1]["behavior_indicators"][0]["task_id"] == "T1.2"
