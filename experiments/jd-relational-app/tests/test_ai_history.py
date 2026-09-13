"""Native old-run lookup with InMemorySaver; zero DB/provider/replay."""

from copy import deepcopy
from hashlib import sha256
import json
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from jd_relational.ai_checkpoints import AiCheckpointError, AiRunCheckpoints
from jd_relational.ai_history import AiRunHistory
from jd_relational.intents import AdmittedIdentity
from jd_relational.runtime_checkpoints import DocumentCheckpoints, DocumentState, build_document_graph


def config(document):
    return {"configurable": {"thread_id": document, "checkpoint_ns": ""}}


def original(dataset, document, text):
    # Explicit already-persisted v1 fixture, independent of new v2 admission.
    run = str(uuid4())
    digest = sha256(json.dumps({"dataset_id": dataset, "document_id": document, "text": text},
        ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {"format_version": 1, "dataset_id": dataset, "document_id": document,
        "run_id": run, "request_digest": digest, "status": "running"}, HumanMessage(id=run, content=text)


@pytest.fixture
def native():
    calls, paused = [], set()
    def model(state):
        run = state["jd_ai_run"]["run_id"]
        calls.append(run)
        return {"messages": [AIMessage(id=str(uuid4()), content=[
            {"type": "thinking", "thinking": "合成內容", "signature": "synthetic-signature"},
            {"type": "text", "text": "完整回覆\r\n不重新生成"}])]}
    def hold(state):
        if state["jd_ai_run"]["run_id"] in paused: interrupt("synthetic pause")
        return {}
    child = StateGraph(DocumentState)
    child.add_node("model", model); child.add_node("hold", hold)
    child.add_edge(START, "model"); child.add_edge("model", "hold"); child.add_edge("hold", END)
    graph = build_document_graph(child.compile(), InMemorySaver())
    dataset, document = str(uuid4()), str(uuid4())
    return graph, dataset, document, calls, paused


def append(native, text="原始訪談\r\n  保留😀", *, pause=False):
    graph, dataset, document, _, paused = native
    record, human = original(dataset, document, text)
    if pause: paused.add(record["run_id"])
    graph.invoke({"jd_ai_run": record, "messages": [human], "jd_ai_bindings": [], "jd_ai_read": None},
        config(document), durability="sync")
    checkpoints = AiRunCheckpoints(graph)
    result = checkpoints.discover(document, dataset)
    if not pause:
        result = checkpoints.close(result, status="completed", messages=result.messages,
            bindings=result.bindings, model_view=result.model_view, read_binding=result.read_binding)
    return result


@pytest.mark.parametrize("paused", [False, True])
def test_A_then_B_returns_original_A_without_replay(native, paused):
    graph, dataset, document, calls, _ = native
    a, b = append(native, "A 原話"), append(native, "B 原話", pause=paused)
    history = AiRunHistory(AiRunCheckpoints(graph))
    assert history.find(document, a.record.run_id, dataset) == a
    assert history.find(document, b.record.run_id, dataset) == b
    assert len(calls) == 2


def test_manual_roots_return_latest_valid_same_terminal_without_duplicate_run(native):
    graph, dataset, document, calls, _ = native
    a = append(native)
    manual = AdmittedIdentity(document, uuid4(), uuid4(), "manual", None, "a" * 64, "jd_set_text")
    checkpoints = DocumentCheckpoints(graph)
    checkpoints.admit(manual); checkpoints.close(manual)
    latest_a = AiRunCheckpoints(graph).discover(document, dataset)
    append(native, "B")
    result = AiRunHistory(AiRunCheckpoints(graph)).find(document, a.record.run_id, dataset)
    assert result == latest_a and result.messages == a.messages
    assert len(calls) == 2


def test_same_prefix_side_branch_never_wins_over_effective_ancestor(native):
    graph, dataset, document, _, _ = native
    a, b = append(native, "A"), append(native, "B")
    side = graph.update_state(a.root_config,
        {"jd_ai_run": a.record.model_copy(update={"status": "failed"}).model_dump()}, as_node="consultant")
    active = graph.update_state(b.root_config, {"jd_manual_pending": None}, as_node="consultant")
    wrong = next(row for row in graph.get_state_history(config(document), before=active, limit=16)
        if (row.values.get("jd_ai_run") or {}).get("run_id") == a.record.run_id)
    assert wrong.config["configurable"] == side["configurable"]
    assert wrong.values["messages"] == b.messages[:len(a.messages)]
    found = AiRunHistory(AiRunCheckpoints(graph)).find(document, a.record.run_id, dataset)
    assert found == a and found.record.status == "completed"


@pytest.mark.parametrize("fault", ["input", "loop"])
def test_START_prior_record_and_missing_parent_are_not_guessed(native, fault):
    graph, dataset, document, calls, _ = native
    a = append(native, "A")
    record, human = original(dataset, document, "B 原始START")
    put, failed = graph.checkpointer.put, []
    def failure(conf, checkpoint, metadata, versions):
        if not failed and not conf["configurable"].get("checkpoint_ns") and metadata["source"] == fault:
            failed.append(True); raise OSError("synthetic private fault")
        return put(conf, checkpoint, metadata, versions)
    graph.checkpointer.put = failure
    try:
        with pytest.raises(OSError):
            graph.invoke({"jd_ai_run": record, "messages": [human], "jd_ai_bindings": [], "jd_ai_read": None},
                config(document), durability="sync")
    finally: graph.checkpointer.put = put
    history = AiRunHistory(AiRunCheckpoints(graph))
    current = history.find(document, record["run_id"], dataset)
    assert current.messages == [*a.messages, human] and not current.closed
    if fault == "loop":
        assert graph.get_state(current.root_config).next == (START,)
        assert history.find(document, a.record.run_id, dataset) == a
    else:
        with pytest.raises(AiCheckpointError, match="^original_run_lookup_required$"):
            history.find(document, a.record.run_id, dataset)
    assert len(calls) == 1


def test_none_requires_verified_absence_from_complete_current_message_ids(native):
    graph, dataset, document, calls, _ = native
    history = AiRunHistory(AiRunCheckpoints(graph))
    assert history.find(document, str(uuid4()), dataset) is None
    a = append(native)
    assert history.find(document, str(uuid4()), dataset) is None
    with pytest.raises(AiCheckpointError, match="^original_run_lookup_required$"):
        history.find(document, a.messages[-1].id, dataset)
    assert len(calls) == 1


@pytest.mark.parametrize("field", ["document", "dataset", "run"])
def test_invalid_scope_input_is_fixed(native, field):
    graph, dataset, document, _, _ = native
    a = append(native)
    arguments = {"document_id": document, "dataset_id": dataset, "run_id": a.record.run_id}
    arguments[field + "_id"] = "not-uuid"
    with pytest.raises(AiCheckpointError, match="^invalid_input$"):
        AiRunHistory(AiRunCheckpoints(graph)).find(**arguments)


def test_other_document_does_not_return_A_and_wrong_dataset_is_rejected(native):
    graph, dataset, document, calls, _ = native
    a = append(native)
    history = AiRunHistory(AiRunCheckpoints(graph))
    assert history.find(str(uuid4()), a.record.run_id, dataset) is None
    with pytest.raises(AiCheckpointError, match="^invalid_checkpoint$"):
        history.find(document, a.record.run_id, str(uuid4()))
    assert len(calls) == 1


def test_limit_does_not_masquerade_as_new_request(native, monkeypatch):
    graph, dataset, document, _, _ = native
    a = append(native, "A")
    append(native, "B")
    monkeypatch.setattr("jd_relational.ai_history.MAX_PARENT_LOOKUPS", 1)
    with pytest.raises(AiCheckpointError, match="^original_run_lookup_required$"):
        AiRunHistory(AiRunCheckpoints(graph)).find(document, a.record.run_id, dataset)


@pytest.mark.parametrize("fault", ["cycle", "wrong_parent_document", "wrong_parent_namespace", "missing_parent", "wrong_checkpoint_id"])
def test_parent_tuple_scope_and_cycles_fail_closed(native, monkeypatch, fault):
    graph, dataset, document, _, _ = native
    a = append(native, "A"); b = append(native, "B")
    current = b.root_config["configurable"]["checkpoint_id"]
    original_get = graph.checkpointer.get_tuple
    def altered(conf):
        saved = original_get(conf)
        if conf["configurable"].get("checkpoint_id") == current:
            saved = deepcopy(saved)
            if fault == "cycle": return saved._replace(parent_config=saved.config)
            if fault == "missing_parent": return saved._replace(parent_config=None)
            if fault == "wrong_checkpoint_id": saved.checkpoint["id"] = str(uuid4())
            elif fault == "wrong_parent_document": saved.parent_config["configurable"]["thread_id"] = str(uuid4())
            elif fault == "wrong_parent_namespace": saved.parent_config["configurable"]["checkpoint_ns"] = "other"
        return saved
    monkeypatch.setattr(graph.checkpointer, "get_tuple", altered)
    with pytest.raises(AiCheckpointError) as error:
        AiRunHistory(AiRunCheckpoints(graph)).find(document, a.record.run_id, dataset)
    assert error.value.code in {"original_run_lookup_required", "invalid_checkpoint"}


def test_checkpoint_service_failure_has_no_original_error_details(native, monkeypatch):
    graph, dataset, document, _, _ = native
    a = append(native)
    append(native)
    def broken(*args, **kwargs): raise OSError("synthetic-private-connection-data")
    monkeypatch.setattr(graph.checkpointer, "get_tuple", broken)
    with pytest.raises(AiCheckpointError, match="^checkpoint_unavailable$") as error:
        AiRunHistory(AiRunCheckpoints(graph)).find(document, a.record.run_id, dataset)
    assert error.value.__suppress_context__ and "private" not in repr(error.value)


def test_ancestor_claiming_A_but_containing_later_Human_is_not_original_A(native):
    graph, dataset, document, calls, _ = native
    a = append(native, "A")
    # Native update can write arbitrary app-invalid state. A shorter prefix
    # comparison could accept this later Human as part of A's original reply.
    _, later = original(dataset, document, "B without its own run record")
    graph.update_state(a.root_config, {"messages": [later]}, as_node="consultant")
    append(native, "C")
    with pytest.raises(AiCheckpointError, match="^invalid_checkpoint$"):
        AiRunHistory(AiRunCheckpoints(graph)).find(document, a.record.run_id, dataset)
    assert len(calls) == 2


def test_only_one_latest_read_and_no_global_history_fallback(native, monkeypatch):
    graph, dataset, document, _, _ = native
    a = append(native, "A"); append(native, "B")
    reads, original_get = [], graph.get_state
    def tracked(conf, **kwargs):
        reads.append(deepcopy(conf))
        return original_get(conf, **kwargs)
    def forbidden(*args, **kwargs): raise AssertionError("global history must not select ancestry")
    monkeypatch.setattr(graph, "get_state", tracked)
    monkeypatch.setattr(graph, "get_state_history", forbidden)
    assert AiRunHistory(AiRunCheckpoints(graph)).find(document, a.record.run_id, dataset) == a
    assert sum("checkpoint_id" not in conf["configurable"] for conf in reads) == 1
    assert all(conf["configurable"]["thread_id"] == document for conf in reads)


def test_current_inconsistent_last_Human_cannot_establish_unused_ID(native):
    graph, dataset, document, _, _ = native
    a = append(native, "A")
    _, later = original(dataset, document, "B without matching current run")
    graph.update_state(a.root_config, {"messages": [later]}, as_node="consultant")
    with pytest.raises(AiCheckpointError, match="^invalid_checkpoint$"):
        AiRunHistory(AiRunCheckpoints(graph)).find(document, str(uuid4()), dataset)
