"""Native in-memory checkpoint evidence; no model, database, or writer authority."""

from copy import deepcopy
from dataclasses import replace
from uuid import UUID

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.types import PregelTask, interrupt

from jd_relational.intents import AdmittedIdentity
from jd_relational.runtime_checkpoints import (
    CheckpointError, DocumentCheckpoints, build_document_graph,
)


DOC = "00000000-0000-4000-8000-000000000001"
OTHER_DOC = "00000000-0000-4000-8000-000000000002"
IDENTITY = AdmittedIdentity(
    DOC, UUID(int=11), UUID(int=12), "manual", None, "a" * 64, "jd_set_text",
)
PRIVATE = "synthetic private checkpoint driver detail"


def config(document_id=DOC):
    return {"configurable": {"thread_id": document_id}}


def test_native_child_runtime_receives_the_host_store():
    from langgraph.runtime import Runtime
    from langgraph.store.memory import InMemoryStore
    store = InMemoryStore()
    seen = []
    def node(state, runtime: Runtime):
        seen.append(runtime.store)
        runtime.store.put(("synthetic-runtime", DOC), "value", {"scope": DOC})
        return {}
    child = StateGraph(MessagesState)
    child.add_node("observe", node)
    child.add_edge(START, "observe"); child.add_edge("observe", END)
    graph = build_document_graph(child.compile(), InMemorySaver(), store=store)
    graph.invoke({"messages": []}, config(), durability="sync")
    assert seen == [store]
    assert store.get(("synthetic-runtime", DOC), "value").value == {"scope": DOC}


def test_a_child_cannot_bind_another_memory_store():
    from langgraph.store.memory import InMemoryStore
    child = StateGraph(MessagesState)
    child.add_node("observe", lambda state: {})
    child.add_edge(START, "observe"); child.add_edge("observe", END)
    child = child.compile(store=InMemoryStore())
    with pytest.raises(CheckpointError, match="invalid_input"):
        build_document_graph(child, InMemorySaver(), store=InMemoryStore())


def descriptor(identity=IDENTITY):
    return {
        "format_version": 1,
        "document_id": identity.document_id,
        "operation_id": str(identity.operation_id),
        "base_revision_id": str(identity.base_revision_id),
        "origin": identity.origin,
        "ai_run_id": identity.ai_run_id,
        "request_digest": identity.request_digest,
        "command_kind": identity.command_kind,
    }


def native_graph(*, paused=False, saver=None):
    calls = []

    def synthetic_consultant(state):
        calls.append("entered")
        if paused:
            interrupt("synthetic pause")
        return {"messages": [AIMessage(content="synthetic reply", id="reply")]}

    child_builder = StateGraph(MessagesState)
    child_builder.add_node("synthetic", synthetic_consultant)
    child_builder.add_edge(START, "synthetic")
    child_builder.add_edge("synthetic", END)
    saver = saver if saver is not None else InMemorySaver()
    child = child_builder.compile()
    return build_document_graph(child, saver), saver, calls


class ObservedGraph:
    """Inject transport faults around a real compiled graph, preserving its Saver."""

    def __init__(self, graph, *, update_mode="normal", fail_read_at=()):
        self.graph = graph
        self.update_mode = update_mode
        self.fail_read_at = set(fail_read_at)
        self.reads = []
        self.updates = []
        self.snapshot_transform = lambda snapshot: snapshot

    def get_state(self, supplied, **kwargs):
        self.reads.append((deepcopy(supplied), kwargs))
        if len(self.reads) in self.fail_read_at:
            raise RuntimeError(PRIVATE)
        return self.snapshot_transform(self.graph.get_state(supplied, **kwargs))

    def update_state(self, supplied, values, **kwargs):
        self.updates.append((deepcopy(supplied), deepcopy(values), kwargs))
        if self.update_mode == "fail_before":
            raise RuntimeError(PRIVATE)
        result = self.graph.update_state(supplied, values, **kwargs)
        if self.update_mode == "ack_lost":
            raise RuntimeError(PRIVATE)
        return result


