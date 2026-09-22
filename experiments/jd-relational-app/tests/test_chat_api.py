"""Real chat ASGI/native graph/Futures; the SQL receipt port is synthetic.

No provider, DB, process host or browser. Public routes use real ChatService,
ManualService and fixed native ChatHistoryService, not prebuilt success JSON.
"""

from contextlib import asynccontextmanager, contextmanager
from copy import deepcopy
import json
import logging
from threading import Event
from types import SimpleNamespace
from uuid import uuid4

import anyio
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator
from langchain_core.messages import AIMessage
import pytest

from jd_relational.catalog_service import CatalogService
from jd_relational.chat_api import ChatServices
from jd_relational.chat_history import ChatHistoryCodec, ChatHistoryService
from jd_relational.chat_service import ChatService
from jd_relational.configured_api import create_configured_api
from jd_relational.generated.chat_http import ChatHistoryPage, ChatProblem, ChatRunState
from jd_relational.manual_service import ManualService
from jd_relational.references import SignedReference
from test_ai_runtime import make_runtime


ORIGIN = "http://localhost:3100"
PRIVATE = "SyntheticPrivateChatRequestBody"
HEADER = "X-JD-Dataset"


class NeverRead:
    def read(self, *args, **kwargs):
        pytest.fail("This chat-only test must not enter JD read/change ports")


def revision_ref(runtime, document, revision=None):
    return runtime.codec.issue(SignedReference(document_id=document,
        revision_id=str(revision or runtime.owner.storage.read_current(document).revision_id),
        purpose="history", role="revision", kind="revision"))


def assert_result(response, model, status=200):
    assert response.status_code == status, response.text
    value = response.json()
    assert model.model_validate(value, strict=True).model_dump(mode="json") == value
    Draft202012Validator(model.model_json_schema()).validate(value)
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-request-id"] and response.headers["x-content-type-options"] == "nosniff"
    return value


@pytest.fixture
def chat_app(make_runtime, monkeypatch):
    make, releases = make_runtime

    @contextmanager
    def opened(node=None):
        runtime, graph, model_calls = make(node)
        sql_reads, api_calls = [], []

        def empty_sql(document, run, *, limit=96):
            sql_reads.append((document, run))
            return ()

        monkeypatch.setattr(runtime.history, "read_run_operations", empty_sql)
        manual = ManualService(runtime.owner, runtime.history, runtime.codec)
        history = ChatHistoryService(runtime.checkpoints,
            ChatHistoryCodec(b"synthetic-chat-http-history-key-32", runtime.codec.dataset_id))
        chat = ChatService(runtime, manual, history)
        for name in ("start", "status", "cancel", "recover", "messages"):
            original = getattr(chat, name)

            def traced(*args, _name=name, _original=original, **kwargs):
                api_calls.append(_name)
                return _original(*args, **kwargs)

            monkeypatch.setattr(chat, name, traced)

        @asynccontextmanager
        async def resources():
            yield ChatServices(NeverRead(), NeverRead(), manual,
                CatalogService(runtime.owner, runtime.codec.dataset_id), chat)

        app = create_configured_api(resources, allowed_origins=(ORIGIN,),
            dataset_id=runtime.codec.dataset_id, with_chat=True)
        document, run = str(uuid4()), str(uuid4())
        path = f"/api/documents/{document}/chat/runs"
        payload = {"run_id": run, "text": "原話\r\n  空白及😀完整保留。",
                   "expected_jd_revision_ref": revision_ref(runtime, document)}
        with TestClient(app, base_url="http://localhost", headers={"Origin": ORIGIN}) as client:
            yield SimpleNamespace(client=client, app=app, runtime=runtime, graph=graph,
                model_calls=model_calls, sql_reads=sql_reads, api_calls=api_calls,
                dataset=runtime.codec.dataset_id, document=document, run=run, path=path,
                run_path=f"{path}/{run}", payload=payload, headers={HEADER: runtime.codec.dataset_id},
                releases=releases)
    return opened


