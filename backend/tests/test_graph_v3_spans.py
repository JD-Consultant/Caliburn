import pytest
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from app.graph_v3.tracing import setup_tracing
from app.graph_v3.graph import build_graph_v3
from app.graph_v3.state import new_state
from app.graph_v3.deps import Deps
from app.services.knowledge.models import SearchResult, Hit, TaskPool, PoolGroup, PoolUnit, PoolTask
from tests.conftest_graph import FakeKnowledge, SpyPersist, FakeLlm


@pytest.mark.asyncio
async def test_nodes_emit_spans():
    exp = InMemorySpanExporter()
    setup_tracing(exp, force=True)
    fake = FakeKnowledge(
        search=SearchResult(mode="dense", hits=[Hit(id="p1", ocs_code="OC1", chunk_level="profile")]),
        pool=TaskPool(groups=[PoolGroup(ocs_code="OC1", units=[
            PoolUnit(unit_id="U1", unit_title="u", tasks=[PoolTask(id="x", task_id="T1.1", task_title="巡檢")])])]))
    graph = build_graph_v3(checkpointer=MemorySaver())
    cfg = {"configurable": {"thread_id": "t1", "deps": Deps(knowledge=fake, persist=SpyPersist(), llm=FakeLlm())}}

    out = await graph.ainvoke(new_state(job_profile_id="p1", job_title="工程師"), cfg)
    await graph.ainvoke(Command(resume={"ocs_code": "OC1"}), cfg)
    names = {s.name for s in exp.get_finished_spans()}
    assert "node.pick_profile" in names
    assert "node.build_task_pool" in names
