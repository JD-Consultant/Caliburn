"""Real JD SQL + native PG Saver + agent/SDK, with offline synthetic SSE only.

The imported FakeAuthority prepares manual fixture edits; it is not evidence of
AI writer admission. No Saver setup, persisted-data cleanup, real provider or
automatic graph replay occurs here. Opt in only to the existing test database.
"""

from contextlib import contextmanager
from copy import deepcopy
from hashlib import sha256
import json
import os
from uuid import uuid4

import httpx2
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
import pytest

from jd_relational.consultant_context import (
    ConsultantContext, ConsultantContextError, build_consultant_node,
    checked_model_view, read_closed_model_view,
)
from jd_relational.consultant_model import ConsultantModelError, create_consultant_model
from jd_relational.notice_history import NoticeHistoryReader
from jd_relational.references import ReferenceCodec
from jd_relational.runtime_checkpoints import build_document_graph
from jd_relational.storage.service import JdStorage
from test_consultant_model import SyncBody, events
from test_manual_runtime_postgres import NATIVE_TABLES, RUNTIME_SCHEMA, connect
from test_storage_postgres import engine
from test_storage_service import FakeAuthority, change, intent_for


pytestmark = pytest.mark.skipif(os.environ.get("JD_RELATIONAL_TEST_DB") != "1",
    reason="explicit isolated PostgreSQL test opt-in required")


@pytest.fixture
def store(engine):
    return JdStorage(engine, FakeAuthority())


def _purpose(store, current, text):
    return change(store, current, "jd_set_text", {
        "target_field_ref": "profile.purpose", "text": text, "basis_refs": [],
    })


def _data(mode, number):
    """Give each native response its own id, just as separate SDK messages do."""
    chunks = []
    for chunk in events(mode=mode):
        item = json.loads(chunk.decode().split("data: ", 1)[1])
        if item["type"] == "message_start":
            item["message"]["id"] = f"msg_synthetic_pg_{number}"
        elif item["type"] == "content_block_delta":
            item["delta"]["text"] = f"第 {number} 次合成回覆"
        chunks.append(f"event: {item['type']}\ndata: {json.dumps(item)}\n\n".encode())
    return chunks


@contextmanager
def _offline_model(monkeypatch, modes):
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")
    requests, bodies = [], []

    def receive(request):
        # MockTransport receives the real SDK request; it never opens a socket.
        assert request.url.host == "api.anthropic.com"
        assert request.headers["x-api-key"] == "synthetic-pg-not-a-key"
        assert len(requests) < len(modes), "No hidden model retry or replay is allowed."
        payload = json.loads(request.content)
        assert payload["stream"] is True
        requests.append(payload)
        body = SyncBody(_data(modes[len(requests) - 1], len(requests)))
        bodies.append(body)
        return httpx2.Response(200, headers={"content-type": "text/event-stream"},
                               stream=body, request=request)

    def no_async(**kwargs):
        raise AssertionError("This synchronous PG slice must not construct another HTTP client.")

    with httpx2.Client(transport=httpx2.MockTransport(receive), trust_env=False) as client:
        monkeypatch.setattr("langchain_anthropic.chat_models._get_default_httpx_client", lambda **kwargs: client)
        monkeypatch.setattr("langchain_anthropic.chat_models._get_default_async_httpx_client", no_async)
        model = create_consultant_model(model_name="synthetic", api_key="synthetic-pg-not-a-key",
                                       timeout=5, max_tokens=64)
        yield model, requests, bodies
    assert all(body.closed for body in bodies)


@contextmanager
def _graph(model):
    with connect() as conn:
        assert conn.execute("SELECT current_database() AS db, current_user AS usr, "
            "current_setting('server_version_num')::integer AS version").fetchone() == {
                "db": "caliburn_jd_relational_test", "usr": "jd_test", "version": 180006}
        assert conn.execute("SHOW search_path").fetchone()["search_path"] == "jd_runtime_test,public"
        assert {row["tablename"] for row in conn.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname = %s", (RUNTIME_SCHEMA,))} == NATIVE_TABLES
        saver = PostgresSaver(conn, serde=JsonPlusSerializer(allowed_msgpack_modules=None))
        child = build_consultant_node(model, tools=[], guidance="合成顧問指引：依員工原話與已保存工作繼續。")
        yield build_document_graph(child, saver)
    assert conn.closed


def _context(history, codec, document_id, previous=None):
    baseline = previous.boundary if previous else None
    return ConsultantContext(codec.dataset_id, document_id, str(uuid4()), history, codec,
                             history.read(document_id, baseline))


def _notice(payload):
    notices = []
    for block in payload["system"]:
        if block["type"] != "text":
            continue
        try:
            value = json.loads(block["text"])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and value.get("type") == "jd_change_notice":
            notices.append(value)
    assert len(notices) == 1
    return notices[0]


def _digest(value):
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":"), allow_nan=False).encode()
    return sha256(encoded).hexdigest()


