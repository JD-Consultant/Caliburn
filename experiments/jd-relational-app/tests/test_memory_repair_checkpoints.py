"""Native static C checkpoint observation/closure; no DB, provider or stop proof."""
from copy import deepcopy
from dataclasses import replace
from typing import TypedDict
from uuid import uuid4

from langchain_core.messages import AIMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.types import Command, interrupt
import pytest

from jd_relational.ai_checkpoints import AiCheckpointError, AiRunCheckpoints, new_run_record
from test_ai_checkpoints import Wrapper, close


DATASET, DOCUMENT = str(uuid4()), str(uuid4())
TEXT = "合成原話\r\n  主管更正為處長。"
OMIT = object()


class RootState(MessagesState):
    jd_ai_run: dict | None
    jd_ai_bindings: list
    jd_ai_read: dict | None
    jd_model_view: dict | None
    jd_memory_view: dict | None
    jd_memory_repair_bindings: list


class CState(TypedDict):
    operation_id: str
    request: dict
    files: dict


def config():
    return {"configurable": {"thread_id": DOCUMENT}}


def binding():
    # Deliberately opaque to this adapter; the App session owns semantic checks.
    return {"operation_id": str(uuid4()), "tool_call_id": "synthetic-c-call",
        "source": "synthetic-source", "input_digest": "a" * 64}


def native(*, pause=True, handoff=True, saver=None):
    calls = []
    original = binding()
    def model(state):
        calls.append("model")
        return {"messages": [AIMessage(id=str(uuid4()), content="", tool_calls=[{
            "name": "repair_memory", "id": "synthetic-c-call", "args": {}, "type": "tool_call"}])],
            "jd_memory_repair_bindings": [original]}
    def tools(state):
        calls.append("tool")
        if not handoff:
            interrupt("synthetic_consultant_pending")
        return Command(graph=Command.PARENT, goto="memory_repair", update={
            "messages": state["messages"], "jd_memory_repair_bindings": state["jd_memory_repair_bindings"]})
    child = StateGraph(RootState)
    child.add_node("model", model); child.add_node("tools", tools)
    child.add_edge(START, "model"); child.add_edge("model", "tools"); child.add_edge("tools", END)
    def prepare(state):
        calls.append("prepare")
        return {"request": {"operation_id": state["operation_id"], "opaque": "original-request"},
            "files": {"/memory/knowledge.md": {"content": ["合成暫存正文"]}}}
    def publish(state):
        calls.append("publish")
        if pause:
            interrupt("synthetic_after_saved_prepare")
        return {}
    c = StateGraph(CState)
    c.add_node("prepare", prepare); c.add_node("publish", publish)
    c.add_edge(START, "prepare"); c.add_edge("prepare", "publish"); c.add_edge("publish", END)
    repair_graph = c.compile()
    def repair(state):
        result = repair_graph.invoke({"operation_id": state["jd_memory_repair_bindings"][-1]["operation_id"]},
            durability="sync")
        return {"messages": [ToolMessage(id=str(uuid4()), tool_call_id="synthetic-c-call",
            name="repair_memory", content="synthetic_result", artifact={"request": result["request"]})]}
    root = StateGraph(RootState)
    root.add_node("consultant", child.compile()); root.add_node("memory_repair", repair)
    root.add_edge(START, "consultant"); root.add_edge("consultant", END); root.add_edge("memory_repair", END)
    return root.compile(checkpointer=saver or InMemorySaver()), calls, original


def invoke(graph, *, repairs=OMIT, fail_start=False):
    run = str(uuid4())
    record, human = new_run_record(DATASET, DOCUMENT, run, TEXT, start_revision_id=str(uuid4()))
    payload = {"jd_ai_run": record.model_dump(mode="json"), "messages": [human],
        "jd_ai_bindings": [], "jd_ai_read": None}
    if repairs is not OMIT:
        payload["jd_memory_repair_bindings"] = deepcopy(repairs)
    if not fail_start:
        graph.invoke(payload, config(), durability="sync")
        return run
    original_put = graph.checkpointer.put
    failures = []
    def fail_loop(cfg, checkpoint, metadata, versions):
        if not cfg["configurable"].get("checkpoint_ns") and metadata["source"] == "loop":
            failures.append(True)
            raise OSError("synthetic_failed_initial_loop")
        return original_put(cfg, checkpoint, metadata, versions)
    graph.checkpointer.put = fail_loop
    try:
        with pytest.raises(OSError, match="synthetic_failed_initial_loop"):
            graph.invoke(payload, config(), durability="sync")
    finally:
        graph.checkpointer.put = original_put
    assert failures
    return run