def safe_error(code):
    return pytest.raises(CheckpointError, match=f"^{code}$")


def test_fresh_manual_admit_close_are_native_root_only_and_never_invoke_child():
    graph, saver, calls = native_graph()
    observed = ObservedGraph(graph)
    adapter = DocumentCheckpoints(observed)
    assert adapter.read(DOC) is None
    adapter.admit(IDENTITY)
    assert adapter.read(DOC) == IDENTITY
    assert graph.get_state(config()).values["jd_manual_pending"] == descriptor()
    update_count = len(observed.updates)
    adapter.admit(IDENTITY)
    assert len(observed.updates) == update_count
    adapter.close(IDENTITY)
    adapter.close(IDENTITY)
    assert adapter.read(DOC) is None
    assert calls == []
    assert graph.get_state(config()).values.get("messages", []) == []
    assert list(saver.list(config()))
    assert {entry.config["configurable"]["checkpoint_ns"] for entry in saver.list(config())} == {""}
    for supplied, kwargs in observed.reads:
        assert supplied == config()
        assert kwargs == {"subgraphs": True}
    for supplied, values, kwargs in observed.updates:
        assert supplied == config()
        assert set(values) == {"jd_manual_pending"}
        assert kwargs == {"as_node": "consultant"}


def test_messages_and_provider_native_blocks_survive_admit_close_and_adapter_restart():
    graph, saver, calls = native_graph()
    messages = [
        HumanMessage(content="原始問題\n不可重建", id="human-original"),
        AIMessage(content=[
            {"type": "reasoning", "id": "opaque-reasoning", "encrypted_content": "synthetic-opaque"},
            {"type": "compaction", "encrypted_content": "synthetic-compaction"},
            {"type": "text", "text": "原始回答"},
        ], id="assistant-original", tool_calls=[
            {"name": "synthetic_tool", "args": {"preserve": True}, "id": "call-original", "type": "tool_call"},
        ]),
        ToolMessage(content="原始工具結果", tool_call_id="call-original", id="tool-original"),
    ]
    graph.update_state(config(), {"messages": messages}, as_node="consultant")
    before = [message.model_dump() for message in graph.get_state(config()).values["messages"]]
    DocumentCheckpoints(graph).admit(IDENTITY)
    replacement_graph, _, replacement_calls = native_graph(saver=saver)
    # A fresh root compilation against the same Saver reconstructs the identity.
    restarted = DocumentCheckpoints(replacement_graph)
    assert restarted.read(DOC) == IDENTITY
    restarted.close(IDENTITY)
    assert [message.model_dump() for message in graph.get_state(config()).values["messages"]] == before
    assert calls == replacement_calls == []


@pytest.mark.parametrize("method", ["read", "admit", "close"])
def test_native_interrupted_child_is_busy_even_without_a_local_future(method):
    graph, _, calls = native_graph(paused=True)
    graph.invoke({"messages": [HumanMessage(content="pause", id="pause")]}, config(), durability="sync")
    snapshot = graph.get_state(config(), subgraphs=True)
    assert snapshot.next == ("consultant",)
    assert snapshot.tasks and snapshot.tasks[0].state.tasks
    observed = ObservedGraph(graph)
    with safe_error("document_busy"):
        getattr(DocumentCheckpoints(observed), method)(DOC if method == "read" else IDENTITY)
    assert len(calls) == 1
    assert observed.updates == []
    assert graph.get_state(config(), subgraphs=True) == snapshot


def test_tasks_alone_cannot_be_misread_as_idle():
    graph, _, _ = native_graph()
    observed = ObservedGraph(graph)
    observed.snapshot_transform = lambda snapshot: snapshot._replace(
        next=(), tasks=(PregelTask("pending-native", "consultant", ()),),
    )
    with safe_error("document_busy"):
        DocumentCheckpoints(observed).admit(IDENTITY)
    assert observed.updates == []


