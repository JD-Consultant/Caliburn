"""Real native root/child + managed Futures; SQL/model ports are synthetic.

These tests cover local coordination only. True PostgreSQL/native SDK coverage
is in test_ai_runtime_postgres; neither suite opens a provider connection.
"""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from hashlib import sha256
import json
from threading import Event
from time import monotonic, sleep
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import START, END, StateGraph

from jd_relational.ai_runtime import AiRuntime, AiRuntimeError, _pending_calls, _verify_saved_results
from jd_relational.consultant_tools import decode_ai_binding
from jd_relational.manual_runtime import ForegroundHandle, ManualRuntime, RuntimeFailure
from jd_relational.observation_projection import project_observation
from jd_relational.reads import read_json
from jd_relational.references import ReferenceCodec
from jd_relational.runtime_checkpoints import DocumentCheckpoints, DocumentState, build_document_graph
from test_foreground_runtime import ForegroundStorage, ai_intent, run_identity
from test_manual_runtime import observation


HEAD = UUID("5d0edc37-c9d9-40c9-a4f1-70b79f5b1cd2")


class SyntheticStorage(ForegroundStorage):
    engine = SimpleNamespace(dialect=SimpleNamespace(name="postgresql", driver="psycopg"))
    revision_id = HEAD
    archived = False

    def read_current(self, document_id):
        return SimpleNamespace(document_id=document_id, revision_id=self.revision_id,
                               archived=self.archived)


class SyntheticRuntime(AiRuntime):
    """Bypass provider/context ports; retain actual native persistence and owner."""
    def _run(self, attempt, permit):
        config = {"configurable": {"thread_id": attempt.record.document_id}}
        attempt.before_config = self.graph.get_state(config, subgraphs=True).config
        attempt.before_state = deepcopy(self.graph.get_state(config, subgraphs=True))
        attempt.invoked = True
        self.graph.invoke({"messages": [attempt.human],
            "jd_ai_run": attempt.record.model_dump(mode="json"),
            "jd_ai_bindings": [], "jd_ai_read": None}, config, durability="sync")


@pytest.fixture
def make_runtime():
    owners, releases, runtimes = [], [], []

    def make(node=None, *, saver=None, background=None):
        calls = []
        def work(state):
            calls.append(state["jd_ai_run"]["run_id"])
            if node is not None:
                return node(state)
            return {"messages": [AIMessage(id=str(uuid4()), content="合成完整回覆")]}
        child = StateGraph(DocumentState)
        child.add_node("model", work)
        child.add_edge(START, "model")
        child.add_edge("model", END)
        graph = build_document_graph(child.compile(), saver or InMemorySaver())
        owner = ManualRuntime(DocumentCheckpoints(graph), SyntheticStorage, max_workers=2)
        codec = ReferenceCodec(b"synthetic-ai-runtime-test-key-32", str(uuid4()))
        runtime = SyntheticRuntime(owner, codec, background=background)
        owners.append(owner); runtimes.append(runtime)
        return runtime, graph, calls

    yield make, releases
    for release in releases:
        release.set()
    for runtime in runtimes:
        for handle in runtime._latest.values():
            if handle._attempt.result is None:
                handle.request_stop()
                handle.wait(5)
    for owner in owners:
        assert owner.close(timeout=5)


def test_pure_interview_closes_native_root_and_original_request_never_replays(make_runtime):
    make, _ = make_runtime
    runtime, graph, calls = make()
    document, run = str(uuid4()), str(uuid4())
    handle = runtime.start(document, run, "原始問答\r\n  保留空白。", expected_revision_id=HEAD)
    result = handle.wait(5)
    assert result.status == "completed" and result.input_saved and result.response_message_id
    assert runtime.start(document, run, "原始問答\r\n  保留空白。", expected_revision_id=HEAD) is handle
    with pytest.raises(AiRuntimeError, match="^operation_conflict$"):
        runtime.start(document, run, "不能更換同一請求的原話", expected_revision_id=HEAD)
    assert calls == [run] and not runtime.owner.storage.executed
    assert not runtime.owner.status(document).write_blocked
    state = graph.get_state({"configurable": {"thread_id": document}})
    assert not state.next and not state.tasks
    assert state.values["messages"][0].content == "原始問答\r\n  保留空白。"
    assert runtime.owner.close(timeout=1)
    reopened_owner = ManualRuntime(DocumentCheckpoints(graph), SyntheticStorage)
    try:
        reopened = SyntheticRuntime(reopened_owner, runtime.codec)
        original = reopened.start(document, run, "原始問答\r\n  保留空白。", expected_revision_id=HEAD)
        assert original.wait() == original.recover() == result
    finally:
        assert reopened_owner.close(timeout=1)
    assert calls == [run]


