import pytest
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from app.graph_v3.state import new_state, InterviewState
from app.graph_v3.deep_nodes import five_w2h_node
from app.graph_v3.deps import Deps
from app.services.knowledge.models import TasksByIdResult, TaskDetail, Pair
from tests.conftest_graph import FakeKnowledge, SpyPersist, FakeLlm
from app.graph.constants import FIVE_W2H_REQUIRED


def _graph():
    g = StateGraph(InterviewState)
    g.add_node("five_w2h", five_w2h_node)
    g.add_edge(START, "five_w2h")
    g.add_edge("five_w2h", END)
    return g.compile(checkpointer=MemorySaver())


def _state():
    s = new_state(job_profile_id="p1", job_title="設備維護工程師")
    s["tasks"] = [{
        "task_name": "例行設備巡檢", "source": "catalog",
        "indexer_ref": {"ocs_code": "OC1", "task_id": "T1.1"},
        "star_case": {"situation": "晨班產線A", "task": "確保可用",
                      "action": "逐項點檢、記錄異常", "result": "停機下降"},
    }]
    return s


@pytest.mark.asyncio
async def test_five_w2h_prefills_then_asks_remaining():
    # catalog 供 outputs → outputs 不再問；star 供 situation+workflow_steps
    detail = TaskDetail(id="T1.1", ocs_code="OC1", task_id="T1.1", task_title="例行設備巡檢",
                        output_pairs=[Pair(code="O1", name="點檢表"), Pair(code="O2", name="異常通報")])
    fake = FakeKnowledge(tasks=TasksByIdResult(tasks=[detail]))
    graph = _graph()
    cfg = {"configurable": {"thread_id": "t1",
                            "deps": Deps(knowledge=fake, persist=SpyPersist(), llm=FakeLlm())}}

    out = await graph.ainvoke(_state(), cfg)
    asked = []
    # 逐欄回答直到節點完成（無 __interrupt__）
    while "__interrupt__" in out:
        payload = out["__interrupt__"][0].value
        assert payload["kind"] == "ask_human" and payload["stage"] == "five_w2h"
        asked.append(payload["field"])
        out = await graph.ainvoke(Command(resume="作業員、ERP系統"), cfg)

    # 被預填者不應被問
    assert "situation" not in asked        # star 預填
    assert "workflow_steps" not in asked    # star.action 預填
    assert "outputs" not in asked           # catalog 預填
    # 其餘必填欄都問到
    remaining = [f for f in FIVE_W2H_REQUIRED if f not in {"situation", "workflow_steps", "outputs"}]
    assert asked == remaining

    task = out["tasks"][0]
    assert task["outputs"] == ["點檢表", "異常通報"]            # catalog 預填
    assert task["workflow_steps"]                               # star 預填
    assert task["collaborators"] == ["作業員", "ERP系統"]       # list 欄位切分
    assert task["purpose"] == "作業員、ERP系統"                 # 純字串欄位


@pytest.mark.asyncio
async def test_five_w2h_company_task_no_catalog_prefill():
    s = new_state(job_profile_id="p1", job_title="X")
    s["tasks"] = [{"task_name": "公司自訂任務", "source": "company"}]  # 無 indexer_ref
    fake = FakeKnowledge()  # tasks_by_id → 空
    graph = _graph()
    cfg = {"configurable": {"thread_id": "t2",
                            "deps": Deps(knowledge=fake, persist=SpyPersist(), llm=FakeLlm())}}
    out = await graph.ainvoke(s, cfg)
    # 無 catalog → 不應呼叫 tasks_by_id（無 indexer_ref 時跳過）
    assert not any(c[0] == "tasks_by_id" for c in fake.calls)
    assert "__interrupt__" in out  # 直接開始逐欄問
