"""Real chat HTTP/owner/PG/Saver, real SDK with fixed offline SSE transport.

TestClient is real ASGI HTTP, not a socket server or browser. Existing public
test database/Saver schema only; no setup, deletion, FakeAuthority or provider.
"""

from contextlib import asynccontextmanager, contextmanager
from copy import deepcopy
import os
from time import monotonic, sleep
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
import httpx2
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
import pytest

from jd_relational.catalog_service import CatalogService
from jd_relational.chat_api import ChatServices
from jd_relational.chat_history import ChatHistoryCodec, ChatHistoryService
from jd_relational.chat_service import ChatService
from jd_relational.configured_api import create_configured_api
from jd_relational.generated.chat_http import ChatHistoryPage, ChatProblem, ChatRunState
from jd_relational.generated.reads import ChangeReadPage, ReadPage
from jd_relational.generated.results import MutationResult
from jd_relational.manual_service import ManualService
from test_ai_runtime_postgres import _offline_model, _runtime, _read, _create, _final
from test_chat_api import ORIGIN, HEADER, assert_result
from test_manual_runtime_postgres import counts
from test_storage_postgres import engine


pytestmark = pytest.mark.skipif(os.environ.get("JD_RELATIONAL_TEST_DB") != "1",
    reason="explicit isolated PostgreSQL test opt-in required")


@contextmanager
def http_runtime(runtime):
    manual = ManualService(runtime.owner, runtime.history, runtime.codec, wait_timeout=5)
    history = ChatHistoryService(runtime.checkpoints,
        ChatHistoryCodec(b"synthetic-chat-pg-history-key-32!!", runtime.codec.dataset_id))
    chat = ChatService(runtime, manual, history)

    @asynccontextmanager
    async def resources():
        yield ChatServices(runtime.reads, runtime.changes, manual,
            CatalogService(runtime.owner, runtime.codec.dataset_id), chat)

    app = create_configured_api(resources, allowed_origins=(ORIGIN,),
        dataset_id=runtime.codec.dataset_id, with_chat=True)
    with TestClient(app, base_url="http://localhost",
        headers={"Origin": ORIGIN, HEADER: runtime.codec.dataset_id}) as client:
        yield client


def current_page(client, document, *, target=None):
    response = client.post(f"/api/documents/{document}/jd/read",
        json={"view": "history" if target else "current", "target_ref": target, "cursor": None})
    page = assert_result(response, ReadPage)
    assert page["has_more"] is False  # These bounded synthetic documents fit one complete page.
    return page


def wait_terminal(client, path):
    deadline = monotonic() + 15
    while monotonic() < deadline:
        state = assert_result(client.get(path), ChatRunState)
        if state["run_status"] not in {"running", "closing"}:
            return state
        sleep(0.01)
    pytest.fail("Actual HTTP run failed to reach a terminal observation within the test deadline")


def test_http_pure_interview_saves_original_native_conversation_without_jd_revision(monkeypatch, engine):
    with _offline_model(monkeypatch, [_final]) as (model, requests):
        with _runtime(engine, model) as (runtime, owner, graph):
            document = owner.create_document(uuid4(), "合成 HTTP 純訪談")
            run = str(uuid4())
            original_text = "  原話\r\n我先說明工作背景，這輪先不改稿。😀  "
            path = f"/api/documents/{document}/chat/runs"
            before = counts(engine, document)
            with http_runtime(runtime) as client:
                base = current_page(client, document)
                assert before == (1, 0)
                response = client.post(path, json={"run_id": run, "text": original_text,
                    "expected_jd_revision_ref": base["revision_ref"]})
                assert response.status_code in {200, 202}, response.text
                assert response.headers["Location"] == path + "/" + run
                state = wait_terminal(client, path + "/" + run)
                assert state["run_status"] == "completed" and state["input_state"] == "saved"
                assert state["jd_effects"] == {"state": "settled", "results": []}
                assert state["response_message_id"] and not state["write_state"]["write_blocked"]
                snapshot = graph.get_state({"configurable": {"thread_id": document}}, subgraphs=True)
                assert not snapshot.tasks and not snapshot.next
                native_messages = deepcopy(snapshot.values["messages"])
                assert [(m.id, m.content) for m in native_messages if isinstance(m, HumanMessage)] == [(run, original_text)]
                page = assert_result(client.get(f"/api/documents/{document}/chat/messages"), ChatHistoryPage)
                assert page["next_cursor"] is None and len(page["messages"]) == 2
                assert page["messages"][0] == {"message_id": run, "run_id": run, "role": "user", "text": original_text}
                assert page["messages"][1]["message_id"] == state["response_message_id"]
                assert page["messages"][1]["role"] == "assistant" and page["messages"][1]["text"]
                for _ in range(2):
                    assert assert_result(client.get(path + "/" + run), ChatRunState) == state
                unknown = assert_result(client.get(path + "/" + str(uuid4())), ChatRunState)
                assert unknown["run_status"] == "not_found" and unknown["input_state"] == "unconfirmed"
                missing = client.get(f"/api/documents/{uuid4()}/chat/runs/{run}")
                assert assert_result(missing, ChatProblem, 404)["code"] == "document_missing"
                assert graph.get_state(snapshot.config, subgraphs=True) == snapshot
                assert counts(engine, document) == before and len(requests) == 1


