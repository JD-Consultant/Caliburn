"""Real ASGI admission boundaries, without a database or provider."""

from contextlib import asynccontextmanager
from copy import deepcopy
import json
import logging
from threading import get_ident
import traceback
from uuid import uuid4

import anyio
from fastapi.testclient import TestClient
import pytest

from jd_relational.generated.manual_http import ManualProblem, ManualSaveInput
from jd_relational.manual_api import (
    EDIT_ROUTE, STATE_ROUTE, OPERATION_ROUTE, RECOVER_ROUTE, ManualServices, create_manual_app,
)
from jd_relational.manual_service import ManualError
from result_fixtures import observed_result


DOCUMENT = str(uuid4())
OPERATION = str(uuid4())
ORIGIN = "http://localhost:3000"
PATH = f"/api/documents/{DOCUMENT}/jd/edits"
STATE_PATH = f"/api/documents/{DOCUMENT}/jd/state"
OPERATION_PATH = f"/api/documents/{DOCUMENT}/jd/operations/{OPERATION}"
RECOVER_PATH = OPERATION_PATH + "/recover"
BODY = {"operation_id": OPERATION, "base_revision_ref": "synthetic-base-ref",
        "command": {"tool": "jd_set_text", "arguments": {
            "target_field_ref": "synthetic-field-ref", "text": "每月核對報表。", "basis_refs": []}}}
STATE = {"ready": True, "archived": False, "write_blocked": False, "running": False,
         "operation_id": None, "error": None}
PRIVATE = "SyntheticPrivateInterviewSentinel"


class NeverRead:
    def read(self, *args):
        raise AssertionError("This request must not reach a query")


class ManualProbe:
    def __init__(self):
        self.calls = []
        self.result = observed_result()
        self.error = None

    def _call(self, name, *args):
        self.calls.append((name, *args))
        if self.error is not None:
            raise self.error

    def save(self, document, envelope):
        self._call("save", document, envelope)
        return deepcopy(self.result)

    def status(self, document):
        self._call("status", document)
        return deepcopy(STATE)

    def lookup(self, document, operation):
        self._call("lookup", document, operation)
        presence = "observed" if self.result["receipt_durability"] == "confirmed" else "pending"
        return {"operation_id": operation, "presence": presence, "result": deepcopy(self.result),
                "write_state": deepcopy(STATE)}

    def recover(self, document, operation):
        self._call("recover", document, operation)
        return {"operation_id": operation, "presence": "observed", "result": deepcopy(self.result),
                "write_state": deepcopy(STATE)}


def app_for(manual=None, *, resources=None):
    probe = manual or ManualProbe()
    if resources is None:
        @asynccontextmanager
        async def resources():
            yield ManualServices(NeverRead(), NeverRead(), probe)
    return create_manual_app(resources, allowed_origins=(ORIGIN,))


def test_disallowed_origin_is_rejected_before_body_or_admission():
    manual = ManualProbe()
    with TestClient(app_for(manual), base_url="http://127.0.0.1") as client:
        response = client.post(PATH, content=b"invalid-json", headers={"origin": "https://evil.example"})
    assert response.status_code == 403
    assert manual.calls == []


@pytest.mark.parametrize("headers", [
    {}, {"origin": "null"}, {"origin": "https://evil.example"},
    {"origin": "http://localhost:3001"}, {"origin": "http://localhost:3000.evil.example"},
    {"origin": "http://localhost:3000/"},
    [("origin", ORIGIN), ("origin", ORIGIN)],
    [("origin", ORIGIN), ("origin", "https://evil.example")],
])
@pytest.mark.parametrize("path,body", [(PATH, BODY), (RECOVER_PATH, {})])
def test_exact_single_origin_on_every_manual_post(headers, path, body):
    probe = ManualProbe()
    with TestClient(app_for(probe), base_url="http://127.0.0.1") as client:
        result = client.post(path, json=body, headers=headers)
    assert result.status_code == 403
    assert result.json()["code"] == "origin_not_allowed"
    assert "jd_result" not in result.json()
    assert result.headers["cache-control"] == "no-store"
    assert result.headers["x-request-id"]
    assert probe.calls == []