def _assert_pair(state, context):
    view = checked_model_view(state.values.get("jd_model_view"), dataset_id=context.dataset_id,
                              document_id=context.document_id)
    assert view is not None
    replies = [message for message in state.values["messages"]
               if isinstance(message, AIMessage) and message.id == view.response_message_id]
    assert len(replies) == 1
    reply = replies[0]
    assert reply.response_metadata["stop_reason"] == "end_turn"
    assert reply.usage_metadata["output_tokens"] == 9
    assert _digest(reply.model_dump(mode="json")) == view.response_digest
    assert sha256(view.notice_json.encode()).hexdigest() == view.notice_digest
    return view


def test_real_notice_two_turns_and_pg_reopen_preserve_paired_response_without_replay(monkeypatch, store, engine):
    current = store.read_current(store.create_document(uuid4(), "合成持久顧問通知"))
    current, first_edit, _ = _purpose(store, current, "合成工作 A")
    history = NoticeHistoryReader(engine)
    codec = ReferenceCodec(b"synthetic-notice-context-pg-key-32", str(uuid4()))
    first_context = _context(history, codec, current.document_id)
    config = {"configurable": {"thread_id": current.document_id}}
    humans = [HumanMessage(id="human-" + str(uuid4()), content="原始問答\n  保留空白與原話。"),
              HumanMessage(id="human-" + str(uuid4()), content=[{"type": "text", "text": "先更正再改回。"}])]
    original_humans = [deepcopy(message.model_dump()) for message in humans]
    with _offline_model(monkeypatch, ["complete", "complete"]) as (model, requests, bodies):
        with _graph(model) as graph:
            graph.invoke({"messages": [humans[0]]}, config, context=first_context, durability="sync")
            first = read_closed_model_view(graph, document_id=current.document_id,
                dataset_id=codec.dataset_id, run_id=first_context.run_id)
            assert first.revision_id == str(current.revision_id) and first.revision_number == 2
            first_notice = _notice(requests[0])
            assert first_notice["turn_start"]["manual_change_count"] == 1
            assert first_notice["turn_start"]["ai_change_count"] == 0
            assert requests[0]["messages"] == [{"role": "user", "content": humans[0].content}]
            first_ref = codec.resolve(first_notice["turn_start"]["events"][0]["change_ref"],
                document_id=current.document_id, roles={"change"}, purposes={"observation"})
            assert first_ref.entity_id == str(first_edit.operation_id)
            current, changed, _ = _purpose(store, current, "合成工作 B")
            current, reverted, _ = _purpose(store, current, "合成工作 A")
            unchanged = intent_for(store, current, "jd_set_text", {
                "target_field_ref": "profile.purpose", "text": "合成工作 A", "basis_refs": []})
            assert store.execute(unchanged).status == "no_change"
            second_context = _context(history, codec, current.document_id, first)
            graph.invoke({"messages": [humans[1]]}, config, context=second_context, durability="sync")
            second = read_closed_model_view(graph, document_id=current.document_id,
                dataset_id=codec.dataset_id, run_id=second_context.run_id)
            assert second.revision_id == str(current.revision_id) and second.revision_number == 4
            assert second.response_message_id != first.response_message_id
            notice = _notice(requests[1])
            assert notice["turn_start"]["first_notification"] is False
            assert notice["turn_start"]["baseline_revision_number"] == 2
            assert notice["turn_start"]["manual_change_count"] == 2
            assert notice["turn_start"]["ai_change_count"] == notice["turn_start"]["omitted_count"] == 0
            assert [row["result_revision_number"] for row in notice["turn_start"]["events"]] == [4, 3]
            assert [codec.resolve(row["change_ref"], document_id=current.document_id,
                                  roles={"change"}, purposes={"observation"}).entity_id
                    for row in notice["turn_start"]["events"]] == [str(reverted.operation_id), str(changed.operation_id)]
            assert notice["turn_start"]["content_included"] is False
            assert [message["role"] for message in requests[1]["messages"]] == ["user", "assistant", "user"]
            assert [message["content"] for message in requests[1]["messages"] if message["role"] == "user"] == [
                humans[0].content, humans[1].content]
            assert "合成工作 A" not in second.notice_json and "合成工作 B" not in second.notice_json
            state = graph.get_state(config)
            assert not state.next and not state.tasks and not state.interrupts
            assert _assert_pair(state, second_context) == second
            saved_messages = [message.model_dump() for message in state.values["messages"]]
            assert [message.type for message in state.values["messages"]] == ["human", "ai", "human", "ai"]
            assert [message.model_dump() for message in state.values["messages"]
                    if isinstance(message, HumanMessage)] == original_humans
            # Every persisted root carrying a boundary must carry its exact AI message too.
            paired_checkpoints = 0
            for persisted in graph.get_state_history(config):
                if persisted.values.get("jd_model_view") is not None:
                    _assert_pair(persisted, second_context)
                    paired_checkpoints += 1
            assert paired_checkpoints >= 2
        assert len(requests) == 2 and all(body.closed for body in bodies)
        with _graph(model) as reopened:
            restored = read_closed_model_view(reopened, document_id=current.document_id,
                dataset_id=codec.dataset_id, run_id=second_context.run_id)
            assert restored == second
            state = reopened.get_state(config)
            assert [message.model_dump() for message in state.values["messages"]] == saved_messages
            assert _assert_pair(state, second_context) == second
        assert len(requests) == 2, "Read-only reopening must never invoke the agent or HTTP client."
        assert store.read_current(current.document_id).revision_id == current.revision_id
    assert [message.model_dump() for message in humans] == original_humans