@pytest.mark.parametrize("ack", ["normal", "after"])
def test_native_c_pending_fixed_request_and_opaque_bindings_survive_close(ack):
    graph, calls, original = native()
    run = invoke(graph, repairs=[])
    wrapped = Wrapper(graph, ack); adapter = AiRunCheckpoints(wrapped)
    observed = adapter.discover(DOCUMENT, DATASET)
    assert observed.record.run_id == run and not observed.closed
    assert observed.source_config == observed.root_config
    assert observed.repair_bindings == [original]
    checkpoint = observed.repair_checkpoint
    assert checkpoint["next"] == ["publish"]
    assert checkpoint["values"]["request"]["operation_id"] == original["operation_id"]
    assert set(checkpoint["config"]["configurable"]) == {"thread_id", "checkpoint_ns", "checkpoint_id"}
    assert "files" not in graph.get_state(config()).values
    checkpoint["values"]["request"]["opaque"] = "mutated"
    observed.repair_bindings[0]["source"] = "mutated"
    assert observed.repair_checkpoint["values"]["request"]["opaque"] == "original-request"
    assert observed.repair_bindings == [original]
    before = list(calls)
    result = close(adapter, observed, status="failed", messages=[*observed.messages,
        ToolMessage(id=str(uuid4()), tool_call_id="synthetic-c-call", content="synthetic_stopped_result")])
    assert result.closed and result.repair_checkpoint is None and result.repair_bindings == [original]
    assert result.messages[0].content == TEXT and result.messages[0].id == run
    assert calls == before and len(wrapped.updates) == 1
    assert wrapped.updates[0][1]["jd_memory_repair_bindings"] == [original]
    assert AiRunCheckpoints(graph).observe(DOCUMENT, run, DATASET).repair_bindings == [original]


def test_root_source_lookup_does_not_load_c_checkpoint():
    graph, calls, _ = native()
    run = invoke(graph)
    adapter = AiRunCheckpoints(graph)
    observed = adapter.observe(DOCUMENT, run, DATASET)
    class SourceOnly(Wrapper):
        def get_state(self, cfg, *, subgraphs=True):
            assert cfg["configurable"].get("checkpoint_ns", "") == ""
            assert subgraphs is False
            return super().get_state(cfg, subgraphs=False)
    before = list(calls)
    fixed = AiRunCheckpoints(SourceOnly(graph)).observe_at(DOCUMENT, run, DATASET,
        observed.root_config, source_config=observed.root_config)
    assert fixed.source_config == observed.root_config and fixed.repair_checkpoint is None
    assert fixed.messages == observed.messages and fixed.repair_bindings == observed.repair_bindings
    assert calls == before


@pytest.mark.parametrize("prior", [False, True])
@pytest.mark.parametrize("include", [False, True])
def test_saved_start_resets_legacy_repair_bindings_and_accepts_only_new_empty_list(prior, include):
    graph, calls, original = native(pause=False)
    adapter = AiRunCheckpoints(graph)
    if prior:
        old = invoke(graph, repairs=[])
        prior_observed = adapter.observe(DOCUMENT, old, DATASET)
        assert prior_observed.repair_bindings == [original]
        close(adapter, prior_observed)
    before = list(calls)
    run = invoke(graph, repairs=[] if include else OMIT, fail_start=True)
    observed = adapter.discover(DOCUMENT, DATASET)
    assert observed.record.run_id == run and observed.repair_bindings == []
    assert observed.repair_checkpoint is None and calls == before
    assert close(adapter, observed, status="failed").repair_bindings == []


@pytest.mark.parametrize("value", [None, {}, [binding()], "PRIVATE_REPAIR_MARKER"])
def test_saved_start_rejects_nonempty_or_malformed_new_binding(value):
    graph, _, _ = native()
    invoke(graph, repairs=value, fail_start=True)
    with pytest.raises(AiCheckpointError, match="^invalid_checkpoint$") as error:
        AiRunCheckpoints(graph).discover(DOCUMENT, DATASET)
    assert "PRIVATE_REPAIR_MARKER" not in str(error.value)


