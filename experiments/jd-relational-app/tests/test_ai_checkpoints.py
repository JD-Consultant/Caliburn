"""Native InMemory root/child closure; no DB, provider or writer/death proof."""

from copy import deepcopy
from hashlib import sha256
import json
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.types import interrupt

from jd_relational.ai_checkpoints import (
    AiCheckpointError, AiRunCheckpoints, AiRunRecordV2, new_run_record, parse_run_record,
)


DATASET, DOCUMENT, RUN = (str(uuid4()) for _ in range(3))
REVISION = str(uuid4())
TEXT = "原話\r\n  每月處理異常。"


class State(MessagesState):
    interview_working_state: dict | None
    jd_ai_run: dict | None
    jd_ai_bindings: list
    jd_ai_read: dict | None
    jd_model_view: dict | None


def config():
    return {"configurable": {"thread_id": DOCUMENT}}


def legacy_run(dataset, document, run, text):
    # Original format is constructed explicitly, never through the V2 builder.
    canonical = json.dumps({"dataset_id": dataset, "document_id": document, "text": text},
                           ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    value = {"format_version": 1, "dataset_id": dataset, "document_id": document,
        "run_id": run, "status": "running", "request_digest": sha256(canonical.encode()).hexdigest()}
    return parse_run_record(value), HumanMessage(id=run, content=text)


def native(*, paused=False, malformed_view=False, saver=None, root_failure=None, record_format=2,
           working_state=None):
    calls = []

    def model(state):
        calls.append("model")
        reply = AIMessage(id="synthetic-ai", content="合成完整回覆",
            response_metadata={"stop_reason": "tool_use"},
            tool_calls=[{"id": "synthetic-call", "name": "synthetic", "args": {}, "type": "tool_call"}])
        notice = '{"current_revision_number":1,"type":"jd_change_notice"}'
        canonical = json.dumps(reply.model_dump(mode="json"), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        view = {"format_version": 1, "dataset_id": DATASET, "document_id": DOCUMENT,
            "run_id": RUN, "revision_id": str(uuid4()), "revision_number": 1,
            "response_message_id": reply.id,
            "response_digest": "0" * 64 if malformed_view else sha256(canonical.encode()).hexdigest(),
            "notice_json": notice, "notice_digest": sha256(notice.encode()).hexdigest()}
        result = {"messages": [reply], "jd_model_view": view,
                "jd_ai_bindings": [{"original": "opaque-test-binding"}],
                "jd_ai_read": {"original": "opaque-test-read"}}
        if working_state is not None:
            result["interview_working_state"] = deepcopy(working_state)
        return result

    def ending(state):
        if paused:
            interrupt("synthetic paused tool")
        return {}

    child = StateGraph(State)
    child.add_node("model", model)
    child.add_node("tools", ending)
    child.add_edge(START, "model")
    child.add_edge("model", "tools")
    child.add_edge("tools", END)
    root = StateGraph(State)
    root.add_node("consultant", child.compile())
    root.add_edge(START, "consultant")
    root.add_edge("consultant", END)
    saver = saver or InMemorySaver()
    compiled = root.compile(checkpointer=saver)
    if root_failure:
        original_put = saver.put
        injections = []

        def fail_root(config, checkpoint, metadata, new_versions):
            inject = (not injections and not config["configurable"].get("checkpoint_ns")
                and checkpoint["channel_values"].get("jd_model_view"))
            if inject:
                injections.append(1)
                if root_failure == "before":
                    raise OSError("SyntheticPrivateCheckpointDetail")
            result = original_put(config, checkpoint, metadata, new_versions)
            if inject:
                raise OSError("SyntheticPrivateCheckpointDetail")
            return result

        saver.put = fail_root
    record, human = (legacy_run(DATASET, DOCUMENT, RUN, TEXT) if record_format == 1 else
                    new_run_record(DATASET, DOCUMENT, RUN, TEXT, start_revision_id=REVISION))
    values = {"jd_ai_run": record.model_dump(mode="json"), "messages": [human],
        "jd_ai_bindings": [], "jd_ai_read": None}
    if root_failure:
        with pytest.raises(OSError):
            compiled.invoke(values, config(), durability="sync")
    else:
        compiled.invoke(values, config(), durability="sync")
    return compiled, calls


class Wrapper:
    def __init__(self, graph, mode="normal"):
        self.graph, self.mode, self.updates = graph, mode, []

    def get_state(self, *args, **kwargs):
        return self.graph.get_state(*args, **kwargs)

    @property
    def checkpointer(self):
        return self.graph.checkpointer

    def update_state(self, config, values, **kwargs):
        self.updates.append((deepcopy(config), deepcopy(values), kwargs))
        if self.mode == "before":
            raise OSError("SyntheticPrivateCheckpointDetail")
        result = self.graph.update_state(config, values, **kwargs)
        if self.mode == "after":
            raise OSError("SyntheticPrivateCheckpointDetail")
        return result


def observe(adapter):
    return adapter.observe(DOCUMENT, RUN, DATASET)


def close(adapter, observed, *, status="completed", **changes):
    values = {"messages": observed.messages, "bindings": observed.bindings,
              "model_view": observed.model_view, "read_binding": observed.read_binding}
    values.update(changes)
    return adapter.close(observed, status=status, **values)


def test_new_run_keeps_exact_human_and_canonical_digest():
    record, human = new_run_record(DATASET, DOCUMENT, RUN, TEXT, start_revision_id=REVISION)
    assert isinstance(record, AiRunRecordV2)
    assert human.id == RUN and human.content == TEXT
    canonical = json.dumps({"format_version": 2, "dataset_id": DATASET, "document_id": DOCUMENT,
                           "text": TEXT, "start_revision_id": REVISION},
        ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    assert record.request_digest == sha256(canonical.encode()).hexdigest()
    assert record.status == "running"
    assert new_run_record(DATASET, DOCUMENT, str(uuid4()), TEXT,
                          start_revision_id=REVISION)[0].request_digest == record.request_digest


@pytest.mark.parametrize("text", ["", " \n", "x\0y", "\ud800", "文" * 50000, None],
    ids=["empty", "blank", "nul", "surrogate", "oversized", "none"])
def test_bad_human_input_rejected(text):
    with pytest.raises(AiCheckpointError, match="^invalid_input$"):
        new_run_record(DATASET, DOCUMENT, RUN, text, start_revision_id=REVISION)


@pytest.mark.parametrize("field,value", [("format_version", True), ("status", "unknown"),
    ("dataset_id", "not-uuid"), ("request_digest", "0" * 63), ("extra", "x")])
def test_record_is_strict(field, value):
    data = new_run_record(DATASET, DOCUMENT, RUN, TEXT, start_revision_id=REVISION)[0].model_dump()
    data[field] = value
    with pytest.raises(ValueError):
        parse_run_record(data)


def test_observe_complete_root_and_explicit_close_keep_original_messages():
    graph, calls = native()
    wrapped = Wrapper(graph)
    adapter = AiRunCheckpoints(wrapped)
    before = observe(adapter)
    assert before.source_config == before.root_config
    assert before.record.status == "running"
    original = [m.model_dump() for m in before.messages]
    result = close(adapter, before)
    assert result.record.status == "completed" and result.closed
    assert [m.model_dump() for m in result.messages] == original
    assert result.bindings == before.bindings and calls == ["model"]
    assert len(wrapped.updates) == 1 and wrapped.updates[0][2] == {"as_node": "consultant"}
    assert close(adapter, result).record.status == "completed"
    assert len(wrapped.updates) == 1


@pytest.mark.parametrize("mode", ["normal", "after"])
def test_stopped_child_can_explicitly_close_root_with_verified_tool_message(mode):
    graph, calls = native(paused=True)
    wrapped = Wrapper(graph, mode)
    adapter = AiRunCheckpoints(wrapped)
    before = observe(adapter)
    assert before.source_config != before.root_config and not before.closed
    assert before.model_view and before.bindings
    extra = ToolMessage(content="synthetic confirmed original result", tool_call_id="synthetic-call")
    result = close(adapter, before, status="cancelled", messages=[*before.messages, extra])
    assert result.record.status == "cancelled" and result.closed
    assert [m.type for m in result.messages] == ["human", "ai", "tool"]
    assert result.messages[0].content == TEXT and result.messages[-1].id
    assert result.model_view == before.model_view and result.bindings == before.bindings
    assert calls == ["model"] and len(wrapped.updates) == 1


def test_stopped_child_closure_copies_its_verified_working_state_to_the_root():
    working = {
        "format_version": 1,
        "focus_item_id": "wi_" + "1" * 32,
        "items": [{
            "item_id": "wi_" + "1" * 32,
            "subject": "故障升級",
            "known_and_open": "升級條件仍待確認。",
            "why_it_matters": None,
            "information_needed": "取得一次實際案例。",
            "status": "open",
            "priority": "normal",
            "source_refs": [],
            "related_refs": [],
        }],
    }
    graph, _ = native(paused=True, working_state=working)
    adapter = AiRunCheckpoints(graph)
    before = observe(adapter)
    assert before.working_state == working and before.source_config != before.root_config
    extra = ToolMessage(content="synthetic confirmed original result", tool_call_id="synthetic-call")
    result = close(adapter, before, status="cancelled", messages=[*before.messages, extra])
    assert result.closed and result.working_state == working
    assert graph.get_state(config()).values["interview_working_state"] == working


def test_failed_update_does_not_retry_or_claim_closed():
    graph, _ = native(paused=True)
    wrapped = Wrapper(graph, "before")
    adapter = AiRunCheckpoints(wrapped)
    with pytest.raises(AiCheckpointError, match="^closure_unconfirmed$") as error:
        close(adapter, observe(adapter), status="failed")
    assert error.value.__suppress_context__ and len(wrapped.updates) == 1
    assert observe(adapter).record.status == "running"


def test_same_run_root_position_drift_rejected_before_update():
    graph, _ = native()
    wrapped = Wrapper(graph)
    adapter = AiRunCheckpoints(wrapped)
    before = observe(adapter)
    graph.update_state(config(), {"jd_ai_read": {"new": "value"}}, as_node="consultant")
    with pytest.raises(AiCheckpointError, match="^checkpoint_changed$"):
        close(adapter, before)
    assert not wrapped.updates


@pytest.mark.parametrize("change", ["human", "bindings", "read", "view", "append_ai", "unknown_tool"])
def test_close_cannot_rewrite_observed_evidence(change):
    graph, _ = native(paused=True)
    adapter = AiRunCheckpoints(graph)
    before = observe(adapter)
    changes = {}
    if change == "human":
        messages = before.messages
        messages[0].content = "silently changed"
        changes["messages"] = messages
    elif change == "bindings": changes["bindings"] = []
    elif change == "read": changes["read_binding"] = None
    elif change == "view": changes["model_view"] = None
    elif change == "append_ai": changes["messages"] = [*before.messages, AIMessage(content="invented")]
    else: changes["messages"] = [*before.messages, ToolMessage(content="invented", tool_call_id="unknown")]
    with pytest.raises(AiCheckpointError, match="^invalid_closure$"):
        close(adapter, before, **changes)


def test_mismatched_child_view_pair_is_rejected():
    graph, _ = native(paused=True, malformed_view=True)
    with pytest.raises(AiCheckpointError, match="^invalid_checkpoint$"):
        observe(AiRunCheckpoints(graph))


def test_no_run_is_not_found_and_no_new_state_is_created():
    graph, _ = native()
    adapter = AiRunCheckpoints(graph)
    with pytest.raises(AiCheckpointError, match="^run_not_found$"):
        adapter.observe(str(uuid4()), RUN, DATASET)
    with pytest.raises(AiCheckpointError, match="^run_not_found$"):
        adapter.observe(DOCUMENT, str(uuid4()), DATASET)


def test_cross_dataset_is_rejected():
    graph, _ = native()
    with pytest.raises(AiCheckpointError, match="^invalid_checkpoint$"):
        AiRunCheckpoints(graph).observe(DOCUMENT, RUN, str(uuid4()))


def test_observation_properties_are_detached():
    graph, _ = native(paused=True)
    before = observe(AiRunCheckpoints(graph))
    before.messages[0].content = "caller changed copy"
    before.bindings.clear()
    before.root_config["configurable"]["thread_id"] = "changed"
    assert before.messages[0].content == TEXT and before.bindings
    assert before.root_config["configurable"]["thread_id"] == DOCUMENT


def test_observation_repr_does_not_include_original_text_or_opaque_payload():
    graph, _ = native(paused=True)
    before = observe(AiRunCheckpoints(graph))
    assert TEXT not in repr(before) and "opaque-test" not in repr(before)


def test_previous_run_model_view_remains_valid_without_new_model_reply():
    graph, _ = native()
    old = observe(AiRunCheckpoints(graph))
    new_run = str(uuid4())
    record, human = new_run_record(DATASET, DOCUMENT, new_run, "新的原話，尚未回覆", start_revision_id=REVISION)
    graph.update_state(config(), {"jd_ai_run": record.model_dump(mode="json"),
        "messages": [human], "jd_ai_bindings": [], "jd_ai_read": None}, as_node="consultant")
    adapter = AiRunCheckpoints(graph)
    before = adapter.observe(DOCUMENT, new_run, DATASET)
    assert before.model_view == old.model_view and before.model_view["run_id"] == RUN
    result = close(adapter, before, status="failed")
    assert result.record.run_id == new_run and result.model_view == old.model_view
    assert result.messages[-1].id == new_run


def test_child_initial_checkpoint_failure_observes_only_fixed_root():
    saver = InMemorySaver()
    original_put = saver.put

    def fail_child(config, checkpoint, metadata, new_versions):
        if config["configurable"].get("checkpoint_ns", "").startswith("consultant:"):
            raise OSError("SyntheticPrivateCheckpointDetail")
        return original_put(config, checkpoint, metadata, new_versions)

    saver.put = fail_child
    child = StateGraph(State)
    child.add_node("model", lambda state: pytest.fail("model must not execute"))
    child.add_edge(START, "model")
    child.add_edge("model", END)
    root = StateGraph(State)
    root.add_node("consultant", child.compile())
    root.add_edge(START, "consultant")
    root.add_edge("consultant", END)
    graph = root.compile(checkpointer=saver)
    record, human = new_run_record(DATASET, DOCUMENT, RUN, TEXT, start_revision_id=REVISION)
    with pytest.raises(OSError):
        graph.invoke({"jd_ai_run": record.model_dump(mode="json"), "messages": [human],
            "jd_ai_bindings": [], "jd_ai_read": None}, config(), durability="sync")
    wrapped = Wrapper(graph)
    adapter = AiRunCheckpoints(wrapped)
    before = observe(adapter)
    assert before.source_config == before.root_config and not before.closed
    assert before.model_view is None and before.bindings == []
    result = close(adapter, before, status="failed")
    assert result.closed and result.messages[0].content == TEXT and len(wrapped.updates) == 1


def test_same_run_child_position_drift_is_rejected():
    graph, _ = native(paused=True)
    wrapped = Wrapper(graph)
    adapter = AiRunCheckpoints(wrapped)
    before = observe(adapter)
    graph.update_state(before.source_config, {"jd_ai_read": {"new": "child"}}, as_node="model")
    with pytest.raises(AiCheckpointError, match="^checkpoint_changed$"):
        close(adapter, before)
    assert not wrapped.updates


@pytest.mark.parametrize("change", ["values", "next"])
def test_unknown_root_structure_does_not_masquerade_as_absence(change):
    graph, _ = native(paused=True)

    class Malformed(Wrapper):
        def get_state(self, config, **kwargs):
            state = super().get_state(config, **kwargs)
            if config.get("configurable", {}).get("checkpoint_id") and not config["configurable"].get("checkpoint_ns"):
                return state._replace(**({"values": ["malformed"]} if change == "values" else {"next": ("unknown",)}))
            return state

    with pytest.raises(AiCheckpointError, match="^invalid_checkpoint$"):
        observe(AiRunCheckpoints(Malformed(graph)))


def test_observer_driver_error_is_fixed_and_has_no_visible_cause():
    class Unavailable:
        def get_state(self, *args, **kwargs):
            raise OSError("SyntheticPrivateCheckpointDetail")

    with pytest.raises(AiCheckpointError, match="^checkpoint_unavailable$") as error:
        observe(AiRunCheckpoints(Unavailable()))
    assert error.value.__suppress_context__ and "Private" not in repr(error.value)


@pytest.mark.parametrize("failure", ["before", "after"])
def test_fixed_root_does_not_mistake_pending_writes_for_closed_checkpoint(failure):
    graph, calls = native(root_failure=failure)
    latest = graph.get_state(config(), subgraphs=True)
    pinned = graph.get_state(latest.config, subgraphs=True)
    assert latest.values.get("jd_model_view")
    assert bool(pinned.values.get("jd_model_view")) == (failure == "after")
    wrapped = Wrapper(graph)
    adapter = AiRunCheckpoints(wrapped)
    before = observe(adapter)
    assert before.closed == (failure == "after")
    assert (before.source_config == before.root_config) == (failure == "after")
    assert before.model_view and before.bindings
    result = close(adapter, before, status="failed")
    assert result.closed and result.record.status == "failed"
    assert len(result.messages) == 2 and result.model_view == before.model_view
    assert calls == ["model"] and len(wrapped.updates) == 1


def initial_input_failure(*, prior=False, record_format=2, prior_format=2):
    if prior:
        graph, calls = native(record_format=prior_format)
        close(AiRunCheckpoints(graph), observe(AiRunCheckpoints(graph)))
    else:
        calls = []
        child = StateGraph(State)
        def unexpected(state):
            calls.append("model")
            return {}
        child.add_node("model", unexpected)
        child.add_edge(START, "model"); child.add_edge("model", END)
        root = StateGraph(State)
        root.add_node("consultant", child.compile())
        root.add_edge(START, "consultant"); root.add_edge("consultant", END)
        graph = root.compile(checkpointer=InMemorySaver())
    before = graph.get_state(config(), subgraphs=True)
    record, human = (legacy_run(DATASET, DOCUMENT, str(uuid4()), "新回合原話\r\n完整保留") if record_format == 1 else
        new_run_record(DATASET, DOCUMENT, str(uuid4()), "新回合原話\r\n完整保留", start_revision_id=REVISION))
    original_put = graph.checkpointer.put
    def fail_loop(config, checkpoint, metadata, new_versions):
        if not config["configurable"].get("checkpoint_ns") and metadata["source"] == "loop":
            raise OSError("synthetic initial loop failure")
        return original_put(config, checkpoint, metadata, new_versions)
    graph.checkpointer.put = fail_loop
    try:
        with pytest.raises(OSError):
            graph.invoke({"jd_ai_run": record.model_dump(), "messages": [human],
                "jd_ai_bindings": [], "jd_ai_read": None}, config(), durability="sync")
    finally:
        graph.checkpointer.put = original_put
    assert len(calls) == int(prior)
    return graph, calls, record, human, before


@pytest.mark.parametrize("prior", [False, True])
@pytest.mark.parametrize("ack", ["normal", "after"])
def test_native_start_input_is_observed_and_closed_without_replay(prior, ack):
    graph, calls, record, human, previous = initial_input_failure(prior=prior)
    latest = graph.get_state(config(), subgraphs=True)
    fixed = graph.get_state(latest.config, subgraphs=True)
    assert fixed.next == (START,) and fixed.metadata["source"] == "input"
    assert human not in fixed.values.get("messages", [])
    wrapped = Wrapper(graph, ack)
    adapter = AiRunCheckpoints(wrapped)
    seen = adapter.observe(DOCUMENT, record.run_id, DATASET)
    assert seen.record == record and not seen.closed
    assert seen.messages == [*previous.values.get("messages", []), human]
    assert seen.bindings == [] and seen.read_binding is None
    assert seen.model_view == previous.values.get("jd_model_view")
    result = close(adapter, seen, status="failed")
    assert result.closed and result.record.status == "failed"
    assert result.messages == seen.messages and result.model_view == seen.model_view
    assert len(calls) == int(prior) and len(wrapped.updates) == 1


@pytest.mark.parametrize("fault", ["extra", "missing", "run", "document", "dataset", "digest",
    "human_id", "two_humans", "bindings", "read", "status", "config"])
def test_native_start_payload_must_match_exact_original_input(fault):
    graph, _, record, _, _ = initial_input_failure()
    class BadSaver:
        def get_tuple(self, config):
            saved = deepcopy(graph.checkpointer.get_tuple(config))
            payload = saved.checkpoint["channel_values"][START]
            if fault == "extra": payload["jd_model_view"] = None
            elif fault == "missing": del payload["jd_ai_read"]
            elif fault in {"run", "document", "dataset"}:
                payload["jd_ai_run"][f"{fault}_id"] = str(uuid4())
            elif fault == "digest": payload["jd_ai_run"]["request_digest"] = "0" * 64
            elif fault == "human_id": payload["messages"][0].id = str(uuid4())
            elif fault == "two_humans": payload["messages"].append(HumanMessage(id=str(uuid4()), content="extra"))
            elif fault == "bindings": payload["jd_ai_bindings"] = [{"unexpected": "binding"}]
            elif fault == "read": payload["jd_ai_read"] = {}
            elif fault == "status": payload["jd_ai_run"]["status"] = "completed"
            elif fault == "config": saved.config["configurable"]["thread_id"] = str(uuid4())
            return saved
    class BadInput(Wrapper):
        @property
        def checkpointer(self): return BadSaver()
    with pytest.raises(AiCheckpointError, match="^invalid_checkpoint$"):
        AiRunCheckpoints(BadInput(graph)).observe(DOCUMENT, record.run_id, DATASET)


@pytest.mark.parametrize("paused", [False, True])
def test_legacy_root_and_child_close_without_rewriting_record_version(paused):
    graph, calls = native(paused=paused, record_format=1)
    adapter = AiRunCheckpoints(graph)
    seen = observe(adapter)
    original = seen.record.model_dump(mode="json")
    assert original["format_version"] == 1 and "start_revision_id" not in original
    assert seen.record == legacy_run(DATASET, DOCUMENT, RUN, TEXT)[0]
    result = close(adapter, seen, status="failed")
    assert result.record.model_dump(mode="json") == {**original, "status": "failed"}
    assert result.messages == seen.messages and result.bindings == seen.bindings
    assert result.model_view == seen.model_view and result.read_binding == seen.read_binding
    assert calls == ["model"]


@pytest.mark.parametrize("prior,prior_format,record_format", [
    (False, 1, 1), (True, 1, 1), (True, 1, 2), (True, 2, 2),
])
def test_saved_start_preserves_actual_format_and_mixed_prior_history(prior, prior_format, record_format):
    graph, calls, record, human, previous = initial_input_failure(
        prior=prior, prior_format=prior_format, record_format=record_format)
    adapter = AiRunCheckpoints(graph)
    seen = adapter.observe(DOCUMENT, record.run_id, DATASET)
    assert seen.record.format_version == record_format and seen.messages[-1] == human
    if prior:
        assert previous.values["jd_ai_run"]["format_version"] == prior_format
        assert seen.messages[:-1] == previous.values["messages"]
    exact = adapter.observe_at(DOCUMENT, record.run_id, DATASET, seen.root_config)
    assert exact == seen
    closed = close(adapter, exact, status="failed")
    assert closed.record.model_dump(mode="json") == {**record.model_dump(mode="json"), "status": "failed"}
    assert closed.messages == seen.messages and len(calls) == int(prior)


def test_observe_at_keeps_original_root_after_a_new_start_exists():
    graph, _, new_record, _, previous = initial_input_failure(prior=True, prior_format=1)
    class FixedOnly(Wrapper):
        def __init__(self, graph): super().__init__(graph); self.locations = []
        def get_state(self, config, **kwargs):
            assert config["configurable"].get("checkpoint_id"), "Do not silently select latest."
            self.locations.append(deepcopy(config))
            return super().get_state(config, **kwargs)
    wrapped = FixedOnly(graph)
    adapter = AiRunCheckpoints(wrapped)
    assert adapter.graph is wrapped
    root = {"configurable": {key: previous.config["configurable"][key]
                             for key in ("thread_id", "checkpoint_ns", "checkpoint_id")}}
    old = adapter.observe_at(DOCUMENT, RUN, DATASET, root)
    assert old.record.run_id == RUN and old.record.format_version == 1 and old.closed
    assert old.messages == previous.values["messages"]
    assert all(m.id != new_record.run_id for m in old.messages)
    assert len(wrapped.locations) == 1
    with pytest.raises(AiCheckpointError, match="^run_not_found$"):
        adapter.observe_at(DOCUMENT, new_record.run_id, DATASET, root)


@pytest.mark.parametrize("change", ["missing", "latest", "document", "child", "blank", "nul", "type", "extra"])
def test_observe_at_requires_a_fixed_same_document_root_before_io(change):
    class NeverRead:
        def get_state(self, *_args, **_kwargs):
            raise AssertionError("invalid_input_must_not_touch_saver")
    root = {"configurable": {"thread_id": DOCUMENT, "checkpoint_ns": "", "checkpoint_id": "known-checkpoint"}}
    if change == "missing": root = None
    elif change == "latest": del root["configurable"]["checkpoint_id"]
    elif change == "document": root["configurable"]["thread_id"] = str(uuid4())
    elif change == "child": root["configurable"]["checkpoint_ns"] = "consultant:some-task"
    elif change == "blank": root["configurable"]["checkpoint_id"] = " "
    elif change == "nul": root["configurable"]["checkpoint_id"] = "bad\0id"
    elif change == "type": root["configurable"]["checkpoint_id"] = 1
    elif change == "extra": root["unexpected"] = True
    with pytest.raises(AiCheckpointError, match="^invalid_input$"):
        AiRunCheckpoints(NeverRead()).observe_at(DOCUMENT, RUN, DATASET, root)


@pytest.mark.parametrize("fault", ["revision", "version"])
def test_v2_saved_request_digest_cannot_be_reinterpreted_as_another_request(fault):
    graph, _ = native(paused=True)
    class Changed(Wrapper):
        def get_state(self, config, **kwargs):
            state = super().get_state(config, **kwargs)
            if state.values.get("jd_ai_run") is not None:
                values = deepcopy(state.values)
                if fault == "revision": values["jd_ai_run"]["start_revision_id"] = str(uuid4())
                else:
                    values["jd_ai_run"]["format_version"] = 1
                    del values["jd_ai_run"]["start_revision_id"]
                state = state._replace(values=values)
            return state
    with pytest.raises(AiCheckpointError, match="^invalid_checkpoint$"):
        observe(AiRunCheckpoints(Changed(graph)))


@pytest.mark.parametrize("version", [1, 2])
def test_manual_gate_reads_both_record_formats_and_keeps_busy_until_closed(version):
    from jd_relational.runtime_checkpoints import CheckpointError, DocumentCheckpoints
    graph, _ = native(record_format=version)
    manual = DocumentCheckpoints(graph)
    with pytest.raises(CheckpointError, match="^document_busy$"):
        manual.read(DOCUMENT)
    close(AiRunCheckpoints(graph), observe(AiRunCheckpoints(graph)), status="failed")
    assert manual.read(DOCUMENT) is None


@pytest.mark.parametrize("tag", [True, 1.0, 2.0])
def test_manual_gate_never_accepts_coerced_record_version(tag):
    from jd_relational.runtime_checkpoints import CheckpointError, DocumentCheckpoints
    graph, _ = native()
    close(AiRunCheckpoints(graph), observe(AiRunCheckpoints(graph)), status="failed")
    class Invalid(Wrapper):
        def get_state(self, config, **kwargs):
            state = super().get_state(config, **kwargs)
            values = deepcopy(state.values)
            values["jd_ai_run"]["format_version"] = tag
            return state._replace(values=values)
    with pytest.raises(CheckpointError, match="^invalid_checkpoint$"):
        DocumentCheckpoints(Invalid(graph)).read(DOCUMENT)