@pytest.mark.parametrize("status,http", [
    ("committed", 200), ("no_change", 200), ("stale_view", 409), ("save_failed", 500),
    ("outcome_unknown", 202),
])
def test_save_and_lookup_keep_the_exact_original_observation(status, http):
    probe = ManualProbe()
    probe.result = observed_result(status, "unconfirmed" if status == "outcome_unknown" else "confirmed")
    before = deepcopy(probe.result)
    with TestClient(app_for(probe), base_url="http://127.0.0.1") as client:
        response = client.post(PATH, json=BODY, headers={"origin": ORIGIN})
        found = client.get(OPERATION_PATH)
    assert response.status_code == http
    assert response.json().get("jd_result", response.json()) == before
    assert found.status_code == 200 and found.json()["result"] == before
    assert [call[0] for call in probe.calls] == ["save", "lookup"]
    assert probe.calls[0][2] == BODY
    assert response.headers["access-control-allow-origin"] == ORIGIN


@pytest.mark.parametrize("content,content_type", [
    (json.dumps(BODY), None), (json.dumps(BODY), "text/plain"),
    (json.dumps(BODY), "application/x-www-form-urlencoded"),
    ('{"private":"' + PRIVATE + '"', "application/json"),
    (json.dumps({**BODY, "private": PRIVATE}), "application/json"),
    (json.dumps(BODY).replace('"operation_id":', '"operation_id": "' + OPERATION + '", "operation_id":'), "application/json"),
    (json.dumps(BODY).replace('"text":', '"text": "duplicate", "text":'), "application/json"),
    (json.dumps(BODY).replace('"basis_refs": []', '"basis_refs": NaN'), "application/json"),
    (json.dumps(BODY).replace('"text": "', '"text": true, "ignored": "'), "application/json"),
])
def test_bad_input_never_reaches_service(content, content_type, caplog):
    headers = {"origin": ORIGIN}
    if content_type is not None:
        headers["content-type"] = content_type
    probe = ManualProbe()
    with TestClient(app_for(probe), base_url="http://127.0.0.1") as client:
        response = client.post(PATH, content=content, headers=headers)
    assert response.status_code == 422
    assert response.json()["code"] == "invalid_input"
    assert PRIVATE not in response.text + caplog.text
    assert probe.calls == []


@pytest.mark.parametrize("content", ["", "null", "[]", '{"extra":1}', '{"extra":1,"extra":1}'])
def test_recovery_requires_an_explicit_empty_json_object(content):
    probe = ManualProbe()
    with TestClient(app_for(probe), base_url="http://127.0.0.1") as client:
        result = client.post(RECOVER_PATH, content=content,
                             headers={"origin": ORIGIN, "content-type": "application/json"})
    assert result.status_code == 422 and probe.calls == []


def test_recover_is_explicit_and_get_state_does_not_recover():
    probe = ManualProbe()
    with TestClient(app_for(probe), base_url="http://127.0.0.1") as client:
        state = client.get(STATE_PATH)
        recovered = client.post(RECOVER_PATH, json={}, headers={"origin": ORIGIN})
    assert state.status_code == recovered.status_code == 200
    assert state.json() == STATE
    assert [call[0] for call in probe.calls] == ["status", "recover"]


@pytest.mark.parametrize("code,status", [
    ("invalid_input", 422), ("invalid_ref", 422), ("target_missing", 404),
    ("stale_view", 409), ("operation_conflict", 409), ("busy", 409),
    ("service_unavailable", 503), ("selection_not_available", 422),
])
def test_service_failures_are_http_problems_not_fabricated_receipts(code, status):
    probe = ManualProbe()
    probe.error = ManualError(code)
    with TestClient(app_for(probe), base_url="http://127.0.0.1") as client:
        result = client.post(PATH, json=BODY, headers={"origin": ORIGIN})
    assert result.status_code == status
    assert ManualProblem.model_validate(result.json(), strict=True).code == code
    assert "jd_result" not in result.json()


