"""Offline SDK/helper checks only; no listener, host bootstrap or PostgreSQL."""

import asyncio
import json
from types import SimpleNamespace
from uuid import uuid4

from langchain_core.messages import HumanMessage, ToolMessage
from langchain_anthropic.chat_models import AnthropicConnectionError
import pytest

from support import ui_chat_server as helper
from support import ui_response_gate_server as original
from jd_relational.consultant_tools import build_jd_tools


@pytest.fixture
def target():
    path = helper.ROOT / ".research-tmp" / f"jd-chat-helper-unit-{uuid4().hex}"
    path.mkdir()
    return path


def test_fixed_fixture_delegates_existing_scope_checks_and_initialization():
    assert helper.prepare is original.prepare
    assert helper.initialize is original.initialize
    assert helper.fixture_file is original.fixture_file
    assert helper.manifest is original.manifest
    assert helper.directory is original.directory
    assert helper.valid_port is original.valid_port
    with pytest.raises(ValueError, match="invalid_probe_directory"):
        helper.directory(helper.ROOT / ".research-tmp" / "jd-ui-gate-not-a-uuid")


def test_real_sdk_fixed_plan_reads_live_ref_creates_complete_task_and_then_two_final_messages(target):
    evidence = helper.Evidence(target)
    with helper.offline_model(evidence) as model:
        bound = model.bind_tools(build_jd_tools(), parallel_tool_calls=False, strict=True)
        messages = [HumanMessage(content="synthetic-private-employee-input")]
        first = bound.invoke(messages)
        assert len(first.tool_calls) == 1 and first.tool_calls[0]["name"] == "jd_read"
        page = {"view": "current", "access": "current", "has_more": False, "records": [
            {"type": "container", "child_kind": "task", "owner_ref": None, "container_ref": "live-container-ref"}]}
        messages.extend([first, ToolMessage(content=json.dumps(page), tool_call_id=first.tool_calls[0]["id"])])
        second = bound.invoke(messages)
        call = second.tool_calls[0]
        assert call["name"] == "jd_create_task"
        assert call["args"]["container_ref"] == "live-container-ref"
        assert len(call["args"]["outcomes"]) == 2 and len(call["args"]["requirements"]) == 1
        messages.extend([second, ToolMessage(content=json.dumps({"status": "committed", "receipt_durability": "confirmed"}),
                                             tool_call_id=call["id"])])
        third = bound.invoke(messages)
        assert not third.tool_calls and helper.FIRST_REPLY in str(third.content)
        assert third.response_metadata["stop_reason"] == "end_turn" and third.usage_metadata
        messages.extend([third, HumanMessage(content="synthetic-private-second-input")])
        fourth = bound.invoke(messages)
        assert not fourth.tool_calls and helper.SECOND_REPLY in str(fourth.content)
        assert fourth.response_metadata["stop_reason"] == "end_turn"
    result = evidence.snapshot()
    assert result["model_request_count"] == 4
    assert [item["tool"] for item in result["model_requests"]] == ["jd_read", "jd_create_task", None, None]
    assert result["closed_model_bodies"] == 4
    saved = (target / "chat.observations.json").read_text(encoding="utf-8")
    for private in ["synthetic-private-employee-input", "synthetic-private-second-input", "live-container-ref", helper.FIRST_REPLY]:
        assert private not in saved


def test_extra_model_request_fails_without_new_network_or_hidden_retry(target):
    evidence = helper.Evidence(target)
    with helper.offline_model(evidence) as model:
        bound = model.bind_tools(build_jd_tools(), parallel_tool_calls=False, strict=True)
        # Exhausting the fixed plan is a failure, never another canned success.
        evidence._next_request = 4
        with pytest.raises(AnthropicConnectionError):
            bound.invoke([HumanMessage(content="private")])
    assert evidence.snapshot()["model_request_count"] == 1
    assert evidence.snapshot()["model_requests"][0]["response"] == "fixture_rejected"


def test_wrong_second_step_read_page_stops_instead_of_inventing_location(target):
    evidence = helper.Evidence(target)
    with helper.offline_model(evidence) as model:
        bound = model.bind_tools(build_jd_tools(), parallel_tool_calls=False, strict=True)
        first = bound.invoke([HumanMessage(content="private")])
        with pytest.raises(AnthropicConnectionError):
            bound.invoke([HumanMessage(content="private"), first,
                          ToolMessage(content='{"view":"wrong"}', tool_call_id=first.tool_calls[0]["id"])])
    assert evidence.snapshot()["model_request_count"] == 2
    assert evidence.snapshot()["model_requests"][1]["response"] == "fixture_rejected"


def test_existing_serve_marker_refuses_replaying_fixture_before_opening_host(target, monkeypatch):
    monkeypatch.setattr(helper, "manifest", lambda _: {"fixture": "synthetic"})
    (target / "serve.ready.json").write_text("{}")
    with pytest.raises(ValueError, match="probe_already_served"):
        helper.serve(target)


def test_stop_requires_exact_ready_process_manifest_and_preserves_request(target, monkeypatch):
    monkeypatch.setattr(helper, "manifest", lambda _: {"fixture": "synthetic"})
    with pytest.raises(ValueError, match="probe_not_ready"):
        helper.stop(target)
    (target / "serve.ready.json").write_text(json.dumps({"pid": 123, "status": "ready"}))
    helper.stop(target)
    assert (target / "stop.request").exists()
    with pytest.raises(FileExistsError):
        helper.stop(target)