def test_http_202_location_lookup_and_cancel_wait_for_actual_future(chat_app):
    entered, release = Event(), Event()

    def paused(state):
        entered.set()
        assert release.wait(10)
        return {"messages": [AIMessage(id="saved-after-stop", content="實際保存的完整回覆")]}

    with chat_app(paused) as value:
        value.releases.append(release)
        started = value.client.post(value.path, json=value.payload, headers=value.headers)
        body = assert_result(started, ChatRunState, 202)
        assert started.headers["Location"] == value.run_path
        assert body["run_status"] == "running" and body["jd_effects"]["state"] == "unconfirmed"
        assert entered.wait(2)
        handle = value.runtime.lookup(value.document, value.run)
        before = value.graph.get_state({"configurable": {"thread_id": value.document}}, subgraphs=True)
        for _ in range(2):
            lookup = assert_result(value.client.get(value.run_path), ChatRunState)
            assert lookup["run_status"] == "running" and lookup["write_state"]["write_blocked"]
        assert value.graph.get_state(before.config, subgraphs=True) == before
        assert value.api_calls.count("start") == 1 and value.model_calls == [value.run]
        cancelled = value.client.post(value.run_path + "/cancel", json={}, headers=value.headers)
        waiting = assert_result(cancelled, ChatRunState, 202)
        assert waiting["stop_requested"] is True and waiting["run_status"] == "running"
        assert cancelled.headers["Location"] == value.run_path
        with pytest.raises(TimeoutError):
            handle.wait(0.01)
        assert value.runtime.owner.status(value.document).write_blocked
        release.set()
        assert handle.wait(5).status == "cancelled"
        final = assert_result(value.client.get(value.run_path), ChatRunState)
        assert final["run_status"] == "cancelled" and final["input_state"] == "saved"
        assert final["response_message_id"] == "saved-after-stop"
        assert final["jd_effects"] == {"state": "settled", "results": []}
        assert value.api_calls.count("start") == 1 and value.model_calls == [value.run]


def test_completed_original_lookup_retry_and_history_do_not_replay_or_replace_input(chat_app):
    with chat_app() as value:
        first = value.client.post(value.path, json=value.payload, headers=value.headers)
        assert first.status_code in {200, 202}, first.text
        assert value.runtime.lookup(value.document, value.run).wait(5).status == "completed"
        original = assert_result(value.client.get(value.run_path), ChatRunState)
        messages_path = f"/api/documents/{value.document}/chat/messages"
        page = assert_result(value.client.get(messages_path, params={"limit": 1}), ChatHistoryPage)
        assert page["messages"] == [{"message_id": original["response_message_id"], "run_id": value.run,
                                      "role": "assistant", "text": "合成完整回覆"}]
        assert page["anchor"] and page["next_cursor"]
        assert page["anchor_run_id"] == value.run
        before = value.graph.get_state({"configurable": {"thread_id": value.document}}, subgraphs=True)
        assert_result(value.client.get(value.run_path), ChatRunState)
        assert value.api_calls.count("start") == 1
        assert value.graph.get_state(before.config, subgraphs=True) == before
        value.runtime.owner.storage.revision_id = uuid4()  # Existing original must precede new head precondition.
        retry = assert_result(value.client.post(value.path, json=value.payload, headers=value.headers), ChatRunState)
        assert retry == original and value.model_calls == [value.run]
        conflicting = value.client.post(value.path, json={**value.payload, "text": "同 ID 的另一個意圖"}, headers=value.headers)
        assert assert_result(conflicting, ChatProblem, 409)["code"] == "run_conflict"
        second = {**value.payload, "run_id": str(uuid4()), "text": "第二輪原話",
                  "expected_jd_revision_ref": revision_ref(value.runtime, value.document)}
        assert value.client.post(value.path, json=second, headers=value.headers).status_code in {200, 202}
        value.runtime.lookup(value.document, second["run_id"]).wait(5)
        continuation = assert_result(value.client.get(messages_path,
            params={"cursor": page["next_cursor"], "limit": 1}), ChatHistoryPage)
        assert continuation["anchor"] == page["anchor"] and continuation["next_cursor"] is None
        assert continuation["anchor_run_id"] == page["anchor_run_id"] == value.run
        assert continuation["messages"] == [{"message_id": value.run, "run_id": value.run,
                                              "role": "user", "text": value.payload["text"]}]
        fresh = assert_result(value.client.get(messages_path, params={"limit": 1}), ChatHistoryPage)
        assert fresh["anchor_run_id"] == second["run_id"]
        assert assert_result(value.client.get(value.run_path), ChatRunState) == original
        unknown = assert_result(value.client.get(value.path + "/" + str(uuid4())), ChatRunState)
        assert unknown["run_status"] == "not_found" and unknown["input_state"] == "unconfirmed"
        assert value.model_calls == [value.run, second["run_id"]] and not value.runtime.owner.storage.executed


