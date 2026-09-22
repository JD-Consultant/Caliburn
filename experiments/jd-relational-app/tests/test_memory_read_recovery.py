"""Selected Memory binding in native checkpoints; no Store, DB or provider."""
from copy import deepcopy
from hashlib import sha256
from uuid import uuid4

from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.types import interrupt
import pytest

from jd_relational.ai_checkpoints import AiCheckpointError, AiRunCheckpoints, new_run_record
from test_ai_checkpoints import Wrapper, close


DATASET, DOCUMENT = str(uuid4()), str(uuid4())
ORIGINAL = "員工原話\r\n  先確認條件；權限仍未知。"
OMIT = object()


class State(MessagesState):
    jd_ai_run: dict | None
    jd_ai_bindings: list
    jd_ai_read: dict | None
    jd_model_view: dict | None
    jd_memory_view: dict | None


def selected(run_id, *, revision=3):
    return {"format_version": 1, "dataset_id": DATASET, "document_id": DOCUMENT,
        "run_id": run_id, "revision": revision,
        "version_id": str(uuid4()) if revision else None,
        "guide_digest": sha256("固定導覽".encode()).hexdigest()}


def graph_fixture(*, pause=True):
    calls = []
    def model(state):
        calls.append(state["jd_ai_run"]["run_id"])
        return {"messages": [AIMessage(id=str(uuid4()), content="合成公開回覆")]}
    def hold(state):
        if pause:
            interrupt("synthetic stopped after model")
        return {}
    child = StateGraph(State)
    child.add_node("model", model); child.add_node("hold", hold)
    child.add_edge(START, "model"); child.add_edge("model", "hold"); child.add_edge("hold", END)
    root = StateGraph(State)
    root.add_node("consultant", child.compile())
    root.add_edge(START, "consultant"); root.add_edge("consultant", END)
    return root.compile(checkpointer=InMemorySaver()), calls


def config():
    return {"configurable": {"thread_id": DOCUMENT}}


def invoke(graph, run_id, view=OMIT, *, fail_start=False):
    record, human = new_run_record(DATASET, DOCUMENT, run_id, ORIGINAL,
        start_revision_id=str(uuid4()))
    payload = {"jd_ai_run": record.model_dump(mode="json"), "messages": [human],
        "jd_ai_bindings": [], "jd_ai_read": None}
    if view is not OMIT:
        payload["jd_memory_view"] = deepcopy(view)
    if not fail_start:
        graph.invoke(payload, config(), durability="sync")
        return
    original_put, failures = graph.checkpointer.put, []
    def fail_loop(config, checkpoint, metadata, new_versions):
        if not config["configurable"].get("checkpoint_ns") and metadata["source"] == "loop":
            failures.append(True)
            raise OSError("synthetic initial loop failure")
        return original_put(config, checkpoint, metadata, new_versions)
    graph.checkpointer.put = fail_loop
    try:
        with pytest.raises(OSError, match="synthetic initial loop failure"):
            graph.invoke(payload, config(), durability="sync")
    finally:
        graph.checkpointer.put = original_put
    assert failures


@pytest.mark.parametrize("ack", ["normal", "after"])
@pytest.mark.parametrize("revision", [0, 3])
def test_native_child_selected_view_survives_close_ack_loss_and_reopen_without_store(ack, revision, monkeypatch):
    from caliburn_memory import MemoryArtifacts, PublicationStore
    def forbidden(*args, **kwargs):
        pytest.fail("Checkpoint recovery must not reopen a Memory publication or artifact")
    monkeypatch.setattr(PublicationStore, "current", forbidden)
    monkeypatch.setattr(MemoryArtifacts, "guide", forbidden)
    monkeypatch.setattr(MemoryArtifacts, "read_text", forbidden)
    graph, calls = graph_fixture()
    run_id = str(uuid4()); view = selected(run_id, revision=revision)
    invoke(graph, run_id, view)
    wrapped = Wrapper(graph, ack); adapter = AiRunCheckpoints(wrapped)
    observed = adapter.discover(DOCUMENT, DATASET)
    assert not observed.closed and observed.root_config != observed.source_config
    assert observed.memory_view == view
    assert observed.model_view is None  # Selected Memory is not a model-read receipt.
    returned = observed.memory_view
    returned["revision"] = 900
    assert observed.memory_view == view
    result = close(adapter, observed, status="failed")
    assert result.closed and result.memory_view == view
    assert len(wrapped.updates) == 1 and wrapped.updates[0][1]["jd_memory_view"] == view
    reopened = AiRunCheckpoints(graph).observe(DOCUMENT, run_id, DATASET)
    assert reopened.memory_view == view and calls == [run_id]
    assert reopened.messages[0].content == ORIGINAL and reopened.messages[0].id == run_id
    assert close(adapter, result, status="failed") == result and len(wrapped.updates) == 1