def test_missing_terminal_event_keeps_previous_pg_boundary_and_reopen_does_not_retry(monkeypatch, store, engine):
    current = store.read_current(store.create_document(uuid4(), "合成未完成回覆通知"))
    history = NoticeHistoryReader(engine)
    codec = ReferenceCodec(b"synthetic-notice-context-pg-key-32", str(uuid4()))
    first_context = _context(history, codec, current.document_id)
    config = {"configurable": {"thread_id": current.document_id}}
    original = HumanMessage(id="human-" + str(uuid4()), content="完整第一輪原話")
    next_human = HumanMessage(id="human-" + str(uuid4()), content="第二輪原話仍要保留\n不可冒稱回覆完成")
    originals = [deepcopy(message.model_dump()) for message in (original, next_human)]
    with _offline_model(monkeypatch, ["complete", "missing_stop"]) as (model, requests, bodies):
        with _graph(model) as graph:
            graph.invoke({"messages": [original]}, config, context=first_context, durability="sync")
            first = read_closed_model_view(graph, document_id=current.document_id,
                dataset_id=codec.dataset_id, run_id=first_context.run_id)
            current, _, _ = _purpose(store, current, "人工已保存而模型回覆尚未完成")
            second_context = _context(history, codec, current.document_id, first)
            with pytest.raises(ConsultantModelError) as failure:
                graph.invoke({"messages": [next_human]}, config, context=second_context, durability="sync")
            assert failure.value.code == str(failure.value) == "incomplete_model_response"
            assert _notice(requests[1])["turn_start"]["manual_change_count"] == 1
            assert [message["content"] for message in requests[1]["messages"] if message["role"] == "user"] == [
                original.content, next_human.content]
            with pytest.raises(ConsultantContextError, match="^consultant_checkpoint_unconfirmed$"):
                read_closed_model_view(graph, document_id=current.document_id,
                    dataset_id=codec.dataset_id, run_id=second_context.run_id)
            latest = graph.get_state(config, subgraphs=True)
            assert latest.next or latest.tasks
            assert _assert_pair(latest, first_context) == first
            assert [message.model_dump() for message in latest.values["messages"]
                    if isinstance(message, HumanMessage)] == originals
            assert len([message for message in latest.values["messages"] if isinstance(message, AIMessage)]) == 1
        assert len(requests) == 2 and all(body.closed for body in bodies)
        with _graph(model) as reopened:
            latest = reopened.get_state(config, subgraphs=True)
            assert _assert_pair(latest, first_context) == first
            assert first.revision_number == 1 and current.revision_number == 2
            assert [message.model_dump() for message in latest.values["messages"]
                    if isinstance(message, HumanMessage)] == originals
            with pytest.raises(ConsultantContextError, match="^consultant_checkpoint_unconfirmed$"):
                read_closed_model_view(reopened, document_id=current.document_id,
                    dataset_id=codec.dataset_id, run_id=second_context.run_id)
        assert len(requests) == 2, "An unfinished checkpoint is observed, never replayed by this test."
