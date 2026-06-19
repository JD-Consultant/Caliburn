import pytest
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from app.graph_v3.graph import build_graph_v3
from app.graph_v3.state import new_state
from app.graph_v3.deps import Deps
from app.services.knowledge.models import (
    SearchResult, Hit, TaskPool, PoolGroup, PoolUnit, PoolTask, TasksByIdResult, Pairs, Pair)
from tests.conftest_graph import FakeKnowledge, SpyPersist, FakeLlm

_GOOD = {"has_situation": True, "has_purpose": True, "has_collaborators": True,
         "has_tools": True, "has_action": True, "has_output": True, "has_standard": True}


@pytest.mark.asyncio
async def test_full_flow_pick_to_done(monkeypatch):
    star_refine = {"S": "s", "T": "t", "A": "a", "R": "r"}
    indicators = [{"output_name": "點檢表", "indicator_5w2h": "x", "indicator_abcd": "y",
                   "quality_dims": _GOOD}]
    def _json(prompt):
        return star_refine if "STAR 四槽" in prompt else indicators
    fake = FakeKnowledge(
        search=SearchResult(mode="dense", hits=[Hit(id="p1", ocs_code="OC1", chunk_level="profile")]),
        pool=TaskPool(groups=[PoolGroup(ocs_code="OC1", units=[
            PoolUnit(unit_id="U1", unit_title="預防保養", tasks=[
                PoolTask(id="x1", task_id="T1.1", task_title="巡檢")])])]),
        tasks=TasksByIdResult(tasks=[]))
    async def _pairs(ocs_code):
        return Pairs(ocs_code="OC1", knowledge=[Pair(code="K01", name="設備原理")],
                     skills=[], attitudes=[])
    monkeypatch.setattr(fake, "pairs", _pairs)
    spy = SpyPersist()
    graph = build_graph_v3(checkpointer=MemorySaver())
    cfg = {"configurable": {"thread_id": "t1",
                            "deps": Deps(knowledge=fake, persist=spy, llm=FakeLlm(json=_json))}}

    out = await graph.ainvoke(new_state(job_profile_id="p1", job_title="工程師"), cfg)
    out = await graph.ainvoke(Command(resume={"ocs_code": "OC1"}), cfg)        # select_profile
    out = await graph.ainvoke(Command(resume={"tasks": [
        {"task_name": "巡檢", "source": "catalog", "unit_id": "U1", "unit_title": "預防保養",
         "indexer_ref": {"ocs_code": "OC1", "task_id": "T1.1"}}]}), cfg)        # edit_tasks
    # 深問所有 interrupt（ask_human）
    guard = 0
    while "__interrupt__" in out and out["__interrupt__"][0].value["kind"] == "ask_human":
        out = await graph.ainvoke(Command(resume="作業員、ERP、零漏檢、當日完成"), cfg)
        guard += 1; assert guard < 40
    # curate_ks：逐任務一次（本測試 1 任務）
    assert out["__interrupt__"][0].value["kind"] == "curate_ks"
    out = await graph.ainvoke(Command(resume={"ks": {"knowledge": [], "skills": []}}), cfg)
    # curate_attitudes：全域一次
    assert out["__interrupt__"][0].value["kind"] == "curate_attitudes"
    out = await graph.ainvoke(Command(resume={"attitudes": []}), cfg)
    # build_doc preview
    assert out["__interrupt__"][0].value["kind"] == "preview"
    out = await graph.ainvoke(Command(resume=True), cfg)

    assert out["current_step"] == "done"
    assert out["document"]["ocs_content"]["ocu_units"][0]["tasks"][0]["task_code"] == "T1.1"
    assert spy.doc_saved[0] == "p1"
