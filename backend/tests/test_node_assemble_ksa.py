import pytest
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from app.graph_v3.state import new_state, InterviewState
from app.graph_v3.assemble_nodes import assemble_ksa
from app.graph_v3.deps import Deps
from app.services.knowledge.models import Pairs, Pair
from tests.conftest_graph import FakeKnowledge, SpyPersist, FakeLlm


def _graph():
    g = StateGraph(InterviewState)
    g.add_node("assemble_ksa", assemble_ksa)
    g.add_edge(START, "assemble_ksa")
    g.add_edge("assemble_ksa", END)
    return g.compile(checkpointer=MemorySaver())


def _state():
    s = new_state(job_profile_id="p1", job_title="設備維護工程師")
    s["profile"] = {"candidates": [], "selected_ocs_code": "OC1"}
    return s


@pytest.mark.asyncio
async def test_assemble_ksa_from_catalog_then_edit_and_flush(monkeypatch):
    pairs = Pairs(ocs_code="OC1",
                  knowledge=[Pair(code="K01", name="設備原理")],
                  skills=[Pair(code="S01", name="點檢操作")],
                  attitudes=[Pair(code="A01", name="細心")])
    fake = FakeKnowledge()
    async def _pairs(ocs_code): return pairs
    monkeypatch.setattr(fake, "pairs", _pairs)
    spy = SpyPersist()
    graph = _graph()
    cfg = {"configurable": {"thread_id": "t1",
                            "deps": Deps(knowledge=fake, persist=spy, llm=FakeLlm())}}

    out = await graph.ainvoke(_state(), cfg)
    payload = out["__interrupt__"][0].value
    assert payload["kind"] == "edit_ksa"
    # draft 帶 catalog 來源 + icap_ref
    assert payload["ksa"]["knowledge"][0] == {"content": "設備原理", "source": "catalog", "icap_ref": "K01"}

    # 人編輯：加一條公司補充
    edited = {"knowledge": payload["ksa"]["knowledge"] + [{"content": "公司SOP", "source": "company", "icap_ref": None}],
              "skills": payload["ksa"]["skills"], "attitudes": payload["ksa"]["attitudes"]}
    out = await graph.ainvoke(Command(resume={"ksa": edited}), cfg)

    assert out["current_step"] == "build_doc"
    assert len(out["ksa"]["knowledge"]) == 2
    assert spy.ksa_flushed[0] == "p1"
    assert len(spy.ksa_flushed[1]["knowledge"]) == 2