def test_http_and_writer_evidence_record_only_counts_and_identity_without_reading_bodies(target):
    evidence = helper.Evidence(target)
    document, operation, revision, run = str(uuid4()), uuid4(), uuid4(), str(uuid4())
    intent = SimpleNamespace(document_id=document, operation_id=operation, origin="ai", ai_run_id=run)
    result = SimpleNamespace(confirmed=True, status="committed", receipt=SimpleNamespace(result_revision_id=revision))
    evidence.write(intent, result)
    called = []

    async def app(scope, receive, send):
        called.append(scope["path"])

    async def receive():
        raise AssertionError("Metadata observer must never consume the body")

    async def send(value):
        raise AssertionError("This synthetic app does not send")

    for method, suffix in [("POST", "runs"), ("GET", f"runs/{run}"), ("GET", "messages")]:
        asyncio.run(evidence.routes(app, {"type": "http", "method": method,
            "path": f"/api/documents/{document}/chat/{suffix}", "query_string": b"private-query"}, receive, send))
    snapshot = evidence.snapshot()
    assert len(called) == 3
    assert snapshot["http_counts"] == {"POST chat_runs": 1, "GET chat_runs": 1, "GET chat_messages": 1}
    assert snapshot["writer_execute_count"] == 1
    assert snapshot["writes"][0] == {"document_id": document, "operation_id": str(operation), "origin": "ai",
        "run_id": run, "confirmed": True, "status": "committed", "result_revision_id": str(revision)}
    assert "private-query" not in (target / "chat.observations.json").read_text()


def test_http_observer_records_distinct_read_and_state_and_real_send_completion(target):
    evidence = helper.Evidence(target)
    private_origin = b"http://127.0.0.1:3002"
    document = str(uuid4())

    async def scenario():
        for method, suffix in [("POST", "read"), ("GET", "state")]:
            sent = []
            async def app(scope, receive, send):
                await send({"type": "http.response.start", "status": 200,
                    "headers": [(b"access-control-allow-origin", private_origin), (b"x-private", b"private-header")]})
                await send({"type": "http.response.body", "body": b"private-body", "more_body": True})
                await send({"type": "http.response.body", "body": b"private-final-body"})
            async def receive():
                raise AssertionError("Observer must not read body")
            async def original_send(message):
                current = evidence.snapshot()["http_observations"][-1]
                if message["type"] == "http.response.start":
                    assert current["response_start_forwarded"] is False
                else:
                    assert current["response_start_forwarded"] is True
                    assert current["response_body_end_forwarded"] is False
                sent.append(message)
            await evidence.routes(app, {"type": "http", "method": method,
                "path": f"/api/documents/{document}/jd/{suffix}", "query_string": b"private-query",
                "headers": [(b"origin", private_origin)]}, receive, original_send)
            assert len(sent) == 3
    asyncio.run(scenario())
    rows = evidence.snapshot()["http_observations"]
    assert [(row["ordinal"], row["method"], row["route"], row["status"]) for row in rows] == [
        (1, "POST", "jd_read", 200), (2, "GET", "jd_state", 200)]
    for row in rows:
        assert row["response_start_forwarded"] is True
        assert row["response_body_end_forwarded"] is True
        assert row["cors_origin_matches"] is True
        assert type(row["elapsed_ms"]) in (int, float) and row["elapsed_ms"] >= 0
    saved = (target / "chat.observations.json").read_text()
    for private in [document, private_origin.decode(), "private-header", "private-body", "private-final-body", "private-query"]:
        assert private not in saved


@pytest.mark.parametrize("where", ["before_start", "send_start", "send_body"])
def test_http_observer_does_not_claim_failed_send_reached_browser(target, where):
    evidence = helper.Evidence(target)
    original_error = OSError("private-transport-failure")
    async def scenario():
        async def app(scope, receive, send):
            if where == "before_start":
                raise original_error
            await send({"type": "http.response.start", "status": 503,
                "headers": [(b"access-control-allow-origin", b"http://different.invalid")]})
            await send({"type": "http.response.body", "body": b"private-body"})
        async def receive():
            raise AssertionError("Observer must not read body")
        async def send(message):
            if where == "send_start" or message["type"] == "http.response.body":
                raise original_error
        with pytest.raises(OSError) as error:
            await evidence.routes(app, {"type": "http", "method": "GET", "path": "/private-unknown-path",
                "headers": [(b"origin", b"http://127.0.0.1:3002")]}, receive, send)
        assert error.value is original_error
    asyncio.run(scenario())
    row = evidence.snapshot()["http_observations"][0]
    assert row["status"] == (None if where == "before_start" else 503)
    assert row["response_start_forwarded"] is (where == "send_body")
    assert row["response_body_end_forwarded"] is False
    assert row["cors_origin_matches"] is False
    assert row["elapsed_ms"] >= 0
    saved = (target / "chat.observations.json").read_text()
    assert "private-transport-failure" not in saved and "private-unknown-path" not in saved


def test_http_observer_keeps_response_without_origin_or_cors_header_as_unmatched(target):
    evidence = helper.Evidence(target)
    async def app(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b""})
    async def send(message):
        pass
    asyncio.run(evidence.routes(app, {"type": "http", "method": "GET", "path": "/api/documents"}, None, send))
    assert evidence.snapshot()["http_observations"][0]["cors_origin_matches"] is False
