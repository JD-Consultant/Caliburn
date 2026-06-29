import pytest
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from app.authoring.graph import build_graph
from app.authoring.state import new_state
from app.authoring.deps import Deps
from tests.conftest_graph import FakeKnowledge, SpyPersist, FakeLlm

_GOOD = {"has_situation": True, "has_purpose": True, "has_collaborators": True,
         "has_tools": True, "has_action": True, "has_output": True, "has_standard": True}


@pytest.mark.asyncio
async def test_two_task_deep_loop_reaches_fetch_ksa_pool():
    indicators = [{"output_name": "", "indicator_5w2h": "x", "indicator_abcd": "y",
                   "quality_dims": _GOOD}]
    star_refine = {"S": "s", "T": "t", "A": "a", "R": "r"}

    def _json(prompt):
        return star_refine if "STAR 四槽" in prompt else indicators
    llm = FakeLlm(json=_json)
    fake = FakeKnowledge()
    graph = build_graph(checkpointer=MemorySaver())
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

    # 深問 + curate_ks（逐任務）+ curate_attitudes + build_doc preview 全部 interrupt
    # 深問用 str resume；curate 用對應 dict；preview 用 True
    guard = 0
    while "__interrupt__" in out:
        kind = out["__interrupt__"][0].value.get("kind")
        if kind == "curate_ks":
            resume = {"ks": {"knowledge": [], "skills": []}}
        elif kind == "curate_attitudes":
            resume = {"attitudes": []}
        elif kind == "preview":
            resume = True
        else:
            resume = "作業員、ERP、零漏檢、當日完成"
        out = await graph.ainvoke(Command(resume=resume), cfg)
        guard += 1
        assert guard < 60, "迴圈未收斂"

    assert out["current_step"] == "done"
    assert all(t.get("behavior_indicators") for t in out["tasks"])
    assert len(out["tasks"]) == 2
    assert out["tasks"][0]["behavior_indicators"][0]["task_id"] == "T1.1"
    assert out["tasks"][1]["behavior_indicators"][0]["task_id"] == "T1.2"