def test_consultant_fixed_child_keeps_repair_bindings_without_c_material():
    graph, _, original = native(handoff=False)
    run = invoke(graph, repairs=[])
    observed = AiRunCheckpoints(graph).observe(DOCUMENT, run, DATASET)
    assert observed.source_config != observed.root_config and observed.repair_bindings == [original]
    assert observed.repair_checkpoint is None


def test_old_observation_fields_keep_default_repair_material():
    from test_ai_checkpoints import native as old_native, DOCUMENT as OLD_DOC, DATASET as OLD_DATASET, RUN
    graph, _ = old_native()
    observed = AiRunCheckpoints(graph).observe(OLD_DOC, RUN, OLD_DATASET)
    assert observed.repair_bindings == [] and observed.repair_checkpoint is None


def test_close_ack_cannot_hide_a_different_saved_repair_binding():
    graph, _, _ = native()
    run = invoke(graph)
    class WrongBinding(Wrapper):
        def update_state(self, cfg, values, **kwargs):
            return super().update_state(cfg, {**values, "jd_memory_repair_bindings": []}, **kwargs)
    wrapped = WrongBinding(graph); adapter = AiRunCheckpoints(wrapped)
    observed = adapter.observe(DOCUMENT, run, DATASET)
    with pytest.raises(AiCheckpointError, match="^closure_unconfirmed$"):
        close(adapter, observed, status="failed")
    assert len(wrapped.updates) == 1


@pytest.mark.parametrize("change", ["task_name", "task_count", "child_scope", "nested_task", "unknown_next", "nonjson_values"])
def test_unknown_c_task_shapes_never_become_observed_request(change):
    graph, _, _ = native()
    run = invoke(graph)
    class Damaged(Wrapper):
        def get_state(self, cfg, *, subgraphs=True):
            value = super().get_state(cfg, subgraphs=subgraphs)
            ns = cfg["configurable"].get("checkpoint_ns", "")
            if ns == "" and value.tasks and subgraphs:
                task = value.tasks[0]
                if change == "task_name":
                    return value._replace(tasks=(task._replace(name="unknown_node"),))
                if change == "task_count":
                    return value._replace(tasks=(task, task))
                if change == "child_scope":
                    config2 = deepcopy(task.state.config)
                    config2["configurable"]["thread_id"] = str(uuid4())
                    return value._replace(tasks=(task._replace(state=task.state._replace(config=config2)),))
            if ns.startswith("memory_repair:"):
                if change == "nested_task":
                    return value._replace(tasks=(value.tasks[0]._replace(state={"PRIVATE_REPAIR_MARKER": True}),))
                if change == "unknown_next":
                    return value._replace(next=("unknown_step",))
                if change == "nonjson_values":
                    return value._replace(values={"bad": object()})
            return value
    with pytest.raises(AiCheckpointError, match="^invalid_checkpoint$") as error:
        AiRunCheckpoints(Damaged(graph)).observe(DOCUMENT, run, DATASET)
    assert "PRIVATE_REPAIR_MARKER" not in str(error.value)


def test_c_read_failure_is_safely_unavailable_not_invalid_input():
    graph, _, _ = native(); run = invoke(graph)
    class Unavailable(Wrapper):
        def get_state(self, cfg, *, subgraphs=True):
            if cfg["configurable"].get("checkpoint_ns", "").startswith("memory_repair:"):
                raise OSError("PRIVATE_REPAIR_MARKER")
            return super().get_state(cfg, subgraphs=subgraphs)
    with pytest.raises(AiCheckpointError, match="^checkpoint_unavailable$") as error:
        AiRunCheckpoints(Unavailable(graph)).observe(DOCUMENT, run, DATASET)
    assert "PRIVATE_REPAIR_MARKER" not in str(error.value) and error.value.__suppress_context__


def test_repair_bindings_without_a_run_are_not_empty_document():
    graph, _, _ = native()
    graph.update_state(config(), {"jd_memory_repair_bindings": [binding()]}, as_node="consultant")
    with pytest.raises(AiCheckpointError, match="^invalid_checkpoint$"):
        AiRunCheckpoints(graph).discover(DOCUMENT, DATASET)
