"""Real JD SQL + native PG Saver + agent/SDK, with offline synthetic replies only.

The imported FakeAuthority prepares manual fixture edits; it is not evidence of
AI writer admission. No Saver setup, persisted-data cleanup, real provider or
automatic graph replay occurs here. Opt in only to the existing test database.
"""

from contextlib import contextmanager
from copy import deepcopy
from hashlib import sha256
import asyncio
import json
import os
from uuid import uuid4

import httpx
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
import pytest

from jd_relational.consultant_context import (
    ConsultantContext, ConsultantContextError, build_consultant_node,
    checked_model_view, read_closed_model_view,
)
from jd_relational.consultant_model import (
    OPENROUTER_HEADERS,
    ConsultantModelError,
    create_consultant_model,
)
from jd_relational.notice_history import NoticeHistoryReader
from jd_relational.references import ReferenceCodec
from jd_relational.runtime_checkpoints import build_document_graph
from jd_relational.storage.service import JdStorage
from support.openrouter_replies import reply as _reply, system_blocks, truncated as _truncated
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
    """Give each response its own id, just as separate SDK replies do.

    `incomplete` is the provider's own way of reporting a reply cut off at the
    output ceiling; it must never read as a short success.
    """
    identity = f"synthetic_pg_{number}"
    if mode == "complete":
        return _reply(identity, text=f"第 {number} 次合成回覆")
    return _truncated(identity)