@pytest.mark.parametrize("mode", ["exception", "bad_output", "status_output"])
def test_unexpected_failures_are_fixed_without_private_traceback(mode, caplog):
    probe = ManualProbe()
    if mode == "exception":
        probe.error = RuntimeError(PRIVATE)
    elif mode == "bad_output":
        probe.result = {"private": PRIVATE}
    else:
        probe.status = lambda _: {"private": PRIVATE}
    with TestClient(app_for(probe), base_url="http://127.0.0.1") as client:
        with caplog.at_level(logging.INFO, logger="caliburn.jd.http"):
            result = (client.get(STATE_PATH) if mode == "status_output" else
                      client.post(PATH, json=BODY, headers={"origin": ORIGIN}))
    assert result.status_code == 500 and "jd_result" not in result.json()
    assert PRIVATE not in result.text + caplog.text
    records = [record for record in caplog.records if record.name == "caliburn.jd.http"]
    assert records and all(record.exc_info is None for record in records)


def test_observed_unconfirmed_result_is_rejected_without_fabricating_a_receipt(caplog):
    probe = ManualProbe()
    unknown = observed_result("outcome_unknown", "unconfirmed")
    probe.lookup = lambda document, operation: {
        "operation_id": operation, "presence": "observed", "result": deepcopy(unknown),
        "write_state": deepcopy(STATE),
    }
    with TestClient(app_for(probe), base_url="http://127.0.0.1") as client:
        result = client.get(OPERATION_PATH)
    assert result.status_code == 500
    assert result.json()["code"] == "service_unavailable"
    assert "result" not in result.json() and "jd_result" not in result.json()
    assert unknown["operation_ref"] not in result.text + caplog.text
    assert unknown["receipt_durability"] == "unconfirmed"


@pytest.mark.parametrize("path", [
    "/api/documents/not-a-uuid/jd/edits",
    f"/api/documents/{DOCUMENT}/jd/operations/not-a-uuid/recover",
])
def test_invalid_path_identifiers_do_not_reach_service(path):
    probe = ManualProbe()
    with TestClient(app_for(probe), base_url="http://127.0.0.1") as client:
        response = client.post(path, json=BODY if path.endswith("edits") else {}, headers={"origin": ORIGIN})
    assert response.status_code == 422 and probe.calls == []


def test_native_host_cors_and_no_store_apply_to_manual_routes():
    probe = ManualProbe()
    with TestClient(app_for(probe), base_url="http://127.0.0.1") as client:
        assert client.get(STATE_PATH, headers={"host": "evil.example"}).status_code == 400
        assert probe.calls == []
        preflight = client.options(PATH, headers={"origin": ORIGIN,
            "access-control-request-method": "POST", "access-control-request-headers": "content-type"})
        assert preflight.status_code == 200
        assert "GET" in preflight.headers["access-control-allow-methods"]
        bad = client.options(PATH, headers={"origin": "https://evil.example",
            "access-control-request-method": "POST"})
        assert bad.status_code == 400 and probe.calls == []


@pytest.mark.parametrize("origins", [(), [], ("null",), ("http://evil.example",),
    ("http://localhost:0",), ("http://localhost:65536",), ("http://localhost:3000/",),
    ("http://user@localhost:3000",), ("http://LOCALHOST:3000",), ("http://localhost:03000",),
    (None,), ORIGIN])
def test_nonempty_explicit_local_canonical_origin_configuration(origins):
    @asynccontextmanager
    async def resources():
        raise AssertionError("Invalid config must not acquire resources")
        yield
    with pytest.raises(ValueError, match="explicit_local_origins_required"):
        create_manual_app(resources, allowed_origins=origins)


@pytest.mark.parametrize("phase", ["startup", "shutdown"])
def test_shared_native_lifespan_cleans_up_without_private_cause(phase, caplog):
    cleaned = []
    @asynccontextmanager
    async def resources():
        try:
            if phase == "startup":
                raise RuntimeError(PRIVATE)
            yield ManualServices(NeverRead(), NeverRead(), ManualProbe())
            raise RuntimeError(PRIVATE)
        finally:
            cleaned.append(True)
    app = app_for(resources=resources)
    with pytest.raises(RuntimeError, match=f"jd_query_{phase}_failed") as caught:
        with TestClient(app, base_url="http://127.0.0.1"):
            assert phase == "shutdown"
    assert cleaned == [True] and not hasattr(app.state, "jd_queries")
    assert PRIVATE not in "".join(traceback.format_exception(caught.value)) + caplog.text