def test_same_owner_can_atomically_claim_only_one_coordinator(make_runtime):
    make, _ = make_runtime
    runtime, graph, _ = make()
    with pytest.raises(RuntimeFailure, match="^foreground_coordinator_already_configured$"):
        SyntheticRuntime(runtime.owner, runtime.codec)
    owner = ManualRuntime(DocumentCheckpoints(graph), SyntheticStorage)
    def construct():
        try:
            return SyntheticRuntime(owner, runtime.codec)
        except RuntimeFailure as error:
            return error.code
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: construct(), range(2)))
        assert sum(isinstance(result, SyntheticRuntime) for result in results) == 1
        assert results.count("foreground_coordinator_already_configured") == 1
    finally:
        assert owner.close(timeout=1)


def test_failed_new_turn_never_reports_the_previous_turn_response(make_runtime):
    make, _ = make_runtime
    def node(state):
        if state["messages"][-1].content == "第二轮":
            raise OSError("SyntheticPrivateProviderDetail")
        return {"messages": [AIMessage(id="previous-reply", content="第一轮回覆")]}
    runtime, graph, calls = make(node)
    document = str(uuid4())
    assert runtime.start(document, str(uuid4()), "第一轮", expected_revision_id=HEAD).wait(5).response_message_id == "previous-reply"
    failed = runtime.start(document, str(uuid4()), "第二轮", expected_revision_id=HEAD).wait(5)
    assert failed.status == "failed" and failed.input_saved and failed.response_message_id is None
    assert len(calls) == 2 and not runtime.owner.status(document).write_blocked
    assert [m.content for m in graph.get_state({"configurable": {"thread_id": document}}).values["messages"]
            if isinstance(m, HumanMessage)] == ["第一轮", "第二轮"]


def test_concurrent_same_request_returns_the_same_attempt_and_other_document_progresses(make_runtime):
    make, releases = make_runtime
    runtime, graph, calls = make()
    entered, release = Event(), Event()
    releases.append(release)
    document, run = str(uuid4()), str(uuid4())
    original = graph.get_state
    first = [True]
    def delayed(config, **kwargs):
        if config["configurable"]["thread_id"] == document and first[0]:
            first[0] = False
            entered.set()
            assert release.wait(5)
        return original(config, **kwargs)
    graph.get_state = delayed
    with ThreadPoolExecutor(max_workers=3) as pool:
        first_start = pool.submit(runtime.start, document, run, "同一原話", expected_revision_id=HEAD)
        assert entered.wait(2)
        repeated = pool.submit(runtime.start, document, run, "同一原話", expected_revision_id=HEAD)
        other = runtime.start(str(uuid4()), str(uuid4()), "另一份可繼續", expected_revision_id=HEAD)
        assert other.wait(5).status == "completed"
        release.set()
        first_handle, repeated_handle = first_start.result(5), repeated.result(5)
    assert first_handle is repeated_handle
    assert first_handle.wait(5).status == "completed"
    assert calls.count(run) == 1


def test_stop_waits_for_actual_run_and_preserves_original_messages(make_runtime):
    make, releases = make_runtime
    entered, release = Event(), Event()
    releases.append(release)
    def blocked(state):
        entered.set()
        assert release.wait(5)
        return {"messages": [AIMessage(id="actually-saved-reply", content="保存的實際結果")]}
    runtime, graph, calls = make(blocked)
    document, run = str(uuid4()), str(uuid4())
    handle = runtime.start(document, run, "取消不能抹掉原始問答", expected_revision_id=HEAD)
    assert entered.wait(2)
    handle.request_stop()
    with pytest.raises(TimeoutError):
        handle.wait(0.01)
    assert runtime.owner.status(document).running
    with pytest.raises(RuntimeFailure, match="document_busy"):
        runtime.owner.update_catalog(document, 1, archived=True)
    release.set()
    result = handle.wait(5)
    assert result.status == "cancelled" and result.input_saved
    assert result.response_message_id == "actually-saved-reply"
    assert not runtime.owner.status(document).write_blocked and calls == [run]
    assert graph.get_state({"configurable": {"thread_id": document}}).values["messages"][0].content == "取消不能抹掉原始問答"