def test_http_ai_edit_results_match_original_receipt_change_and_history_after_manual_head_advance(monkeypatch, engine):
    with _offline_model(monkeypatch, [_read, _create, _final]) as (model, requests):
        with _runtime(engine, model) as (runtime, owner, graph):
            document = owner.create_document(uuid4(), "合成 HTTP AI 新增工作")
            run, original_text = str(uuid4()), "收到通知後檢查約定設備，先隔離、留檢查記錄並交接異常。"
            path = f"/api/documents/{document}/chat/runs"
            with http_runtime(runtime) as client:
                initial = current_page(client, document)
                first_revision = owner.storage.read_current(document).revision_id
                response = client.post(path, json={"run_id": run, "text": original_text,
                    "expected_jd_revision_ref": initial["revision_ref"]})
                assert response.status_code in {200, 202}, response.text
                assert response.headers["Location"] == path + "/" + run
                state = wait_terminal(client, path + "/" + run)
                assert state["run_status"] == "completed" and state["input_state"] == "saved"
                assert state["jd_effects"]["state"] == "settled" and len(state["jd_effects"]["results"]) == 1
                result = state["jd_effects"]["results"][0]
                assert result["status"] == "committed" and result["receipt_durability"] == "confirmed"
                operation = runtime.codec.resolve(result["operation_ref"], document_id=document,
                    roles={"operation"}, purposes={"observation"})
                receipt = owner.storage.get_operation(document, UUID(operation.entity_id))
                assert receipt.origin == "ai" and receipt.ai_run_id == run
                assert receipt.body.command_kind == "jd_create_task" and receipt.base_revision_id == first_revision
                original_result = runtime.codec.resolve(result["result_revision_ref"], document_id=document,
                    roles={"revision"}, purposes={"observation"})
                assert str(receipt.result_revision_id) == original_result.revision_id
                current = owner.storage.read_current(document)
                assert current.revision_id == receipt.result_revision_id and current.revision_number == 2
                assert len(current.domain["tasks"]) == 1
                assert {row["text"] for row in current.domain["details"].values()} == {"檢查記錄", "異常交接", "先確認隔離再檢查"}
                assert counts(engine, document) == (2, 1)
                change_path = f"/api/documents/{document}/jd/changes/read"
                changes = assert_result(client.post(change_path,
                    json={"change_ref": result["change_ref"], "cursor": None}), ChangeReadPage)
                assert not changes["has_more"] and changes["origin"] == "ai" and changes["total_changes"] == 4
                assert runtime.codec.resolve(changes["base_revision_ref"], document_id=document,
                    roles={"revision"}, purposes={"history"}).revision_id == str(first_revision)
                assert runtime.codec.resolve(changes["result_revision_ref"], document_id=document,
                    roles={"revision"}, purposes={"history"}).revision_id == str(receipt.result_revision_id)
                history = assert_result(client.get(f"/api/documents/{document}/chat/messages"), ChatHistoryPage)
                assert [(row["role"], row["run_id"]) for row in history["messages"]] == [("user", run), ("assistant", run)]
                assert history["messages"][0]["text"] == original_text
                assert history["messages"][1]["message_id"] == state["response_message_id"]
                # The contract states the initial page holds the LATEST messages and
                # next_cursor asks for an older page, each page chronological. A limit
                # of one therefore starts at the newest message, and paging back with
                # that cursor reaches the older one.
                anchored = assert_result(client.get(f"/api/documents/{document}/chat/messages",
                    params={"limit": 1}), ChatHistoryPage)
                assert anchored["next_cursor"] and anchored["messages"] == history["messages"][-1:]
                older = assert_result(client.get(f"/api/documents/{document}/chat/messages",
                    params={"limit": 1, "cursor": anchored["next_cursor"]}), ChatHistoryPage)
                assert older["messages"] == history["messages"][:1]
                assert older["anchor"] == anchored["anchor"], "paging back must keep the same anchor"
                saved_native = deepcopy(graph.get_state({"configurable": {"thread_id": document}}).values["messages"])

                # Same public composition, real manual owner; no fixture authority or direct SQL write.
                before_manual = current_page(client, document)
                purpose = next(row for row in before_manual["records"] if row["type"] == "field" and row["name"] == "purpose")
                manual = assert_result(client.post(f"/api/documents/{document}/jd/edits", json={
                    "operation_id": str(uuid4()), "base_revision_ref": before_manual["revision_ref"],
                    "command": {"tool": "jd_set_text", "arguments": {"target_field_ref": purpose["field_ref"],
                        "text": "後來的人工用途更正", "basis_refs": []}}}), MutationResult)
                assert manual["status"] == "committed" and counts(engine, document) == (3, 2)
                assert assert_result(client.get(path + "/" + run), ChatRunState) == state
                assert assert_result(client.post(change_path,
                    json={"change_ref": result["change_ref"], "cursor": None}), ChangeReadPage) == changes
                historical = current_page(client, document, target=result["result_revision_ref"])
                assert not any(row.get("value") == "後來的人工用途更正" for row in historical["records"])
                latest_history = assert_result(client.get(f"/api/documents/{document}/chat/messages"), ChatHistoryPage)
                # Manual admission/cleanup legitimately creates a newer native
                # root checkpoint; a fresh page anchor need not stay identical.
                assert {key: item for key, item in latest_history.items() if key != "anchor"} == {
                    key: item for key, item in history.items() if key != "anchor"}
                continued = assert_result(client.get(f"/api/documents/{document}/chat/messages",
                    params={"cursor": anchored["next_cursor"], "limit": 1}), ChatHistoryPage)
                assert continued["anchor"] == anchored["anchor"] and continued["next_cursor"] is None
                # Same cursor, same older page: continuing later never re-reads the
                # newest message, and the older page is where the cursor pointed.
                assert continued["messages"] == history["messages"][:1]
                assert graph.get_state({"configurable": {"thread_id": document}}).values["messages"] == saved_native
                assert len(requests) == 3 and len(runtime.history.read_run_operations(document, run)) == 1