@pytest.mark.parametrize("prior", [False, True])
@pytest.mark.parametrize("include_view", [False, True])
def test_start_payload_selects_its_own_view_and_legacy_missing_does_not_inherit_prior(prior, include_view):
    graph, calls = graph_fixture(pause=False)
    adapter = AiRunCheckpoints(graph)
    if prior:
        old_run = str(uuid4())
        invoke(graph, old_run, selected(old_run))
        close(adapter, adapter.observe(DOCUMENT, old_run, DATASET))
    run_id = str(uuid4()); view = selected(run_id) if include_view else OMIT
    invoke(graph, run_id, view, fail_start=True)
    observed = adapter.discover(DOCUMENT, DATASET)
    assert observed.record.run_id == run_id and observed.source_config == observed.root_config
    assert observed.memory_view == (view if include_view else None)
    assert len(calls) == int(prior)
    result = close(adapter, observed, status="failed")
    assert result.memory_view == observed.memory_view
    assert result.messages[-1].id == run_id and result.messages[-1].content == ORIGINAL
    assert len(calls) == int(prior)


@pytest.mark.parametrize("field,value", [
    ("format_version", True), ("revision", True), ("revision", -1), ("revision", 0),
    ("dataset_id", str(uuid4())), ("document_id", str(uuid4())), ("run_id", str(uuid4())),
    ("version_id", None), ("version_id", "not-a-version"),
    ("guide_digest", "PRIVATE_MEMORY_MARKER"), ("extra", "PRIVATE_MEMORY_MARKER"),
])
def test_native_saved_invalid_view_is_rejected_before_closure(field, value):
    graph, _ = graph_fixture(pause=False)
    run_id = str(uuid4()); view = selected(run_id)
    view[field] = value
    invoke(graph, run_id, view)
    wrapped = Wrapper(graph)
    with pytest.raises(AiCheckpointError, match="^invalid_checkpoint$") as error:
        AiRunCheckpoints(wrapped).discover(DOCUMENT, DATASET)
    assert not wrapped.updates and error.value.__suppress_context__
    assert "PRIVATE_MEMORY_MARKER" not in str(error.value)


def test_same_run_child_cannot_replace_the_root_selected_version():
    graph, _ = graph_fixture()
    run_id = str(uuid4()); view = selected(run_id)
    invoke(graph, run_id, view)
    adapter = AiRunCheckpoints(graph)
    observed = adapter.observe(DOCUMENT, run_id, DATASET)
    graph.update_state(observed.source_config, {"jd_memory_view": selected(run_id, revision=4)}, as_node="model")
    with pytest.raises(AiCheckpointError, match="^invalid_checkpoint$"):
        adapter.observe(DOCUMENT, run_id, DATASET)


def test_closure_ack_cannot_hide_a_different_saved_memory_binding():
    graph, calls = graph_fixture()
    run_id = str(uuid4()); view = selected(run_id)
    invoke(graph, run_id, view)
    class WrongMemory(Wrapper):
        def update_state(self, config, values, **kwargs):
            return super().update_state(config,
                {**values, "jd_memory_view": selected(run_id, revision=4)}, **kwargs)
    wrapped = WrongMemory(graph); adapter = AiRunCheckpoints(wrapped)
    observed = adapter.observe(DOCUMENT, run_id, DATASET)
    with pytest.raises(AiCheckpointError, match="^closure_unconfirmed$"):
        close(adapter, observed, status="failed")
    assert len(wrapped.updates) == 1 and calls == [run_id]
    assert adapter.observe(DOCUMENT, run_id, DATASET).memory_view != view


def test_memory_view_without_an_ai_run_is_not_empty_history():
    graph, calls = graph_fixture(pause=False)
    graph.update_state(config(), {"jd_memory_view": selected(str(uuid4()))}, as_node="consultant")
    with pytest.raises(AiCheckpointError, match="^invalid_checkpoint$"):
        AiRunCheckpoints(graph).discover(DOCUMENT, DATASET)
    assert calls == []


def test_legacy_completed_and_child_records_remain_readable_without_memory_view():
    for pause in (False, True):
        graph, calls = graph_fixture(pause=pause)
        run_id = str(uuid4())
        invoke(graph, run_id)
        adapter = AiRunCheckpoints(graph)
        observed = adapter.observe(DOCUMENT, run_id, DATASET)
        assert observed.memory_view is None
        result = close(adapter, observed, status="failed")
        assert result.memory_view is None and calls == [run_id]