def test_unanswered_read_is_closed_with_error_without_reinvoking_the_model(make_runtime):
    make, _ = make_runtime
    def read_call(state):
        return {"messages": [AIMessage(id="read-message", content="", tool_calls=[
            {"id": "read-call", "name": "jd_read", "args": {"view": "current", "target_ref": None, "cursor": None}}])]}
    runtime, graph, calls = make(read_call)
    document = str(uuid4())
    result = runtime.start(document, str(uuid4()), "查讀失敗", expected_revision_id=HEAD).wait(5)
    assert result.status == "failed" and result.response_message_id is None
    saved = graph.get_state({"configurable": {"thread_id": document}}).values["messages"]
    assert len(calls) == 1 and not _pending_calls(saved)
    assert isinstance(saved[-1], ToolMessage) and saved[-1].status == "error"
    assert saved[-1].tool_call_id == "read-call" and saved[-1].name == "jd_read"


@pytest.mark.parametrize("name", ["ls", "grep", "read_file", "read_conversation"])
@pytest.mark.parametrize("answered", [False, True])
def test_memory_reads_close_without_write_receipts_or_replay(make_runtime, name, answered):
    make, _ = make_runtime
    def read_call(state):
        messages = [AIMessage(id="memory-call-message", content="", tool_calls=[
            {"id": "memory-call", "name": name, "args": {}}])]
        if answered:
            messages.extend([ToolMessage(id="memory-result", name=name, tool_call_id="memory-call",
                content="合成原生讀取結果", status="success"), AIMessage(id="memory-final", content="合成回覆")])
        return {"messages": messages}
    runtime, graph, calls = make(read_call)
    document, run = str(uuid4()), str(uuid4())
    result = runtime.start(document, run, "回查工作理解", expected_revision_id=HEAD).wait(5)
    assert result.status == ("completed" if answered else "failed")
    saved = graph.get_state({"configurable": {"thread_id": document}}).values["messages"]
    assert not _pending_calls(saved) and len(calls) == 1
    tool = next(m for m in saved if isinstance(m, ToolMessage))
    if answered:
        assert tool.content == "合成原生讀取結果" and tool.status == "success"
    else:
        assert tool.status == "error" and json.loads(tool.content) == {
            "error": "memory_read_not_completed", "next_action": "stop"}
    assert runtime.lookup(document, run).wait() == result
    assert len(calls) == 1 and not runtime.owner.storage.executed


def test_start_checkpoint_error_uses_a_fixed_public_code(make_runtime):
    make, _ = make_runtime
    runtime, graph, _ = make()
    original = graph.get_state
    def unavailable(*args, **kwargs):
        raise OSError("SYNTHETIC_PRIVATE_DRIVER_DETAIL")
    graph.get_state = unavailable
    try:
        with pytest.raises(AiRuntimeError, match="^checkpoint_unavailable$"):
            runtime.start(str(uuid4()), str(uuid4()), "原話", expected_revision_id=HEAD)
    finally:
        graph.get_state = original


def test_start_read_is_drained_before_the_shared_owner_can_close(make_runtime):
    make, releases = make_runtime
    runtime, graph, _ = make()
    entered, release = Event(), Event()
    releases.append(release)
    original = graph.get_state
    def blocked(*args, **kwargs):
        entered.set()
        assert release.wait(5)
        return original(*args, **kwargs)
    graph.get_state = blocked
    with ThreadPoolExecutor(max_workers=1) as pool:
        starting = pool.submit(runtime.start, str(uuid4()), str(uuid4()), "原話", expected_revision_id=HEAD)
        assert entered.wait(2)
        try:
            assert not runtime.owner.close(timeout=0.01)
        finally:
            release.set()
        with pytest.raises((RuntimeFailure, AiRuntimeError), match="^runtime_closed$"):
            starting.result(5)


def test_run_closes_without_a_waiting_client_and_shutdown_does_not_relabel_success(make_runtime):
    make, _ = make_runtime
    runtime, _, calls = make()
    document, run = str(uuid4()), str(uuid4())
    handle = runtime.start(document, run, "視窗已離開但仍應由App收尾", expected_revision_id=HEAD)
    deadline = monotonic() + 2
    while runtime.owner.status(document).write_blocked and monotonic() < deadline:
        sleep(0.01)
    assert not runtime.owner.status(document).write_blocked
    assert runtime.owner.close(timeout=1)
    assert handle.wait().status == "completed" and calls == [run]


