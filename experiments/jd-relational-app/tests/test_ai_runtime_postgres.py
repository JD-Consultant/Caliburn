"""Real owner, JD SQL and native PG Saver; SDK traffic is synthetic MockTransport.

No FakeAuthority, provider, HTTP host, Saver setup or persisted-data deletion.
These are local foreground-run proofs, not cross-process host-death proofs.
"""

from contextlib import contextmanager
from copy import deepcopy
import asyncio
import json
import os
from threading import Event
import traceback
from uuid import uuid4

import httpx
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langsmith.run_helpers import get_tracing_context
import pytest

from jd_relational.ai_runtime import AiRuntime
from jd_relational.consultant_context import build_consultant_node, read_closed_model_view
from jd_relational.consultant_model import OPENROUTER_HEADERS, create_consultant_model
from jd_relational.consultant_tools import AiToolMiddleware, build_jd_tools, decode_ai_bindings
from jd_relational.intents import bind_edit
from jd_relational.manual_runtime import ManualRuntime, RuntimeFailure
from jd_relational.reads import command_context
from jd_relational.references import ReferenceCodec
from jd_relational.runtime_checkpoints import DocumentCheckpoints, build_document_graph
from jd_relational.storage.service import JdStorage
from support.openrouter_replies import reply as _reply
from test_consultant_context_postgres import _notice
from test_manual_runtime_postgres import NATIVE_TABLES, RUNTIME_SCHEMA, connect, counts
from test_storage_postgres import engine


pytestmark = pytest.mark.skipif(os.environ.get("JD_RELATIONAL_TEST_DB") != "1",
    reason="explicit isolated PostgreSQL test opt-in required")


@contextmanager
def _offline_model(monkeypatch, plan, *, before_reply=None, expected_tools=None,
                   allow_final_no_tools=False):
    # Identity, not a count: the wire must carry exactly the tools this
    # consultant was given, so adding one is a deliberate, visible change.
    expected_names = {getattr(tool, "name", tool) for tool in
                      (build_jd_tools() if expected_tools is None else expected_tools)}
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")
    requests = []
    prefix = uuid4().hex

    def receive(request):
        assert get_tracing_context()["enabled"] is False
        assert request.url.host == "openrouter.ai"
        assert request.headers["authorization"] == "Bearer synthetic-ai-runtime-not-a-key"
        assert len(requests) < len(plan), "No hidden model retry or replay is allowed."
        payload = json.loads(request.content)
        # This product never allows parallel tool calls and never lets the
        # provider keep the conversation: the durable record is this App's.
        assert payload["parallel_tool_calls"] is False
        assert payload["provider"] == {"only": ["OpenAI"], "order": ["OpenAI"],
            "allow_fallbacks": False, "require_parameters": True}
        final_no_tools = payload.get("tools") == [] and payload.get("tool_choice") == "none"
        if final_no_tools:
            assert allow_final_no_tools, "Unexpected final no-tools request in this fixture."
        else:
            assert {tool["function"]["name"] for tool in payload["tools"]} == expected_names
            assert len(payload["tools"]) == len(expected_names)
        assert all(tool["function"]["strict"] is True for tool in payload["tools"])
        requests.append(payload)
        name, arguments = plan[len(requests) - 1](payload)
        if before_reply is not None:
            # The test owns this pause; it holds the real in-flight call open.
            before_reply()
        return httpx.Response(200, json=_reply(f"{prefix}_{len(requests)}", name, arguments),
                              request=request)

    with httpx.Client(
        transport=httpx.MockTransport(receive),
        headers=OPENROUTER_HEADERS,
        trust_env=False,
        timeout=5,
    ) as client:
        async_client = httpx.AsyncClient(
            transport=httpx.MockTransport(receive),
            headers=OPENROUTER_HEADERS,
            trust_env=False,
            timeout=5,
        )
        try:
            model = create_consultant_model(api_key="synthetic-ai-runtime-not-a-key",
                                            http_client=client, async_http_client=async_client)
            yield model, requests
        finally:
            asyncio.run(async_client.aclose())


