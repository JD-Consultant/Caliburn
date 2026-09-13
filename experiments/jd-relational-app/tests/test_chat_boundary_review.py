"""Independent native/ASGI boundary review; zero DB/provider or host startup."""

from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor
import json
from threading import Event
from uuid import uuid4

import anyio
from fastapi.testclient import TestClient
import pytest

from jd_relational.ai_checkpoints import AiCheckpointError
from jd_relational.chat_api import ChatServices
from jd_relational.chat_service import ChatError
from jd_relational.configured_api import create_configured_api
from jd_relational.generated.chat_http import ChatProblem, ChatRunState
from test_ai_runtime import make_runtime
from test_chat_service import request_for, service_for
from test_manual_api import NeverRead, ORIGIN


@pytest.fixture
def boundary(make_runtime):
    make, _ = make_runtime
    runtime, _, calls = make()
    service = service_for(runtime)
    @asynccontextmanager
    async def resources():
        yield ChatServices(NeverRead(), NeverRead(), service.manual, NeverRead(), service)
    app = create_configured_api(resources, allowed_origins=(ORIGIN,),
        dataset_id=runtime.codec.dataset_id, with_chat=True)
    with TestClient(app, base_url="http://localhost", headers={
        "Origin": ORIGIN, "X-JD-Dataset": runtime.codec.dataset_id}) as client:
        yield client, app, runtime, calls


def path(document, run=None, suffix=""):
    return f"/api/documents/{document}/chat/runs" + (f"/{run}" if run else "") + suffix


def test_original_http_request_repeated_after_terminal_is_not_replayed(boundary):
    client, _, runtime, calls = boundary
    document, run = str(uuid4()), str(uuid4())
    value = request_for(runtime, document, run)
    first = client.post(path(document), json=value)
    assert first.status_code in {200, 202}
    runtime.lookup(document, run).wait(5)
    terminal = client.get(path(document, run))
    duplicate = client.post(path(document), json=value)
    assert duplicate.status_code == 200 and duplicate.json() == terminal.json()
    assert calls == [run]
    page = client.get(f"/api/documents/{document}/chat/messages").json()
    assert page["messages"][0]["text"] == value["text"]
    assert page["messages"][1]["message_id"] == terminal.json()["response_message_id"]


@pytest.mark.parametrize("method", ["status", "cancel", "recover", "start"])
def test_history_lookup_gap_is_problem_not_absence_or_a_new_model_admission(boundary, monkeypatch, method):
    client, _, runtime, calls = boundary
    document, run = str(uuid4()), str(uuid4())
    def gap(*_args, **_kwargs): raise AiCheckpointError("original_run_lookup_required")
    monkeypatch.setattr(runtime.run_history, "find", gap)
    if method == "start":
        response = client.post(path(document), json=request_for(runtime, document, run))
    elif method == "status": response = client.get(path(document, run))
    else: response = client.post(path(document, run, "/" + method), json={})
    assert response.status_code == 503
    problem = ChatProblem.model_validate(response.json(), strict=True)
    assert problem.code == "service_unavailable" and problem.next_action == "lookup_run"
    assert "run_status" not in response.json() and not calls
    # A second request cannot turn the same incomplete observation into absence.
    again = client.post(path(document), json=request_for(runtime, document, run))
    assert again.status_code == 503 and not calls


@pytest.mark.parametrize("method", ["cancel", "recover"])
def test_truly_unknown_control_request_never_creates_a_run(boundary, method):
    client, _, _, calls = boundary
    document, run = str(uuid4()), str(uuid4())
    response = client.post(path(document, run, "/" + method), json={})
    assert response.status_code == 200
    value = ChatRunState.model_validate(response.json(), strict=True).model_dump(mode="json")
    assert value["run_status"] == "not_found" and value["input_state"] == "unconfirmed"
    assert value["jd_effects"] == {"state": "unconfirmed", "results": []} and not calls


def test_duplicate_original_json_rejected_before_native_admission(boundary):
    client, _, runtime, calls = boundary
    document, run = str(uuid4()), str(uuid4())
    value = request_for(runtime, document, run)
    raw = json.dumps(value, ensure_ascii=False)
    raw = raw[:-1] + ',"text":"private-second-original"}'
    response = client.post(path(document), content=raw, headers={"Content-Type": "application/json"})
    assert response.status_code == 422 and response.json()["code"] == "invalid_input"
    assert not calls and "private-second-original" not in response.text


@pytest.mark.parametrize("rejected", ["origin", "dataset"])
def test_source_and_dataset_gates_do_not_read_the_body(boundary, rejected):
    _, app, runtime, calls = boundary
    sent, received = [], []
    headers = [(b"host", b"localhost"), (b"content-type", b"application/json")]
    headers += [(b"origin", b"https://wrong.invalid" if rejected == "origin" else ORIGIN.encode())]
    if rejected == "origin": headers.append((b"x-jd-dataset", runtime.codec.dataset_id.encode()))
    scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
        "method": "POST", "scheme": "http", "path": path(str(uuid4())), "raw_path": b"/",
        "root_path": "", "query_string": b"", "headers": headers,
        "client": ("127.0.0.1", 54321), "server": ("localhost", 80)}
    async def receive():
        received.append(True)
        raise AssertionError("Rejected source must not read private body")
    async def send(message): sent.append(message)
    anyio.run(app, scope, receive, send)
    assert not received and not calls
    assert sent[0]["status"] == (403 if rejected == "origin" else 409)
    body = json.loads(b"".join(item.get("body", b"") for item in sent))
    assert body["code"] == ("origin_not_allowed" if rejected == "origin" else "dataset_changed")
    ChatProblem.model_validate(body, strict=True)


def test_native_reader_error_is_safe_and_does_not_turn_into_success(boundary, monkeypatch, caplog):
    client, _, runtime, calls = boundary
    def broken(*_args, **_kwargs): raise OSError("SyntheticPrivateReaderDsn")
    monkeypatch.setattr(runtime.history, "read_run_operations", broken)
    response = client.get(path(str(uuid4()), str(uuid4())))
    assert response.status_code == 503 and response.json()["next_action"] == "lookup_run"
    assert "SyntheticPrivateReaderDsn" not in response.text + caplog.text and not calls


@pytest.mark.parametrize("query", ["status", "messages"])
def test_chat_sync_reads_remain_in_owner_drain_until_materialized(make_runtime, monkeypatch, query):
    make, _ = make_runtime
    runtime, _, calls = make()
    service = service_for(runtime)
    entered, release = Event(), Event()
    if query == "status":
        target, name = runtime.history, "read_run_operations"
    else:
        target, name = service.history, "read"
    original = getattr(target, name)
    def held(*args, **kwargs):
        entered.set()
        assert release.wait(3), "review must release its own read"
        return original(*args, **kwargs)
    monkeypatch.setattr(target, name, held)
    document, run = str(uuid4()), str(uuid4())
    def read():
        try:
            return service.status(document, run) if query == "status" else service.messages(document)
        except ChatError as error:
            return error.code  # Closing may reject a subsequent nested read.
    with ThreadPoolExecutor(max_workers=1) as pool:
        result = pool.submit(read)
        try:
            assert entered.wait(2)
            assert runtime.owner.close(timeout=0) is False and not result.done()
        finally:
            release.set()
        value = result.result(timeout=3)
        assert type(value) in {dict, str}
    assert runtime.owner.close(timeout=2) and not calls
