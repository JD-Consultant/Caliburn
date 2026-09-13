"""Real native owner + PG/Saver + ASGI whole-run changes, fixed offline SDK SSE.

The transport is MockTransport and no provider can be contacted. These are
TestClient ASGI requests, not a socket server, browser or natural-model eval.
Only the existing explicit 55436 database/runtime schema is used: no setup,
deletion, FakeAuthority, new service process or production configuration.
"""

from copy import deepcopy
import os
from threading import Event
from uuid import UUID, uuid4

from langchain_core.messages import HumanMessage
import pytest

from jd_relational.generated.chat_http import ChatRunChangePage, ChatRunState
from jd_relational.generated.reads import ChangeReadPage
from jd_relational.generated.results import MutationResult
from jd_relational.run_change_reads import RunChangeReadService
from test_ai_runtime_postgres import _offline_model, _runtime, _read, _create, _final
from test_chat_api import assert_result
from test_chat_api_postgres import http_runtime, current_page, wait_terminal
from test_manual_runtime_postgres import counts
from test_storage_postgres import engine


pytestmark = pytest.mark.skipif(os.environ.get("JD_RELATIONAL_TEST_DB") != "1",
    reason="explicit isolated PostgreSQL test opt-in required")


def run_changes(client, path, *, cursor=None):
    return assert_result(client.get(path, params={} if cursor is None else {"cursor": cursor}), ChatRunChangePage)


def counted_execute(monkeypatch, owner):
    actual, calls = owner.storage.execute, []

    def execute(intent):
        calls.append((intent.operation_id, intent.origin, intent.ai_run_id))
        return actual(intent)

    monkeypatch.setattr(owner.storage, "execute", execute)
    return calls


def fixed_messages(graph, document):
    # Pin after observing latest; do not treat latest pending-writes overlay as closure.
    latest = graph.get_state({"configurable": {"thread_id": document}}, subgraphs=True)
    fixed = graph.get_state(latest.config, subgraphs=True)
    assert not fixed.tasks and not fixed.next
    return deepcopy(fixed.values["messages"])


def test_ai_create_whole_run_equals_original_operation_and_stays_fixed_after_manual_change(monkeypatch, engine):
    with _offline_model(monkeypatch, [_read, _create, _final]) as (model, requests):
        with _runtime(engine, model) as (runtime, owner, graph):
            document = owner.create_document(uuid4(), "合成整輪變更 API 新增任務")
            writes = counted_execute(monkeypatch, owner)
            run, text = str(uuid4()), "收到通知後檢查約定設備；先隔離、留檢查記錄並交接異常。"
            start_path = f"/api/documents/{document}/chat/runs"
            run_path = start_path + "/" + run
            changes_path = run_path + "/changes"
            with http_runtime(runtime) as client:
                initial = current_page(client, document)
                response = client.post(start_path, json={"run_id": run, "text": text,
                    "expected_jd_revision_ref": initial["revision_ref"]})
                assert response.status_code in {200, 202}, response.text
                state = wait_terminal(client, run_path)
                assert state["run_status"] == "completed" and state["jd_effects"]["state"] == "settled"
                result, = state["jd_effects"]["results"]
                assert result["status"] == "committed"
                current = current_page(client, document)
                whole = run_changes(client, changes_path)
                assert whole["dataset_id"] == runtime.codec.dataset_id
                assert whole["document_id"] == document and whole["run_id"] == run
                assert whole["effects_state"] == "settled" and whole["continuity"] == "continuous"
                assert whole["captured_operation_count"] == 1 and whole["total_changes"] == 4
                assert not whole["has_more"] and whole["start_index"] == 0
                assert whole["base_revision_ref"] == initial["revision_ref"]
                assert whole["result_revision_ref"] == current["revision_ref"]
                one = assert_result(client.post(f"/api/documents/{document}/jd/changes/read",
                    json={"change_ref": result["change_ref"], "cursor": None}), ChangeReadPage)
                assert not one["has_more"] and one["total_changes"] == 4
                assert whole["records"] == one["records"]
                assert whole["total_records"] == one["total_records"]
                assert whole["base_revision_ref"] == one["base_revision_ref"]
                assert whole["result_revision_ref"] == one["result_revision_ref"]
                original_op = runtime.codec.resolve(result["operation_ref"], document_id=document,
                    roles={"operation"}, purposes={"observation"})
                capture = runtime.codec.resolve_run_cursor(whole["capture_ref"], document_id=document, run_id=run)
                assert capture.operation_ids == (UUID(original_op.entity_id),) and capture.settled
                native = fixed_messages(graph, document)
                assert [(m.id, m.content) for m in native if isinstance(m, HumanMessage)] == [(run, text)]
                assert counts(engine, document) == (2, 1) and len(requests) == 3 and len(writes) == 1

                field = next(row for row in current["records"] if row["type"] == "field" and row["name"] == "purpose")
                manual = assert_result(client.post(f"/api/documents/{document}/jd/edits", json={
                    "operation_id": str(uuid4()), "base_revision_ref": current["revision_ref"],
                    "command": {"tool": "jd_set_text", "arguments": {"target_field_ref": field["field_ref"],
                        "text": "後續人工更正，不屬於原 AI 輪次", "basis_refs": []}}}), MutationResult)
                assert manual["status"] == "committed"
                latest = current_page(client, document)
                assert latest["revision_ref"] != whole["result_revision_ref"]
                for _ in range(2):
                    assert run_changes(client, changes_path) == whole
                assert fixed_messages(graph, document) == native
                assert counts(engine, document) == (3, 2)
                assert len(requests) == 3 and [origin for _, origin, _ in writes] == ["ai", "manual"]