@pytest.mark.parametrize("method", ["admit", "close"])
@pytest.mark.parametrize("patch", [
    {"operation_id": UUID(int=13)}, {"base_revision_id": UUID(int=13)},
    {"request_digest": "b" * 64}, {"command_kind": "jd_delete_item"},
])
def test_different_identity_cannot_overwrite_or_clear_pending(method, patch):
    graph, _, _ = native_graph()
    adapter = DocumentCheckpoints(graph)
    adapter.admit(IDENTITY)
    other = replace(IDENTITY, **patch)
    with safe_error("pending_conflict"):
        getattr(adapter, method)(other)
    assert adapter.read(DOC) == IDENTITY


@pytest.mark.parametrize("method", ["admit", "close"])
def test_update_ack_lost_succeeds_only_after_one_matching_native_readback(method):
    graph, _, _ = native_graph()
    if method == "close":
        DocumentCheckpoints(graph).admit(IDENTITY)
    observed = ObservedGraph(graph, update_mode="ack_lost")
    getattr(DocumentCheckpoints(observed), method)(IDENTITY)
    assert len(observed.updates) == 1
    assert len(observed.reads) == 2
    assert DocumentCheckpoints(graph).read(DOC) == (IDENTITY if method == "admit" else None)


@pytest.mark.parametrize("method", ["admit", "close"])
def test_ack_lost_readback_of_a_different_pending_identity_is_not_success(method):
    graph, _, _ = native_graph()
    if method == "close":
        DocumentCheckpoints(graph).admit(IDENTITY)
    observed = ObservedGraph(graph, update_mode="ack_lost")
    other = replace(IDENTITY, operation_id=UUID(int=13))
    observed.snapshot_transform = lambda snapshot: (
        snapshot._replace(values=snapshot.values | {"jd_manual_pending": descriptor(other)})
        if len(observed.reads) == 2 else snapshot
    )
    with safe_error("pending_conflict"):
        getattr(DocumentCheckpoints(observed), method)(IDENTITY)
    assert len(observed.reads) == 2
    assert len(observed.updates) == 1


@pytest.mark.parametrize("method", ["admit", "close"])
def test_matching_readback_with_unfinished_native_work_is_not_confirmation(method):
    graph, _, _ = native_graph()
    if method == "close":
        DocumentCheckpoints(graph).admit(IDENTITY)
    observed = ObservedGraph(graph)
    observed.snapshot_transform = lambda snapshot: (
        snapshot._replace(tasks=(PregelTask("native-work", "consultant", ()),))
        if len(observed.reads) == 2 else snapshot
    )
    with safe_error("document_busy"):
        getattr(DocumentCheckpoints(observed), method)(IDENTITY)
    assert len(observed.reads) == 2
    assert len(observed.updates) == 1


@pytest.mark.parametrize("method", ["admit", "close"])
@pytest.mark.parametrize("mode,fail_read_at", [("fail_before", ()), ("ack_lost", (2,)), ("normal", (2,))])
def test_failed_write_or_unavailable_readback_never_claims_confirmation(method, mode, fail_read_at):
    graph, _, _ = native_graph()
    if method == "close":
        DocumentCheckpoints(graph).admit(IDENTITY)
    observed = ObservedGraph(graph, update_mode=mode, fail_read_at=fail_read_at)
    with safe_error("checkpoint_unavailable") as caught:
        getattr(DocumentCheckpoints(observed), method)(IDENTITY)
    assert len(observed.reads) == 2
    assert len(observed.updates) == 1
    assert caught.value.code == "checkpoint_unavailable"
    assert caught.value.__cause__ is None
    assert PRIVATE not in str(caught.value)


@pytest.mark.parametrize("method", ["read", "admit", "close"])
def test_initial_checkpoint_failure_is_safe_and_does_not_write(method):
    graph, _, _ = native_graph()
    observed = ObservedGraph(graph, fail_read_at=(1,))
    with safe_error("checkpoint_unavailable") as caught:
        getattr(DocumentCheckpoints(observed), method)(DOC if method == "read" else IDENTITY)
    assert caught.value.__cause__ is None
    assert PRIVATE not in str(caught.value)
    assert observed.updates == []


