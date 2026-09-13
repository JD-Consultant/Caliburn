"""Native persisted turns and real recovery Futures; SQL/OS are synthetic ports."""

from dataclasses import replace
from threading import Event
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import START, END, StateGraph

from jd_relational.ai_checkpoints import new_run_record
from jd_relational.ai_runtime import AiRuntime, AiRuntimeError
from jd_relational.manual_runtime import ManualRuntime, RuntimeFailure
from jd_relational.runtime_checkpoints import DocumentCheckpoints, DocumentState, build_document_graph, _encode
from test_ai_runtime import SyntheticStorage, _receipt_fixture
from test_startup_recovery import PreviousHost
from test_manual_runtime import intent


class RestartStorage(SyntheticStorage):
    def __init__(self, authority):
        super().__init__(authority)
        self.documents = []

    def document_ids(self, *, after=None, limit=100):
        return tuple(d for d in sorted(self.documents) if after is None or d > after)[:limit]

    def reconcile_stopped(self, identity):
        result = super().reconcile_stopped(identity)
        result = replace(result, receipt=replace(result.receipt, origin=identity.origin, ai_run_id=identity.ai_run_id))
        self.receipts[identity.operation_id] = result
        return result


def saved_turn(*, calls=False, terminal=False, initial=False):
    messages, bindings, receipts, codec = _receipt_fixture()
    binding = bindings[0]
    receipts = {key: replace(value, receipt=replace(value.receipt,
        origin=binding.identity.origin, ai_run_id=binding.identity.ai_run_id))
        for key, value in receipts.items()}
    record, human = new_run_record(codec.dataset_id, binding.identity.document_id,
                                  binding.identity.ai_run_id, "原始訪談\n  不可改寫")
    model_calls = []
    def work(state):
        model_calls.append(1)
        return {"messages": [messages[0]] if calls else [AIMessage(id="saved-response", content="已寫下的回覆")],
                "jd_ai_bindings": [binding.to_dict()] if calls else []}
    child = StateGraph(DocumentState)
    child.add_node("model", work)
    child.add_edge(START, "model"); child.add_edge("model", END)
    saver = InMemorySaver()
    graph = build_document_graph(child.compile(), saver)
    original = saver.put
    if initial:
        def fail_loop(config, checkpoint, metadata, versions):
            if not config["configurable"].get("checkpoint_ns") and metadata.get("source") == "loop":
                raise OSError("synthetic loop checkpoint failure")
            return original(config, checkpoint, metadata, versions)
        saver.put = fail_loop
    try:
        graph.invoke({"messages": [human], "jd_ai_run": record.model_dump(mode="json"),
                      "jd_ai_bindings": [], "jd_ai_read": None},
                     {"configurable": {"thread_id": record.document_id}}, durability="sync")
    except OSError:
        assert initial
    finally:
        saver.put = original
    if terminal:
        graph.update_state({"configurable": {"thread_id": record.document_id}},
            {"jd_ai_run": record.model_copy(update={"status": "completed"}).model_dump(mode="json")},
            as_node="consultant")
    owner = ManualRuntime(DocumentCheckpoints(graph), RestartStorage, previous_host=PreviousHost())
    owner.storage.documents.append(record.document_id)
    runtime = AiRuntime(owner, codec)
    return runtime, record, binding, graph, model_calls, receipts


@pytest.mark.parametrize("initial", [False, True])
def test_restart_preserves_original_input_and_stops_without_replaying(initial):
    runtime, record, _, graph, calls, _ = saved_turn(initial=initial)
    before = len(calls)
    try:
        assert runtime.owner.finish_startup() == 1
        assert runtime.owner.ready
        observed = runtime.checkpoints.observe(record.document_id, record.run_id, record.dataset_id)
        assert observed.record.status == "failed" and observed.closed
        assert observed.messages[0] == HumanMessage(id=record.run_id, content="原始訪談\n  不可改寫")
        assert len(calls) == before and runtime.owner.storage.executed == []
        original = runtime.start(record.document_id, record.run_id, "原始訪談\n  不可改寫")
        assert original.wait().input_saved and original.wait().status == "failed"
        assert runtime.owner.finish_startup() == 0
    finally:
        assert runtime.owner.close(timeout=2)


def test_terminal_restart_is_read_only_and_does_not_relabel_a_complete_turn():
    runtime, record, _, graph, calls, _ = saved_turn(terminal=True)
    before = graph.get_state({"configurable": {"thread_id": record.document_id}})
    try:
        assert runtime.owner.finish_startup() == 0
        assert graph.get_state(before.config) == before
        assert graph.get_state({"configurable": {"thread_id": record.document_id}}).config == before.config
        result = runtime.start(record.document_id, record.run_id, "原始訪談\n  不可改寫").wait()
        assert result.status == "completed" and result.response_message_id == "saved-response"
        assert calls == [1] and not runtime.owner.storage.recovered
    finally:
        assert runtime.owner.close(timeout=2)