def test_done_callback_registration_waits_for_the_owner_callback_that_is_still_running(make_runtime, monkeypatch):
    make, releases = make_runtime
    runtime, _, _ = make()
    owner_entered, release, registering = Event(), Event(), Event()
    releases.append(release)
    original_done = runtime.owner._foreground_finished
    original_add = ForegroundHandle.add_done_callback
    def delayed_done(slot, entry, future):
        owner_entered.set()
        assert release.wait(5)
        return original_done(slot, entry, future)
    def late_registration(handle, callback):
        assert owner_entered.wait(3)
        assert handle._entry.future.done() and not handle._entry.settled.is_set()
        registering.set()
        return original_add(handle, callback)
    monkeypatch.setattr(runtime.owner, "_foreground_finished", delayed_done)
    monkeypatch.setattr(ForegroundHandle, "add_done_callback", late_registration)
    with ThreadPoolExecutor(max_workers=1) as pool:
        starting = pool.submit(runtime.start, str(uuid4()), str(uuid4()), "完整回合", expected_revision_id=HEAD)
        assert registering.wait(3)
        # Registration on an already-done Future runs in this registering thread.
        # The owner's earlier callback is still executing on the original worker.
        sleep(0.02)
        release.set()
        handle = starting.result(5)
    try:
        assert handle.wait(5).status == "completed"
    finally:
        if handle._attempt.result is None:
            handle.recover()


def test_background_closure_failure_requires_explicit_reconciliation_without_model_replay(make_runtime):
    make, _ = make_runtime
    runtime, graph, calls = make()
    original_update = graph.update_state
    updates = []
    def unavailable(*args, **kwargs):
        updates.append(1)
        raise OSError("SYNTHETIC_PRIVATE_CLOSURE_DETAIL")
    graph.update_state = unavailable
    document, run = str(uuid4()), str(uuid4())
    handle = runtime.start(document, run, "回覆已保存但閉合暫不可用", expected_revision_id=HEAD)
    try:
        with pytest.raises(AiRuntimeError, match="^run_recovery_required$"):
            handle.wait(5)
        assert calls == [run] and len(updates) == 1
        assert runtime.owner.status(document).write_blocked
    finally:
        graph.update_state = original_update
        restored = handle.recover()
    assert restored.status == "completed" and handle.wait() == restored
    assert calls == [run] and not runtime.owner.status(document).write_blocked


def test_short_wait_does_not_block_on_background_saver_closure(make_runtime):
    make, releases = make_runtime
    runtime, graph, _ = make()
    entered, release = Event(), Event()
    releases.append(release)
    original_update = graph.update_state
    def blocked(*args, **kwargs):
        entered.set()
        assert release.wait(5)
        return original_update(*args, **kwargs)
    graph.update_state = blocked
    # Keep callback registration before completion so this test owns only the
    # observer timeout, not the separate finished-Future registration race.
    original_done = runtime.owner._foreground_finished
    registered = Event()
    def delayed_done(*args):
        assert registered.wait(5)
        return original_done(*args)
    runtime.owner._foreground_finished = delayed_done
    with ThreadPoolExecutor(max_workers=1) as pool:
        starting = pool.submit(runtime.start, str(uuid4()), str(uuid4()), "等待保存", expected_revision_id=HEAD)
        registered.set()
        assert entered.wait(3)
        # If the Future completed before callback registration, start itself can
        # be completing the callback. The shared cached handle is already valid.
        handle = next(iter(runtime._latest.values()))
        try:
            with pytest.raises(TimeoutError, match="^run_closure_pending$"):
                handle.wait(0.01)
            with pytest.raises(AiRuntimeError, match="^run_recovery_pending$"):
                handle.recover()
            assert not runtime.owner.close(timeout=0.01)
        finally:
            release.set()
        assert starting.result(5) is handle
    assert handle.wait(5).status == "completed"


