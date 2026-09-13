"""Static native C graph with per-invocation resources; zero provider calls."""
from contextlib import contextmanager
from dataclasses import asdict
from types import SimpleNamespace
from uuid import uuid4

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.config import get_config
from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from langgraph.store.memory import InMemoryStore
from langgraph.types import Command, interrupt
import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from caliburn_memory.memory import MemoryArtifacts
from caliburn_memory.publication import PublicationStore
from caliburn_memory.repair import RepairState, RepairWorkflow
import caliburn_memory.repair as repair_module
from conftest import ExampleSource


@contextmanager
def resources(document):
    source = ExampleSource(document)
    artifacts = MemoryArtifacts(InMemoryStore(), document, source=source)
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    publication = PublicationStore(engine, artifacts)
    publication.setup()
    memory = artifacts.save_memory(knowledge="例外由主管核准。", guide="主管核准：/memory/knowledge.md")
    head = publication.publish(publication.prepare(memory, expected_revision=0,
        kind="consolidation", processed_source=source.reference))
    try:
        yield SimpleNamespace(source=source, artifacts=artifacts, publication=publication,
            head=head, workflow=RepairWorkflow(artifacts, publication, source))
    finally:
        engine.dispose()


def payload(item, *, two_edits=False):
    edits = [{"path": "/memory/knowledge.md", "diff": "@@\n-例外由主管核准。\n+例外由處長核准。"}]
    if two_edits:
        edits.append({"path": "/memory/guide.md", "diff": "@@\n-主管核准：/memory/knowledge.md\n+處長核准：/memory/knowledge.md"})
    return {"operation_id": str(uuid4()), "base": asdict(item.head),
        "source_reference": item.source.context_reference, "edits": edits}


def config(document):
    return {"configurable": {"thread_id": document}}


def parent(child):
    builder = StateGraph(RepairState, context_schema=dict)
    builder.add_node("repair", child)
    builder.add_edge(START, "repair")
    builder.add_edge("repair", END)
    return builder.compile(checkpointer=InMemorySaver())


def test_build_inspection_and_empty_state_do_not_resolve_resources():
    calls = []
    def forbidden(runtime):
        calls.append(runtime)
        raise AssertionError("Inspection must not resolve live resources")
    child = repair_module.build_repair_graph(forbidden)
    graph = parent(child)
    assert set(child.nodes) == {"__start__", "seed", "edit", "validate", "save", "prepare", "publish"}
    assert [name for name, _ in graph.get_subgraphs()] == ["repair"]
    graph.get_graph()
    assert graph.get_state(config("document-a"), subgraphs=True).values == {}
    assert calls == []


def test_static_graph_resolves_each_native_step_from_that_runs_context():
    calls = []
    def resolve(runtime):
        assert isinstance(runtime, Runtime)
        item = runtime.context["resources"]
        calls.append((item.source.document_id, get_config()["metadata"]["langgraph_node"]))
        return item.workflow
    graph = parent(repair_module.build_repair_graph(resolve))
    with resources("document-a") as first, resources("document-b") as second:
        for item in (first, second):
            original = payload(item, two_edits=True)
            result = graph.invoke(original, config(item.source.document_id),
                context={"resources": item}, durability="sync")
            assert result["outcome"]["status"] == "applied"
            assert item.publication.receipt(original["operation_id"]).result.revision == 2
            assert item.publication.current().processed_source == item.head.processed_source
            assert item.artifacts.read_text("/memory/knowledge.md", item.publication.current().memory) == "例外由處長核准。"
        expected = ["seed", "edit", "edit", "validate", "save", "prepare", "publish"]
        assert calls == [(document, step) for document in ("document-a", "document-b") for step in expected]
        assert graph.get_state(config("document-a")).values["source_reference"] == first.source.context_reference
        assert graph.get_state(config("document-b")).values["source_reference"] == second.source.context_reference
        assert len(calls) == 14  # Reading either saved state did not resolve a workflow.


def test_static_child_can_be_read_after_interrupt_without_context_or_resolver_call(monkeypatch):
    calls = []
    def resolve(runtime):
        calls.append(runtime.context["label"])
        return runtime.context["workflow"]
    graph = parent(repair_module.build_repair_graph(resolve))
    with resources("document-a") as item:
        actual_publish = item.workflow._publish
        def paused_publish(state):
            interrupt("before_publication")
            return actual_publish(state)
        monkeypatch.setattr(item.workflow, "_publish", paused_publish)
        original = payload(item)
        graph.invoke(original, config("document-a"),
            context={"label": "first", "workflow": item.workflow}, durability="sync")
        assert calls == ["first"] * 6
        root = graph.get_state(config("document-a"), subgraphs=True)
        child = root.tasks[0].state
        fixed = graph.get_state(child.config, subgraphs=True)
        assert fixed.next == ("publish",)
        assert fixed.values["request"]["operation_id"] == original["operation_id"]
        assert item.publication.receipt(original["operation_id"]) is None
        assert calls == ["first"] * 6
        # Core-only explicit resume demonstrates resolver context is not captured
        # from the initial invocation. It is not an App recovery/replay policy.
        replacement = RepairWorkflow(item.artifacts, item.publication, item.source)
        result = graph.invoke(Command(resume=True), config("document-a"),
            context={"label": "replacement", "workflow": replacement}, durability="sync")
        assert result["outcome"]["status"] == "applied"
        assert calls == ["first"] * 6 + ["replacement"]
        assert item.publication.current().revision == 2


def test_non_workflow_resolver_result_fails_before_source_or_publication():
    graph = parent(repair_module.build_repair_graph(lambda runtime: object()))
    with resources("document-a") as item:
        item.source.reads.clear()
        original = payload(item)
        with pytest.raises(TypeError) as raised:
            graph.invoke(original, config("document-a"), context={}, durability="sync")
        assert str(raised.value) == "repair_workflow_unavailable"
        assert item.source.reads == []
        assert item.publication.current() == item.head
        assert item.publication.receipt(original["operation_id"]) is None


def test_resolver_io_failure_is_not_converted_to_patch_feedback():
    error = ValueError("synthetic_source_unavailable")
    def unavailable(runtime):
        raise error
    graph = parent(repair_module.build_repair_graph(unavailable))
    with resources("document-a") as item:
        original = payload(item)
        with pytest.raises(ValueError) as raised:
            graph.invoke(original, config("document-a"), context={}, durability="sync")
        assert raised.value is error
        assert item.publication.current() == item.head
        assert item.publication.receipt(original["operation_id"]) is None


def test_factory_rejects_non_callable_without_building_an_executable_graph():
    with pytest.raises(TypeError):
        repair_module.build_repair_graph(None)