def test_previous_terminal_ai_does_not_hide_later_manual_recovery():
    runtime, record, _, graph, _, _ = saved_turn(terminal=True)
    manual = intent(record.document_id)
    runtime.owner.checkpoints.admit(manual.identity)
    try:
        assert runtime.owner.finish_startup() == 1
        assert runtime.owner.storage.recovered == [manual.identity]
        observed = runtime.checkpoints.observe(record.document_id, record.run_id, record.dataset_id)
        assert observed.record.status == "completed" and runtime.owner.ready
    finally:
        assert runtime.owner.close(timeout=2)


def test_closed_record_with_unanswered_tool_blocks_instead_of_guessing_completion():
    runtime, record, _, graph, calls, _ = saved_turn(calls=True, terminal=True)
    before = graph.get_state({"configurable": {"thread_id": record.document_id}})
    try:
        with pytest.raises((AiRuntimeError, RuntimeFailure)):
            runtime.owner.finish_startup()
        assert not runtime.owner.ready and calls == [1]
        assert graph.get_state({"configurable": {"thread_id": record.document_id}}).config == before.config
        assert not runtime.owner.storage.recovered and not runtime.owner.storage.executed
    finally:
        assert runtime.owner.close(timeout=2)


def test_conflicting_saved_ai_and_manual_pending_is_rejected_before_any_recovery_write():
    runtime, record, _, graph, calls, _ = saved_turn()
    manual = intent(record.document_id)
    graph.update_state({"configurable": {"thread_id": record.document_id}},
                       {"jd_manual_pending": _encode(manual.identity)}, as_node="consultant")
    before = graph.get_state({"configurable": {"thread_id": record.document_id}})
    try:
        with pytest.raises((AiRuntimeError, RuntimeFailure)):
            runtime.owner.finish_startup()
        after = graph.get_state({"configurable": {"thread_id": record.document_id}})
        assert after.config == before.config and after.values == before.values
        assert not runtime.owner.ready and not runtime.owner.storage.recovered and calls == [1]
    finally:
        assert runtime.owner.close(timeout=2)


@pytest.mark.parametrize("committed", [False, True])
def test_restart_fills_only_original_unanswered_tool_from_receipt(committed):
    runtime, record, binding, _, calls, receipts = saved_turn(calls=True)
    if committed:
        runtime.owner.storage.receipts.update(receipts)
    try:
        assert runtime.owner.finish_startup() == 1
        observed = runtime.checkpoints.observe(record.document_id, record.run_id, record.dataset_id)
        tool = observed.messages[-1]
        assert isinstance(tool, ToolMessage) and tool.tool_call_id == binding.tool_call_id
        assert tool.status == ("success" if committed else "error")
        assert observed.record.status == "failed" and observed.closed
        assert calls == [1] and not runtime.owner.storage.executed
        assert runtime.owner.storage.recovered == ([] if committed else [binding.identity])
    finally:
        assert runtime.owner.close(timeout=2)


def test_restart_failed_closure_retry_retains_same_foreign_owner_and_original_results():
    runtime, record, binding, graph, calls, _ = saved_turn(calls=True)
    original = graph.update_state
    def failure(*args, **kwargs):
        raise OSError("synthetic closure failure")
    graph.update_state = failure
    try:
        with pytest.raises((AiRuntimeError, RuntimeFailure)):
            runtime.owner.finish_startup()
        assert not runtime.owner.ready and runtime.owner.status(record.document_id).write_blocked
        handle = runtime._latest[record.document_id]._attempt.handle
        graph.update_state = original
        assert runtime.owner.finish_startup() == 1
        assert runtime._latest[record.document_id]._attempt.handle is handle
        assert runtime.owner.storage.recovered == [binding.identity] and calls == [1]
    finally:
        graph.update_state = original
        assert runtime.owner.close(timeout=2)


def test_restart_timeout_retains_actual_sql_future_and_does_not_duplicate_it():
    runtime, record, binding, _, calls, _ = saved_turn(calls=True)
    entered, release = Event(), Event()
    original = runtime.owner.storage.reconcile_stopped
    attempts = []
    def slow(identity):
        attempts.append(identity)
        entered.set()
        assert release.wait(3)
        return original(identity)
    runtime.owner.storage.reconcile_stopped = slow
    try:
        with pytest.raises((AiRuntimeError, RuntimeFailure)):
            runtime.owner.finish_startup(timeout=0.01)
        assert entered.wait(1) and runtime.owner.status(record.document_id).running
        with pytest.raises((AiRuntimeError, RuntimeFailure)):
            runtime.owner.finish_startup(timeout=0.01)
        assert attempts == [binding.identity] and not runtime.owner.ready
        release.set()
        runtime.owner._slots[record.document_id].entry.attempt.handle.wait(2)
        assert runtime.owner.finish_startup() == 1
        assert attempts == [binding.identity] and calls == [1]
    finally:
        release.set()
        assert runtime.owner.close(timeout=2)