@pytest.mark.parametrize("suffix", ["", "/cancel", "/recover"])
@pytest.mark.parametrize("headers,expected", [
    ([], 409), ([(HEADER, "other-dataset")], 409),
    ([("Origin", "https://wrong.invalid")], 403),
])
def test_origin_and_dataset_reject_before_receiving_body(chat_app, suffix, headers, expected, caplog):
    with chat_app() as value:
        caplog.set_level(logging.INFO, logger="caliburn.jd.http")
        path = value.path if not suffix else value.run_path + suffix
        extra = [(name.lower().encode(), item.encode()) for name, item in headers]
        scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
            "method": "POST", "scheme": "http", "path": path, "raw_path": path.encode(),
            "root_path": "", "query_string": b"", "client": ("127.0.0.1", 11001),
            "server": ("localhost", 80), "headers": [(b"host", b"localhost"),
                (b"content-type", b"application/json"), (b"origin", ORIGIN.encode()), *extra]}
        sent = []
        async def receive():
            pytest.fail("Rejected browser scope must not read the raw request body")
        async def send(message):
            sent.append(message)
        anyio.run(value.app, scope, receive, send)
        assert sent[0]["status"] == expected
        body = json.loads(b"".join(message.get("body", b"") for message in sent))
        assert body["code"] == ("origin_not_allowed" if expected == 403 else "dataset_changed")
        assert value.api_calls == value.model_calls == value.sql_reads == []
        assert PRIVATE not in caplog.text


def test_duplicate_dataset_cannot_trigger_uuid_only_recovery(chat_app):
    with chat_app() as value:
        headers = [(HEADER, value.dataset), (HEADER.lower(), value.dataset)]
        response = value.client.post(value.run_path + "/recover", json={}, headers=headers)
        assert response.status_code == 409 and response.json()["code"] == "dataset_changed"
        assert value.api_calls == value.model_calls == []


@pytest.mark.parametrize("damage", ["json", "duplicate", "unknown", "type", "nul", "utf8_limit"])
def test_invalid_original_json_never_exposes_body_or_admits_run(chat_app, damage, caplog):
    with chat_app() as value:
        caplog.set_level(logging.INFO, logger="caliburn.jd.http")
        payload = {**value.payload, "text": PRIVATE}
        if damage == "json":
            raw = '{"text":"' + PRIVATE
        elif damage == "duplicate":
            raw = json.dumps(payload)[:-1] + ', "text": "second value"}'
        else:
            if damage == "unknown": payload[PRIVATE] = PRIVATE
            elif damage == "type": payload["run_id"] = {PRIVATE: PRIVATE}
            elif damage == "nul": payload["text"] = PRIVATE + "\0"
            else: payload["text"] = "漢" * 45000
            raw = json.dumps(payload, ensure_ascii=False)
        response = value.client.post(value.path, content=raw,
            headers={**value.headers, "Content-Type": "application/json"})
        assert assert_result(response, ChatProblem, 422)["code"] == "invalid_input"
        assert PRIVATE not in response.text + caplog.text
        assert value.model_calls == [] and value.api_calls == []
        assert value.graph.get_state({"configurable": {"thread_id": value.document}}).values == {}


@pytest.mark.parametrize("suffix", ["/cancel", "/recover"])
def test_cancel_and_recover_require_exact_empty_body(chat_app, suffix):
    with chat_app() as value:
        response = value.client.post(value.run_path + suffix, json={PRIVATE: PRIVATE}, headers=value.headers)
        assert assert_result(response, ChatProblem, 422)["code"] == "invalid_input"
        assert PRIVATE not in response.text and value.api_calls == []


def test_service_driver_failure_is_safe_and_cors_still_applies(chat_app, monkeypatch, caplog):
    with chat_app() as value:
        caplog.set_level(logging.INFO, logger="caliburn.jd.http")
        def fail(*args, **kwargs):
            raise RuntimeError(PRIVATE)
        monkeypatch.setattr(value.runtime.history, "read_run_operations", fail)
        response = value.client.get(value.run_path)
        assert assert_result(response, ChatProblem, 503)["code"] == "service_unavailable"
        assert response.headers["Access-Control-Allow-Origin"] == ORIGIN
        assert PRIVATE not in response.text + caplog.text
        assert value.model_calls == []


def test_openapi_and_cors_expose_actual_chat_contract_and_location(chat_app):
    with chat_app() as value:
        preflight = value.client.options(value.path, headers={"Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": f"Content-Type,{HEADER}"})
        assert preflight.status_code == 200
        assert HEADER.lower() in preflight.headers["Access-Control-Allow-Headers"].lower()
        schema = value.app.openapi()
        route = "/api/documents/{document_id}/chat/runs"
        for path in (route, route + "/{run_id}/cancel", route + "/{run_id}/recover"):
            operation = schema["paths"][path]["post"]
            assert operation["responses"]["202"]["content"]["application/json"]["schema"]["$ref"].endswith("/ChatRunState")
            assert any(p.get("name") == HEADER and p["required"] for p in operation["parameters"])
            conflict = operation["responses"]["409"]["content"]["application/problem+json"]["schema"]
            assert {entry["$ref"].rsplit("/", 1)[-1] for entry in conflict["anyOf"]} == {"CatalogProblem", "ChatProblem"}
        frozen = deepcopy(schema)
        assert value.app.openapi() == frozen
        response = value.client.get(value.run_path)
        assert "location" in response.headers["Access-Control-Expose-Headers"].lower()