def test_pure_interview_whole_run_is_none_and_does_not_create_jd_revision(monkeypatch, engine):
    with _offline_model(monkeypatch, [_final]) as (model, requests):
        with _runtime(engine, model) as (runtime, owner, graph):
            document = owner.create_document(uuid4(), "合成整輪變更 API 純訪談")
            writes = counted_execute(monkeypatch, owner)
            run, text = str(uuid4()), "  先補充實際工作背景；本輪不需要改稿。\r\n😀  "
            start_path = f"/api/documents/{document}/chat/runs"
            run_path = start_path + "/" + run
            with http_runtime(runtime) as client:
                initial = current_page(client, document)
                response = client.post(start_path, json={"run_id": run, "text": text,
                    "expected_jd_revision_ref": initial["revision_ref"]})
                assert response.status_code in {200, 202}, response.text
                state = wait_terminal(client, run_path)
                assert state["run_status"] == "completed" and state["input_state"] == "saved"
                assert state["jd_effects"] == {"state": "settled", "results": []}
                whole = run_changes(client, run_path + "/changes")
                assert whole["effects_state"] == "settled" and whole["continuity"] == "none"
                assert whole["captured_operation_count"] == whole["total_changes"] == whole["total_records"] == 0
                assert whole["base_revision_ref"] is None and whole["result_revision_ref"] is None
                assert whole["records"] == [] and not whole["has_more"] and whole["next_cursor"] is None
                assert current_page(client, document)["revision_ref"] == initial["revision_ref"]
                messages = fixed_messages(graph, document)
                assert [(m.id, m.content) for m in messages if isinstance(m, HumanMessage)] == [(run, text)]
                assert run_changes(client, run_path + "/changes") == whole
                assert fixed_messages(graph, document) == messages
                assert counts(engine, document) == (1, 0) and len(requests) == 1 and not writes


def test_active_capture_pages_keep_first_commit_and_unconfirmed_state_after_second_commit(monkeypatch, engine):
    # A supported page-budget injection changes pagination only. Every capture,
    # snapshot, record, scope and signature still comes from the actual service.
    monkeypatch.setattr("jd_relational.chat_service.RunChangeReadService",
        lambda history, codec: RunChangeReadService(history, codec, page_bytes=4096))
    entered, release = Event(), Event()

    def held_second_create(payload):
        entered.set()
        assert release.wait(15), "bounded synthetic second model reply must be released"
        return _create(payload)

    with _offline_model(monkeypatch, [_read, _create, _read, held_second_create, _final]) as (model, requests):
        with _runtime(engine, model) as (runtime, owner, graph):
            document = owner.create_document(uuid4(), "合成進行中整輪固定分頁")
            writes = counted_execute(monkeypatch, owner)
            run = str(uuid4())
            start_path = f"/api/documents/{document}/chat/runs"
            run_path = start_path + "/" + run
            changes_path = run_path + "/changes"
            with http_runtime(runtime) as client:
                initial = current_page(client, document)
                try:
                    response = client.post(start_path, json={"run_id": run,
                        "text": "合成情境：本輪分兩次建立設備檢查工作，確認每次保存與分頁範圍。",
                        "expected_jd_revision_ref": initial["revision_ref"]})
                    assert response.status_code in {200, 202}, response.text
                    assert entered.wait(5), "the second write response has not been released"
                    assert counts(engine, document) == (2, 1) and len(writes) == 1
                    first = run_changes(client, changes_path)
                    assert first["effects_state"] == "unconfirmed" and first["continuity"] == "continuous"
                    assert first["captured_operation_count"] == 1 and first["total_changes"] == 4
                    assert first["has_more"] and first["next_cursor"]
                    first_end = first["result_revision_ref"]
                    assert first_end == current_page(client, document)["revision_ref"]
                finally:
                    release.set()
                terminal = wait_terminal(client, run_path)
                assert terminal["run_status"] == "completed" and len(terminal["jd_effects"]["results"]) == 2
                assert counts(engine, document) == (3, 2) and len(writes) == 2 and len(requests) == 5
                native = fixed_messages(graph, document)

                # Continuations cannot call inspect_run again or advance the capture.
                inspect = runtime.inspect_run
                def no_new_native_capture(*_args, **_kwargs):
                    pytest.fail("A cursor continuation must not recapture native run state")
                monkeypatch.setattr(runtime, "inspect_run", no_new_native_capture)
                rows, cursor = list(first["records"]), first["next_cursor"]
                try:
                    for _ in range(32):
                        if cursor is None:
                            break
                        page = run_changes(client, changes_path, cursor=cursor)
                        assert page["start_index"] == len(rows)
                        assert page["capture_ref"] == first["capture_ref"]
                        assert page["effects_state"] == "unconfirmed" and page["captured_operation_count"] == 1
                        assert page["base_revision_ref"] == first["base_revision_ref"]
                        assert page["result_revision_ref"] == first_end and page["total_changes"] == 4
                        rows.extend(page["records"]); cursor = page["next_cursor"]
                    assert cursor is None and len(rows) == first["total_records"]
                finally:
                    monkeypatch.setattr(runtime, "inspect_run", inspect)
                fresh = run_changes(client, changes_path)
                assert fresh["effects_state"] == "settled" and fresh["captured_operation_count"] == 2
                assert fresh["total_changes"] == 8 and fresh["capture_ref"] != first["capture_ref"]
                assert fresh["base_revision_ref"] == first["base_revision_ref"]
                assert fresh["result_revision_ref"] != first_end
                assert fixed_messages(graph, document) == native
                assert counts(engine, document) == (3, 2) and len(writes) == 2 and len(requests) == 5