@contextmanager
def _runtime(engine, model):
    with connect() as conn:
        assert conn.execute("SELECT current_database() AS db, current_user AS usr, "
            "current_setting('server_version_num')::integer AS version").fetchone() == {
                "db": "caliburn_jd_relational_test", "usr": "jd_test", "version": 180006}
        assert conn.execute("SHOW search_path").fetchone()["search_path"] == "jd_runtime_test,public"
        assert {row["tablename"] for row in conn.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname = %s", (RUNTIME_SCHEMA,))} == NATIVE_TABLES
        saver = PostgresSaver(conn, serde=JsonPlusSerializer(allowed_msgpack_modules=None))
        child = build_consultant_node(model, tools=build_jd_tools(), guidance="合成測試：忠實保存原話描述的工作。",
                                      extra_middleware=(AiToolMiddleware(),))
        graph = build_document_graph(child, saver)
        owner = ManualRuntime(DocumentCheckpoints(graph), lambda authority: JdStorage(engine, authority), max_workers=2)
        codec = ReferenceCodec(b"synthetic-ai-runtime-pg-key-32-bytes", str(uuid4()))
        runtime = AiRuntime(owner, codec)
        try:
            yield runtime, owner, graph
        finally:
            assert owner.close(timeout=5), "Actual test-owned work must finish before closing the PG Saver."
    assert conn.closed


def _read(_):
    return "jd_read", {"view": "current", "target_ref": None, "cursor": None}


def _final(_):
    return None, None


def _last_page(payload):
    results = []
    for message in payload["messages"]:
        if message.get("role") == "tool":
            results.append(json.loads(message["content"]))
        elif isinstance(message.get("content"), list):
            results.extend(json.loads(block["content"]) for block in message["content"]
                           if block.get("type") == "tool_result")
    value = results[-1]
    assert value["view"] == "current" and value["access"] == "current" and not value["has_more"]
    return value


def _create(payload):
    page = _last_page(payload)
    container = next(row for row in page["records"] if row["type"] == "container"
                     and row["child_kind"] == "task" and row["owner_ref"] is None)
    return "jd_create_task", {"container_ref": container["container_ref"], "after_ref": None,
        "name": "合成設備检查", "description": "收到通知後檢查約定設備。", "basis_refs": [],
        "outcomes": [{"text": "檢查記錄", "basis_refs": []}, {"text": "異常交接", "basis_refs": []}],
        "requirements": [{"text": "先確認隔離再檢查", "basis_refs": []}], "capabilities": []}


def _task_field(page, name):
    item = next(row for row in page["records"] if row["type"] == "item" and row["kind"] == "task")
    return next(row for row in page["records"] if row["type"] == "field" and row["item_ref"] == item["item_ref"]
                and row["name"] == name)


def _revise(payload):
    page = _last_page(payload)
    assert _task_field(page, "description")["value"] == "人工更正：只檢查約定設備，不修理外包設備。"
    return "jd_set_text", {"target_field_ref": _task_field(page, "name")["field_ref"],
                           "text": "約定設備檢查與交接", "basis_refs": []}


def _manual_description(runtime, document):
    current = runtime.owner.storage.read_current(document)
    page = runtime.reads.read(document, {"view": "current", "target_ref": None, "cursor": None})
    command = {"tool": "jd_set_text", "arguments": {
        "target_field_ref": _task_field(page, "description")["field_ref"],
        "text": "人工更正：只檢查約定設備，不修理外包設備。", "basis_refs": []}}

    def no_sources(*args):
        raise AssertionError("Synthetic empty basis must not read external sources.")

    context = command_context(current.domain, command, runtime.codec, no_sources, lambda: str(uuid4()))
    intent = bind_edit(uuid4(), "manual", None, command, context)
    result = runtime.owner.submit(intent).wait(10)
    assert result.observation.confirmed and result.observation.status == "committed" and result.checkpoint_closed
    return intent


def _state(graph, document):
    state = graph.get_state({"configurable": {"thread_id": document}}, subgraphs=True)
    assert not state.next and not state.tasks
    return state


def _failure(handle):
    # Test-only diagnostics expose exception classes/codes and stack locations,
    # never exception text, request bodies, credentials or saved content.
    error = handle._attempt.handle._entry.future.exception()
    chain = []
    while error is not None and len(chain) < 5:
        chain.append((type(error).__name__, getattr(error, "code", None),
            [(frame.name, frame.lineno) for frame in traceback.extract_tb(error.__traceback__)][-3:]))
        error = error.__cause__
    return chain


def test_real_owner_ai_manual_ai_journey_preserves_body_and_native_conversation(monkeypatch, engine):
    plan = [_read, _create, _final, _read, _revise, _final]
    with _offline_model(monkeypatch, plan) as (model, requests):
        with _runtime(engine, model) as (runtime, owner, graph):
            document = owner.create_document(uuid4(), "合成 AI 與人工共同保存")
            execute, saved_before_sql = owner.storage.execute, []

            def require_persisted_binding(intent):
                if intent.origin == "ai":
                    observed = runtime.checkpoints.observe(document, intent.ai_run_id, runtime.codec.dataset_id)
                    bindings = decode_ai_bindings(observed.bindings, dataset_id=runtime.codec.dataset_id,
                                                  document_id=document, run_id=intent.ai_run_id)
                    assert any(binding.identity == intent.identity for binding in bindings)
                    saved_before_sql.append(intent.operation_id)
                return execute(intent)

            monkeypatch.setattr(owner.storage, "execute", require_persisted_binding)
            first_run, second_run = str(uuid4()), str(uuid4())
            first_text = "原話\n  我收到通知後檢查設備，先確認隔離，留檢查記錄並交接異常。"
            first_base = owner.storage.read_current(document).revision_id
            first_handle = runtime.start(document, first_run, first_text, expected_revision_id=first_base)
            first = first_handle.wait(15)
            assert first.status == "completed" and first.input_saved and first.response_message_id, (len(requests), _failure(first_handle))
            first_current = owner.storage.read_current(document)
            assert first_current.revision_number == 2 and len(first_current.domain["tasks"]) == 1
            assert {row["text"] for row in first_current.domain["details"].values()} == {"先確認隔離再檢查", "異常交接", "檢查記錄"}
            before = _state(graph, document)
            original_messages = deepcopy(before.values["messages"])
            first_view = read_closed_model_view(graph, document_id=document,
                dataset_id=runtime.codec.dataset_id, run_id=first_run)
            assert first_view.revision_id == str(first_current.revision_id)
            first_bindings = decode_ai_bindings(before.values["jd_ai_bindings"], dataset_id=runtime.codec.dataset_id,
                                               document_id=document, run_id=first_run)
            first_receipt = owner.storage.lookup(first_bindings[0].identity).receipt
            assert first_receipt.origin == "ai" and first_receipt.ai_run_id == first_run
            assert counts(engine, document) == (2, 1)
            manual = _manual_description(runtime, document)
            assert _state(graph, document).values["messages"] == original_messages
            second_text = "依我手動更正的範圍，把任務名稱也寫清楚。"
            second_base = owner.storage.read_current(document).revision_id
            second = runtime.start(document, second_run, second_text, expected_revision_id=second_base).wait(15)
            assert second.status == "completed" and second.response_message_id
            current = owner.storage.read_current(document)
            task = next(iter(current.domain["tasks"].values()))
            assert task["name"] == "約定設備檢查與交接"
            assert task["description"] == "人工更正：只檢查約定設備，不修理外包設備。"
            assert current.domain["details"] == first_current.domain["details"]
            assert current.revision_number == 4 and counts(engine, document) == (4, 3)
            assert owner.storage.lookup(first_bindings[0].identity).receipt == first_receipt
            notice = _notice(requests[3])
            assert notice["turn_start"]["manual_change_count"] == 1
            assert notice["turn_start"]["ai_change_count"] == 0
            change = runtime.codec.resolve(notice["turn_start"]["events"][0]["change_ref"],
                document_id=document, roles={"change"}, purposes={"observation"})
            assert change.entity_id == str(manual.operation_id)
            saved = _state(graph, document)
            humans = [message for message in saved.values["messages"] if isinstance(message, HumanMessage)]
            assert [(message.id, message.content) for message in humans] == [(first_run, first_text), (second_run, second_text)]
            assert saved.values["messages"][:len(original_messages)] == original_messages
            assert saved.values["jd_ai_run"]["status"] == "completed"
            assert read_closed_model_view(graph, document_id=document, dataset_id=runtime.codec.dataset_id,
                                          run_id=second_run).revision_id == str(current.revision_id)
            assert len(requests) == 6 and owner.checkpoints.read(document) is None
            assert len(saved_before_sql) == 2 and len(set(saved_before_sql)) == 2
            # Same request identity returns the original local run; no new model request.
            assert runtime.start(document, second_run, second_text, expected_revision_id=second_base).wait(1) == second
            # A later run replaced the local slot: lookup A through native
            # history and its true SQL receipts, without requiring today's head.
            assert runtime.lookup(document, first_run).wait(0) == first_handle.wait(0)
            assert runtime.start(document, first_run, first_text,
                expected_revision_id=first_base).wait(0) == first_handle.wait(0)
            assert len(requests) == 6


def test_real_ai_sql_commit_ack_loss_reads_original_receipt_without_next_model(monkeypatch, engine):
    with _offline_model(monkeypatch, [_read, _create]) as (model, requests):
        with _runtime(engine, model) as (runtime, owner, graph):
            document = owner.create_document(uuid4(), "合成 AI 保存回覆遺失")
            run_id = str(uuid4())
            original_execute, original_commit = owner.storage.execute, engine.dialect.do_commit
            executions, lost = [], []

            def lose_commit(connection):
                original_commit(connection)
                lost.append(True)
                raise OSError("synthetic SQL COMMIT acknowledgment lost")

            def execute(intent):
                assert not executions, "Recovery must not replay the write command."
                executions.append(intent)
                with monkeypatch.context() as fault:
                    fault.setattr(engine.dialect, "do_commit", lose_commit)
                    return original_execute(intent)

            monkeypatch.setattr(owner.storage, "execute", execute)
            handle = runtime.start(document, run_id, "合成原話：建立設備檢查工作。", expected_revision_id=runtime.owner.storage.read_current(document).revision_id)
            result = handle.wait(15)
            assert result.status == "failed" and result.input_saved and result.response_message_id is None
            assert executions and lost and len(requests) == 2, (len(requests), _failure(handle))
            saved = owner.storage.lookup(executions[0].identity)
            assert saved.confirmed and saved.receipt.status == "committed"
            assert saved.receipt.origin == "ai" and saved.receipt.ai_run_id == run_id
            assert counts(engine, document) == (2, 1)
            assert len(owner.storage.read_current(document).domain["tasks"]) == 1
            state = _state(graph, document)
            output = [message for message in state.values["messages"] if isinstance(message, ToolMessage)
                      and message.name == "jd_create_task"]
            assert len(output) == 1 and output[0].status == "success"
            value = json.loads(output[0].content)
            assert value["status"] == "committed" and value["receipt_durability"] == "confirmed"
            operation = runtime.codec.resolve(value["operation_ref"], document_id=document,
                                               roles={"operation"}, purposes={"observation"})
            assert operation.entity_id == str(executions[0].operation_id)
            assert not [message for message in state.values["messages"] if isinstance(message, AIMessage) and not message.tool_calls]
            assert state.values["jd_ai_run"]["status"] == "failed" and owner.checkpoints.read(document) is None
            assert handle.wait(1) == result and len(requests) == 2 and len(executions) == 1
            assert owner.storage.lookup(executions[0].identity).receipt == saved.receipt


def test_real_pure_interview_has_no_revision_and_reopened_saver_only_reads(monkeypatch, engine):
    with _offline_model(monkeypatch, [_final]) as (model, requests):
        with _runtime(engine, model) as (runtime, owner, graph):
            document = owner.create_document(uuid4(), "合成純訪談不強迫改稿")
            run_id, text = str(uuid4()), "先問我這項工作的範圍，現在還不用改 JD。"
            original = owner.storage.read_current(document)
            result = runtime.start(document, run_id, text, expected_revision_id=runtime.owner.storage.read_current(document).revision_id).wait(15)
            assert result.status == "completed" and result.input_saved
            assert counts(engine, document) == (1, 0)
            assert owner.storage.read_current(document) == original
            saved = _state(graph, document)
            assert saved.values["jd_ai_bindings"] == [] and saved.values["jd_ai_read"] is None
            original_messages = deepcopy(saved.values["messages"])
        # New native Saver connection and graph; no invoke/start or HTTP replay.
        with _runtime(engine, model) as (_, owner, graph):
            reopened = _state(graph, document)
            assert reopened.values["messages"] == original_messages
            assert reopened.values["jd_ai_run"]["status"] == "completed"
            assert owner.checkpoints.read(document) is None
            assert counts(engine, document) == (1, 0) and len(requests) == 1


def test_cancel_waits_for_actual_stream_future_before_closing_pg_run(monkeypatch, engine):
    entered, release = Event(), Event()

    def hold():
        entered.set()
        assert release.wait(5), "The test-owned call must be released within its budget."

    with _offline_model(monkeypatch, [_final], before_reply=hold) as (model, requests):
        with _runtime(engine, model) as (runtime, owner, graph):
            document = owner.create_document(uuid4(), "合成取消等待真串流停止")
            handle = runtime.start(document, str(uuid4()), "合成原话，尚未完成回覆。", expected_revision_id=runtime.owner.storage.read_current(document).revision_id)
            try:
                assert entered.wait(5)
                handle.request_stop()
                with pytest.raises(TimeoutError):
                    handle.wait(0.01)
                status = owner.status(document)
                assert status.running and status.write_blocked
                with pytest.raises(RuntimeFailure) as conflict:
                    owner.update_catalog(document, 1, title="取消仍在執行，不可更名")
                assert conflict.value.code == "document_busy"
                assert owner.close(timeout=0.01) is False
                assert counts(engine, document) == (1, 0)
            finally:
                release.set()
            result = handle.wait(15)
            assert result.status == "cancelled" and result.input_saved and result.response_message_id is None
            state = _state(graph, document)
            assert state.values["jd_ai_run"]["status"] == "cancelled"
            assert state.values.get("jd_model_view") is None
            assert not [message for message in state.values["messages"] if isinstance(message, AIMessage)]
            assert counts(engine, document) == (1, 0) and len(requests) == 1
            assert owner.checkpoints.read(document) is None