@pytest.mark.parametrize("patch", [
    {"format_version": None}, {"format_version": True}, {"format_version": 2},
    {"operation_id": "not-a-uuid"}, {"base_revision_id": UUID(int=12)},
    {"document_id": OTHER_DOC}, {"document_id": "invalid-document"},
    {"origin": "ai", "ai_run_id": "synthetic-ai"}, {"ai_run_id": "unexpected"},
    {"request_digest": "a" * 63}, {"command_kind": "not_a_command"}, {"extra": None},
])
def test_invalid_persisted_descriptor_is_rejected_without_repair_or_write(patch):
    graph, _, _ = native_graph()
    invalid = descriptor() | patch
    graph.update_state(config(), {"jd_manual_pending": invalid}, as_node="consultant")
    observed = ObservedGraph(graph)
    with safe_error("invalid_checkpoint"):
        DocumentCheckpoints(observed).read(DOC)
    assert observed.updates == []


@pytest.mark.parametrize("invalid", [{}, [], "not-json-object", {"format_version": 1}])
def test_missing_descriptor_fields_are_not_empty_pending(invalid):
    graph, _, _ = native_graph()
    graph.update_state(config(), {"jd_manual_pending": invalid}, as_node="consultant")
    with safe_error("invalid_checkpoint"):
        DocumentCheckpoints(graph).read(DOC)


@pytest.mark.parametrize("method", ["admit", "close"])
def test_ai_identity_and_non_typed_input_are_invalid_for_manual_adapter(method):
    graph, _, _ = native_graph()
    observed = ObservedGraph(graph)
    for invalid in [replace(IDENTITY, origin="ai", ai_run_id="synthetic-ai"), descriptor(), None]:
        with safe_error("invalid_input"):
            getattr(DocumentCheckpoints(observed), method)(invalid)
    assert observed.reads == observed.updates == []


@pytest.mark.parametrize("invalid", [None, {}, "", "not-a-uuid", UUID(DOC)])
def test_invalid_document_id_never_reaches_checkpoint(invalid):
    graph, _, _ = native_graph()
    observed = ObservedGraph(graph)
    with safe_error("invalid_input"):
        DocumentCheckpoints(observed).read(invalid)
    assert observed.reads == []


def test_document_roots_are_isolated_and_existing_pending_is_read_from_latest():
    graph, _, _ = native_graph()
    adapter = DocumentCheckpoints(graph)
    other = replace(IDENTITY, document_id=OTHER_DOC, operation_id=UUID(int=21))
    adapter.admit(IDENTITY)
    old_config = graph.get_state(config()).config
    adapter.admit(other)
    adapter.close(IDENTITY)
    assert graph.get_state(old_config).values["jd_manual_pending"] == descriptor()
    assert adapter.read(DOC) is None
    assert adapter.read(OTHER_DOC) == other


def test_builder_rejects_callable_child_and_child_with_a_different_or_disabled_saver():
    saver = InMemorySaver()
    with safe_error("invalid_input"):
        build_document_graph(lambda state: state, saver)
    child_builder = StateGraph(MessagesState)
    child_builder.add_node("synthetic", lambda state: {"messages": []})
    child_builder.add_edge(START, "synthetic")
    child_builder.add_edge("synthetic", END)
    for child_saver in [False, InMemorySaver()]:
        with safe_error("invalid_input"):
            build_document_graph(child_builder.compile(checkpointer=child_saver), saver)
    with safe_error("invalid_input"):
        build_document_graph(child_builder.compile(), None)
    assert list(saver.list(config())) == []


def test_adapter_revalidates_even_a_typed_identity_before_checkpoint_access():
    graph, _, _ = native_graph()
    observed = ObservedGraph(graph)
    invalid = replace(IDENTITY)
    object.__setattr__(invalid, "operation_id", "not-a-uuid")
    with safe_error("invalid_input"):
        DocumentCheckpoints(observed).admit(invalid)
    assert observed.reads == observed.updates == []