@pytest.mark.parametrize("prior", [False, True])
@pytest.mark.parametrize("failure", ["all_puts", "input_to_loop", "first_put_ack"])
def test_initial_saver_failure_preserves_the_actual_input_state_without_model_replay(make_runtime, prior, failure):
    make, _ = make_runtime
    saver = InMemorySaver()
    runtime, graph, calls = make(saver=saver)
    document, run = str(uuid4()), str(uuid4())
    if prior:
        assert runtime.start(document, str(uuid4()), "先前原話", expected_revision_id=HEAD).wait(5).status == "completed"
    previous_calls = len(calls)
    previous = graph.get_state({"configurable": {"thread_id": document}})
    original, injected = saver.put, []
    def failing(config, checkpoint, metadata, new_versions):
        root = not config["configurable"].get("checkpoint_ns")
        if failure == "all_puts":
            raise OSError("SYNTHETIC_PRIVATE_SAVER_DETAIL")
        candidate = root and (metadata.get("source") == "input" if failure == "first_put_ack"
                             else metadata.get("source") == "loop")
        if candidate and not injected:
            injected.append(1)
            if failure == "first_put_ack":
                original(config, checkpoint, metadata, new_versions)
            raise OSError("SYNTHETIC_PRIVATE_SAVER_DETAIL")
        return original(config, checkpoint, metadata, new_versions)
    saver.put = failing
    try:
        result = runtime.start(document, run, "新原始問答\n  不可遺漏", expected_revision_id=HEAD).wait(5)
        assert result.status == "failed" and result.response_message_id is None
        assert result.input_saved is (failure != "all_puts")
        assert len(calls) == previous_calls
        state = graph.get_state({"configurable": {"thread_id": document}})
        assert not state.next and not state.tasks and not runtime.owner.status(document).write_blocked
        if failure == "all_puts":
            assert state.values == previous.values and state.config == previous.config
        else:
            assert [m.content for m in state.values["messages"] if isinstance(m, HumanMessage)] == (
                ["先前原話"] if prior else []) + ["新原始問答\n  不可遺漏"]
    finally:
        saver.put = original


def _receipt_fixture():
    identity = run_identity()
    intent = ai_intent(identity)
    codec = ReferenceCodec(b"synthetic-ai-runtime-test-key-32", str(uuid4()))
    command = intent.command
    call = AIMessage(id="bound-ai", content="", tool_calls=[{
        "id": "bound-call", "name": command["tool"], "args": command["arguments"]}])
    digest = sha256(json.dumps({"name": command["tool"], "args": command["arguments"]},
        ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    binding = decode_ai_binding({"format_version": 1, "dataset_id": codec.dataset_id,
        "document_id": identity.document_id, "run_id": identity.run_id,
        "operation_id": str(intent.operation_id), "base_revision_id": str(intent.base_revision_id),
        "origin": "ai", "request_digest": intent.request_digest,
        "command_kind": command["tool"], "message_id": call.id, "tool_call_id": "bound-call", "input_digest": digest},
        dataset_id=codec.dataset_id, document_id=identity.document_id, run_id=identity.run_id)
    result = observation(intent.identity)
    receipts = {intent.operation_id: result}
    message = ToolMessage(id="result", tool_call_id="bound-call", name=command["tool"],
        content=read_json(project_observation(result, codec)), status="success")
    return [call, message], (binding,), receipts, codec


@pytest.mark.parametrize("fault", [None, "content", "status", "name"])
def test_saved_success_must_match_the_original_receipt(fault):
    messages, bindings, receipts, codec = _receipt_fixture()
    if fault == "content":
        value = json.loads(messages[-1].content)
        value["result_revision_ref"] = "invented-version"
        messages[-1].content = read_json(value)
    elif fault == "status":
        messages[-1].status = "error"
    elif fault == "name":
        messages[-1].name = "jd_read"
    if fault is None:
        _verify_saved_results(messages, bindings, receipts, codec)
    else:
        with pytest.raises(AiRuntimeError, match="^invalid_saved_tool_result$"):
            _verify_saved_results(messages, bindings, receipts, codec)


@pytest.mark.parametrize("following", [HumanMessage(content="next"), AIMessage(content="next"),
    ToolMessage(content="wrong", tool_call_id="wrong")])
def test_unpaired_history_cannot_become_the_next_model_input(following):
    call = AIMessage(id="ai", content="", tool_calls=[{"id": "call", "name": "jd_read", "args": {}}])
    with pytest.raises(AiRuntimeError, match="^invalid_saved_conversation$"):
        _pending_calls([call, following])