def test_http_failed_final_model_keeps_saved_input_and_confirmed_committed_jd(monkeypatch, engine):
    marker = "SyntheticPrivateFinalModelFailure"

    def failed_final(payload):
        assert payload["tools"] == [] and payload["tool_choice"] == "none"
        raise httpx2.ReadError(marker)

    # Preserve the real JD write first, then use successful read-only model
    # turns to reach the reserved 64th request.  The final failure therefore
    # exercises the Runtime no-tools finalization path, not an ordinary model
    # request that happened to be the last fixture item.
    plan = [_read, _create, *([_read] * 61), failed_final]
    with _offline_model(monkeypatch, plan, allow_final_no_tools=True) as (model, requests):
        with _runtime(engine, model) as (runtime, owner, graph):
            document = owner.create_document(uuid4(), "合成 HTTP 已保存但最後回覆失敗")
            run, text = str(uuid4()), "建立約定設備檢查工作，先確認隔離並保留檢查及交接結果。"
            path = f"/api/documents/{document}/chat/runs"
            with http_runtime(runtime) as client:
                base = current_page(client, document)
                response = client.post(path, json={"run_id": run, "text": text,
                    "expected_jd_revision_ref": base["revision_ref"]})
                assert response.status_code in {200, 202}, response.text
                state = wait_terminal(client, path + "/" + run)
                assert state["run_status"] == "failed" and state["input_state"] == "saved"
                assert state["response_message_id"] is None and not state["write_state"]["write_blocked"]
                assert state["jd_effects"]["state"] == "settled" and len(state["jd_effects"]["results"]) == 1
                result = state["jd_effects"]["results"][0]
                assert result["status"] == "committed" and result["receipt_durability"] == "confirmed"
                assert result["effect"] == "changed" and result["change_ref"] and result["error"] is None
                operation = runtime.codec.resolve(result["operation_ref"], document_id=document,
                    roles={"operation"}, purposes={"observation"})
                saved = owner.storage.get_operation(document, UUID(operation.entity_id))
                assert saved.status == "committed" and saved.ai_run_id == run and saved.origin == "ai"
                current = owner.storage.read_current(document)
                assert current.revision_number == 2 and current.revision_id == saved.result_revision_id
                assert len(current.domain["tasks"]) == 1 and len(current.domain["details"]) == 3
                assert counts(engine, document) == (2, 1) and len(requests) == 64
                history = assert_result(client.get(f"/api/documents/{document}/chat/messages"), ChatHistoryPage)
                assert history["messages"] == [{"message_id": run, "run_id": run, "role": "user", "text": text}]
                native = graph.get_state({"configurable": {"thread_id": document}}, subgraphs=True)
                assert not native.next and not native.tasks and native.values["jd_ai_run"]["status"] == "failed"
                messages = native.values["messages"]
                assert any(isinstance(message, AIMessage) and message.tool_calls for message in messages)
                assert any(isinstance(message, ToolMessage) for message in messages)
                assert not any(isinstance(message, AIMessage) and not message.tool_calls for message in messages)
                assert all(marker not in str(message.content) for message in messages)
                again = client.get(path + "/" + run)
                assert assert_result(again, ChatRunState) == state and marker not in again.text
                assert len(requests) == 64 and counts(engine, document) == (2, 1)
