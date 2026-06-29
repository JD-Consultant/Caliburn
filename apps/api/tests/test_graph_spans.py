import pytest
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from app.authoring.tracing import setup_tracing
from app.authoring.graph import build_graph
from app.authoring.state import new_state
from app.authoring.deps import Deps
from tests.conftest_graph import FakeKnowledge, SpyPersist, FakeLlm


@pytest.mark.asyncio
async def test_nodes_emit_spans():
    exp = InMemorySpanExporter()
    setup_tracing(exp, force=True)
    fake = FakeKnowledge()
    graph = build_graph(checkpointer=MemorySaver())
    cfg = {"configurable": {"thread_id": "t1", "deps": Deps(knowledge=fake, persist=SpyPersist(), llm=FakeLlm())}}

    out = await graph.ainvoke(new_state(job_profile_id="p1", job_title="工程師"), cfg)
    await graph.ainvoke(Command(resume={"ocs_code": "OC1"}), cfg)
    names = {s.name for s in exp.get_finished_spans()}
    assert "node.pick_profile" in names
    assert "node.build_task_pool" in names