@contextmanager
def _offline_model(monkeypatch, modes):
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")
    requests = []

    def receive(request):
        # MockTransport receives the real SDK request; it never opens a socket.
        assert request.url.host == "openrouter.ai"
        assert request.headers["authorization"] == "Bearer synthetic-pg-not-a-key"
        assert len(requests) < len(modes), "No hidden model retry or replay is allowed."
        payload = json.loads(request.content)
        assert payload["parallel_tool_calls"] is False
        assert payload["provider"] == {"only": ["OpenAI"], "order": ["OpenAI"],
            "allow_fallbacks": False, "require_parameters": True}
        requests.append(payload)
        return httpx.Response(200, json=_data(modes[len(requests) - 1], len(requests)),
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
            model = create_consultant_model(api_key="synthetic-pg-not-a-key",
                                            http_client=client, async_http_client=async_client)
            yield model, requests, []
        finally:
            asyncio.run(async_client.aclose())


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


def _context(history, codec, document_id, previous=None, *, run_id=None):
    baseline = previous.boundary if previous else None
    return ConsultantContext(codec.dataset_id, document_id, str(uuid4()) if run_id is None else run_id, history, codec,
                             history.read(document_id, baseline))


def _said(item):
    """The employee's words out of one request item, ignoring the block label.

    A Responses input block is typed `input_text` where a saved HumanMessage
    block is typed `text`; the words themselves must be identical.
    """
    content = item["content"]
    if isinstance(content, str):
        return content
    return "".join(block.get("text", "") for block in content)


def _notice(payload):
    notices = []
    for block in system_blocks(payload):
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
    assert reply.response_metadata["status"] == "completed"
    assert reply.usage_metadata["output_tokens"] == 10
    assert _digest(reply.model_dump(mode="json")) == view.response_digest
    assert sha256(view.notice_json.encode()).hexdigest() == view.notice_digest
    return view


def test_real_notice_two_turns_and_pg_reopen_preserve_paired_response_without_replay(monkeypatch, store, engine):
    current = store.read_current(store.create_document(uuid4(), "合成持久顧問通知"))
    current, first_edit, _ = _purpose(store, current, "合成工作 A")
    history = NoticeHistoryReader(engine)
    codec = ReferenceCodec(b"synthetic-notice-context-pg-key-32", str(uuid4()))
    first_context = _context(history, codec, current.document_id, run_id=str(uuid4()))
    config = {"configurable": {"thread_id": current.document_id}}
    humans = [HumanMessage(id=first_context.run_id, content="原始問答\n  保留空白與原話。")]
    with _offline_model(monkeypatch, ["complete", "complete"]) as (model, requests, bodies):
        with _graph(model) as graph:
            graph.invoke({"messages": [humans[0]]}, config, context=first_context, durability="sync")
            first = read_closed_model_view(graph, document_id=current.document_id,
                dataset_id=codec.dataset_id, run_id=first_context.run_id)
            assert first.revision_id == str(current.revision_id) and first.revision_number == 2
            first_notice = _notice(requests[0])
            assert first_notice["turn_start"]["manual_change_count"] == 1
            assert first_notice["turn_start"]["ai_change_count"] == 0
            assert [item for item in requests[0]["messages"] if item.get("role") == "user"] == [
                {"role": "user", "content": humans[0].content}]
            first_ref = codec.resolve(first_notice["turn_start"]["events"][0]["change_ref"],
                document_id=current.document_id, roles={"change"}, purposes={"observation"})
            assert first_ref.entity_id == str(first_edit.operation_id)
            current, changed, _ = _purpose(store, current, "合成工作 B")
            current, reverted, _ = _purpose(store, current, "合成工作 A")
            unchanged = intent_for(store, current, "jd_set_text", {
                "target_field_ref": "profile.purpose", "text": "合成工作 A", "basis_refs": []})
            assert store.execute(unchanged).status == "no_change"
            second_context = _context(history, codec, current.document_id, first, run_id=str(uuid4()))
            humans.append(HumanMessage(id=second_context.run_id,
                content=[{"type": "text", "text": "先更正再改回。"}]))
            original_humans = [deepcopy(message.model_dump()) for message in humans]
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
            assert [item["role"] for item in requests[1]["messages"] if item.get("role")] == [
                "system", "user", "assistant", "user"]
            assert [_said(item) for item in requests[1]["messages"] if item.get("role") == "user"] == [
                _said({"content": humans[0].content}), _said({"content": humans[1].content})]
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
        assert len(requests) == 2
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
    first_context = _context(history, codec, current.document_id, run_id=str(uuid4()))
    config = {"configurable": {"thread_id": current.document_id}}
    original = HumanMessage(id=first_context.run_id, content="完整第一輪原話")
    with _offline_model(monkeypatch, ["complete", "incomplete"]) as (model, requests, bodies):
        with _graph(model) as graph:
            graph.invoke({"messages": [original]}, config, context=first_context, durability="sync")
            first = read_closed_model_view(graph, document_id=current.document_id,
                dataset_id=codec.dataset_id, run_id=first_context.run_id)
            current, _, _ = _purpose(store, current, "人工已保存而模型回覆尚未完成")
            second_context = _context(history, codec, current.document_id, first, run_id=str(uuid4()))
            next_human = HumanMessage(id=second_context.run_id,
                content="第二輪原話仍要保留\n不可冒稱回覆完成")
            originals = [deepcopy(message.model_dump()) for message in (original, next_human)]
            with pytest.raises(ConsultantContextError) as failure:
                graph.invoke({"messages": [next_human]}, config, context=second_context, durability="sync")
            # The reply is rejected one layer higher now: the provider reports an
            # unfinished reply as `incomplete` status rather than a truncated
            # stream, so the consultant node is what refuses it.
            assert failure.value.code == str(failure.value) == "incomplete_consultant_response"
            assert _notice(requests[1])["turn_start"]["manual_change_count"] == 1
            assert [_said(item) for item in requests[1]["messages"] if item.get("role") == "user"] == [
                _said({"content": original.content}), _said({"content": next_human.content})]
            with pytest.raises(ConsultantContextError, match="^consultant_checkpoint_unconfirmed$"):
                read_closed_model_view(graph, document_id=current.document_id,
                    dataset_id=codec.dataset_id, run_id=second_context.run_id)
            latest = graph.get_state(config, subgraphs=True)
            assert latest.next or latest.tasks
            assert _assert_pair(latest, first_context) == first
            assert [message.model_dump() for message in latest.values["messages"]
                    if isinstance(message, HumanMessage)] == originals
            assert len([message for message in latest.values["messages"] if isinstance(message, AIMessage)]) == 1
        assert len(requests) == 2
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