def test_native_threadpool_keeps_sync_owner_outside_asgi_loop():
    threads = {}
    probe = ManualProbe()
    original = probe.save
    def save(*args):
        threads["save"] = get_ident()
        return original(*args)
    probe.save = save
    @asynccontextmanager
    async def resources():
        threads["loop"] = get_ident()
        yield ManualServices(NeverRead(), NeverRead(), probe)
    with TestClient(app_for(resources=resources), base_url="http://127.0.0.1") as client:
        assert client.post(PATH, json=BODY, headers={"origin": ORIGIN}).status_code == 200
    assert threads["save"] != threads["loop"]


def test_diagnostic_sink_failure_cannot_replace_saved_outcome(monkeypatch):
    def broken(*args, **kwargs):
        raise RuntimeError(PRIVATE)
    monkeypatch.setattr("jd_relational.query_api.LOG.log", broken)
    probe = ManualProbe()
    with TestClient(app_for(probe), base_url="http://127.0.0.1") as client:
        response = client.post(PATH, json=BODY, headers={"origin": ORIGIN})
    assert response.status_code == 200 and response.json() == probe.result


def test_openapi_has_generated_envelope_results_and_problem_media():
    schema = app_for().openapi()
    operation = schema["paths"][EDIT_ROUTE]["post"]
    assert operation["requestBody"]["content"]["application/json"]["schema"]["$ref"].endswith("/ManualSaveInput")
    expected = ManualSaveInput.model_json_schema(ref_template="#/components/schemas/{model}")
    expected.pop("$defs")
    assert schema["components"]["schemas"]["ManualSaveInput"] == expected
    for path, method in ((EDIT_ROUTE, "post"), (STATE_ROUTE, "get"),
                         (OPERATION_ROUTE, "get"), (RECOVER_ROUTE, "post")):
        for status in (403, 404, 409, 422, 500, 503):
            assert set(schema["paths"][path][method]["responses"][str(status)]["content"]) == {"application/problem+json"}
    assert set(operation["responses"]["202"]["content"]) == {"application/json"}


async def raw_request(app, messages, *, path=PATH, send_error=False):
    sent = []
    scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
             "method": "POST", "scheme": "http", "path": path, "raw_path": path.encode(),
             "query_string": b"", "root_path": "", "client": ("127.0.0.1", 10000),
             "server": ("127.0.0.1", 80), "headers": [(b"host", b"127.0.0.1"),
             (b"origin", ORIGIN.encode()), (b"content-type", b"application/json")]}
    queue = list(messages)
    async def receive():
        return queue.pop(0) if queue else {"type": "http.disconnect"}
    async def send(message):
        if send_error:
            raise OSError(PRIVATE)
        sent.append(message)
    # A real ASGI server executes request tasks separately from lifespan. Do
    # not inject an HTTP send failure into the resource manager as shutdown.
    failure = None
    async with app.router.lifespan_context(app):
        try:
            await app(scope, receive, send)
        except Exception as error:
            failure = error
    if failure is not None:
        raise failure
    return sent


def test_native_raw_chunk_limit_without_content_length():
    probe = ManualProbe()
    chunks = [{"type": "http.request", "body": b"x" * 600000, "more_body": True},
              {"type": "http.request", "body": b"x" * 600000, "more_body": False}]
    sent = anyio.run(raw_request, app_for(probe), chunks)
    assert next(item["status"] for item in sent if item["type"] == "http.response.start") == 413
    assert probe.calls == []


def test_disconnect_before_complete_request_never_admits():
    probe = ManualProbe()
    chunks = [{"type": "http.request", "body": b'{"operation_id":', "more_body": True},
              {"type": "http.disconnect"}]
    anyio.run(raw_request, app_for(probe), chunks)
    assert probe.calls == []


def test_response_loss_does_not_replay_or_rewrite_the_observed_outcome(caplog):
    probe = ManualProbe()
    chunks = [{"type": "http.request", "body": json.dumps(BODY).encode(), "more_body": False}]
    async def lost():
        await raw_request(app_for(probe), chunks, send_error=True)
    with pytest.raises(RuntimeError, match="jd_manual_response_interrupted") as caught:
        anyio.run(lost)
    assert PRIVATE not in "".join(traceback.format_exception(caught.value)) + caplog.text
    with TestClient(app_for(probe), base_url="http://127.0.0.1") as client:
        response = client.get(OPERATION_PATH)
    assert response.status_code == 200 and response.json()["result"] == probe.result
    assert [call[0] for call in probe.calls] == ["save", "lookup"]
