"""Synthetic ASGI unit evidence only; native/browser acceptance is separate."""

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from support.ui_response_gate import ResponseGate, GateError
from support import ui_response_gate_server as native


@pytest.fixture
def tmp_path():
    # Preserve synthetic artifacts; pytest's mode-0700 temp dirs are inaccessible
    # to this Windows managed sandbox. No cleanup or user directory is touched.
    path = Path(__file__).resolve().parents[3] / ".research-tmp" / f"jd-gate-unit-{uuid4().hex}"
    path.mkdir()
    return path


def arm(path, document):
    (path / "gate.arm.json").write_text(json.dumps({"format": 1, "document_id": document}), encoding="utf-8")


def scope(document, method="POST", suffix="edits"):
    return {"type": "http", "method": method, "path": f"/api/documents/{document}/jd/{suffix}"}


def observation(document, operation, revision=None, status="committed"):
    receipt = SimpleNamespace(document_id=document, operation_id=operation,
        result_revision_id=revision or uuid4(), status=status)
    return SimpleNamespace(confirmed=True, receipt=receipt)


async def until(predicate):
    async with asyncio.timeout(2):
        while not predicate():
            await asyncio.sleep(0.005)


@pytest.mark.parametrize("status", [200, 202])
@pytest.mark.parametrize("release_first", [False, True])
def test_hold_start_until_commit_and_release_while_get_keeps_working(tmp_path, status, release_first):
    async def scenario():
        document, operation, revision = str(uuid4()), uuid4(), uuid4()
        arm(tmp_path, document)
        entered = asyncio.Event()
        sent = []

        async def app(request, receive, send):
            if request["method"] == "POST":
                entered.set()
            await send({"type": "http.response.start", "status": status, "headers": []})
            await send({"type": "http.response.body", "body": b"private-body"})

        gate = ResponseGate(app, tmp_path, timeout=1)
        async def receive(): return {"type": "http.disconnect"}
        async def send(message): sent.append(message)
        running = asyncio.create_task(gate(scope(document), receive, send))
        await entered.wait()
        await until(lambda: (tmp_path / "gate.held.json").exists())
        assert sent == []
        other = []
        async def send_other(message): other.append(message)
        await asyncio.wait_for(gate(scope(document, "GET", "state"), receive, send_other), 0.3)
        assert len(other) == 2
        if release_first:
            (tmp_path / "gate.release.request").touch()
            await asyncio.sleep(0.03)
            assert sent == []
        result = observation(document, operation, revision)
        gate.record_execution(document, operation, result)
        if not release_first:
            await asyncio.sleep(0.03)
            assert sent == []
            (tmp_path / "gate.release.request").touch()
        await running
        assert [message["type"] for message in sent] == ["http.response.start", "http.response.body"]
        evidence = json.loads((tmp_path / "gate.committed.json").read_text())
        assert evidence["operation_id"] == str(operation)
        assert evidence["result_revision_id"] == str(revision)
        assert evidence["response_start_forwarded"] is False
        assert json.loads((tmp_path / "gate.finished.json").read_text())["outcome"] == "released"
        assert "private-body" not in "".join(path.read_text() for path in tmp_path.glob("*.json"))
    asyncio.run(scenario())


def test_timeout_does_not_forward_or_create_commit_evidence(tmp_path):
    async def scenario():
        document = str(uuid4()); arm(tmp_path, document)
        (tmp_path / "gate.release.request").touch()
        async def app(request, receive, send): await send({"type": "http.response.start", "status": 202})
        gate = ResponseGate(app, tmp_path, timeout=0.05)
        sent = []
        async def receive(): return {"type": "http.disconnect"}
        async def send(message): sent.append(message)
        with pytest.raises(GateError, match="gate_timeout"):
            await gate(scope(document), receive, send)
        assert sent == [] and not (tmp_path / "gate.committed.json").exists()
        final = json.loads((tmp_path / "gate.finished.json").read_text())
        assert final["outcome"] == "timeout" and final["response_start_forwarded"] is False
    asyncio.run(scenario())


def test_only_exact_first_post_and_restart_does_not_rearm(tmp_path):
    async def scenario():
        document = str(uuid4()); arm(tmp_path, document)
        calls = []
        async def app(request, receive, send):
            calls.append(request)
            await send({"type": "http.response.start", "status": 200})
        async def receive(): return {"type": "http.disconnect"}
        async def send(message): pass
        gate = ResponseGate(app, tmp_path, timeout=0.03)
        for request in [scope(str(uuid4())), scope(document, "GET"), scope(document, suffix="read"), {"type": "lifespan"}]:
            await gate(request, receive, send)
        assert not (tmp_path / "gate.claimed.json").exists()
        with pytest.raises(GateError): await gate(scope(document), receive, send)
        await gate(scope(document), receive, send)
        await ResponseGate(app, tmp_path, timeout=0.03)(scope(document), receive, send)
        assert len(calls) == 7
    asyncio.run(scenario())


def test_disconnect_is_forwarded_and_does_not_release_or_prove_writer_stopped(tmp_path):
    async def scenario():
        document, operation = str(uuid4()), uuid4(); arm(tmp_path, document)
        disconnect_seen = asyncio.Event()
        async def app(request, receive, send):
            assert await receive() == {"type": "http.disconnect"}
            disconnect_seen.set()
            await send({"type": "http.response.start", "status": 200})
        gate = ResponseGate(app, tmp_path, timeout=1)
        async def receive(): return {"type": "http.disconnect"}
        async def send(message): raise OSError("private-disconnect-detail")
        running = asyncio.create_task(gate(scope(document), receive, send))
        await disconnect_seen.wait()
        await until(lambda: (tmp_path / "gate.held.json").exists())
        assert not running.done()
        gate.record_execution(document, operation, observation(document, operation))
        (tmp_path / "gate.release.request").touch()
        with pytest.raises(OSError): await running
        final = json.loads((tmp_path / "gate.finished.json").read_text())
        assert final["outcome"] == "send_disconnected"
        assert final["writer_stopped_proven"] is False
        assert "private-disconnect-detail" not in "".join(path.read_text() for path in tmp_path.glob("*.json"))
    asyncio.run(scenario())


def test_malformed_arm_is_safe_and_not_consumed(tmp_path):
    async def scenario():
        (tmp_path / "gate.arm.json").write_text('{"document_id":"private-content"}')
        async def app(*args): raise AssertionError("must not enter app")
        with pytest.raises(GateError, match="gate_invalid_arm") as error:
            await ResponseGate(app, tmp_path)(scope(str(uuid4())), None, None)
        assert "private-content" not in str(error.value)
        assert not (tmp_path / "gate.claimed.json").exists()
    asyncio.run(scenario())


def test_unconfirmed_or_other_operation_cannot_release(tmp_path):
    async def scenario():
        document, operation = str(uuid4()), uuid4(); arm(tmp_path, document)
        (tmp_path / "gate.release.request").touch()
        async def app(request, receive, send):
            gate.record_execution(document, operation, SimpleNamespace(confirmed=False, receipt=None))
            gate.record_execution(str(uuid4()), uuid4(), observation(str(uuid4()), uuid4()))
            await send({"type": "http.response.start", "status": 202})
        gate = ResponseGate(app, tmp_path, timeout=0.04)
        with pytest.raises(GateError, match="gate_timeout"): await gate(scope(document), None, None)
        assert not (tmp_path / "gate.committed.json").exists()
    asyncio.run(scenario())


def write_manifest(path):
    value = {"database": "caliburn_jd_setup_test_" + path.name.removeprefix("jd-ui-gate-"),
        "port": 55436, "api_port": 8767, "ui_origin": native.ORIGIN}
    (path / "fixture.json").write_text(json.dumps(value), encoding="utf-8")
    return value


def test_cli_scope_and_one_shot_arm_release_controls(tmp_path):
    target = tmp_path / ("jd-ui-gate-" + uuid4().hex); target.mkdir()
    write_manifest(target)
    document = str(uuid4())
    native.arm(target, document)
    with pytest.raises(FileExistsError): native.arm(target, document)
    with pytest.raises(FileNotFoundError): native.release(target)
    common = {"document_id": document, "operation_id": str(uuid4()), "result_revision_id": str(uuid4())}
    (target / "gate.committed.json").write_text(json.dumps({**common, "committed": True}), encoding="utf-8")
    (target / "gate.held.json").write_text(json.dumps({**common, "response_start_forwarded": False}), encoding="utf-8")
    native.release(target)
    with pytest.raises(FileExistsError): native.release(target)
    assert native.valid_port(8767) and native.valid_port(8768)
    assert not any(native.valid_port(value) for value in (True, 3001, 3002, 55436, 65536))
    with pytest.raises(ValueError): native.directory(tmp_path)


@pytest.mark.parametrize("field,value", [("host", "localhost"), ("port", 5432), ("database", "production"),
    ("username", "someone"), ("password", "private-password"), ("checkpoint_schema", "public"),
    ("api_port", 8768), ("allowed_origins", ("https://example.invalid",))])
def test_wrong_fixture_configuration_never_opens_native_host(tmp_path, monkeypatch, field, value):
    # Pure branch test: no DPAPI decryption, OS host, DB connection or provider.
    from jd_relational import config_file, local_configuration, managed_app
    target = tmp_path / ("jd-ui-gate-" + uuid4().hex); target.mkdir()
    manifest = write_manifest(target)
    settings = SimpleNamespace(host="127.0.0.1", port=55436, database=manifest["database"],
        username="jd_test", password="jd-local-test-only", checkpoint_schema="jd_runtime",
        api_port=8767, allowed_origins=(native.ORIGIN, "http://127.0.0.1:8767"))
    setattr(settings, field, value)
    monkeypatch.setattr(config_file.ConfigFile, "read", lambda self: b"synthetic-configuration")
    monkeypatch.setattr(local_configuration, "parse_configuration", lambda raw: settings)
    called = []
    monkeypatch.setattr(managed_app, "open_managed_app", lambda *args, **kwargs: called.append(True))
    with pytest.raises(ValueError, match="invalid_probe_configuration") as error:
        native.serve(target, 1)
    assert called == [] and "private-password" not in str(error.value)


def test_bad_timeout_fails_before_reading_configuration(tmp_path, monkeypatch):
    from jd_relational import config_file
    target = tmp_path / ("jd-ui-gate-" + uuid4().hex); target.mkdir(); write_manifest(target)
    def forbidden(self): raise AssertionError("must not read configuration")
    monkeypatch.setattr(config_file.ConfigFile, "read", forbidden)
    with pytest.raises(GateError, match="gate_invalid_timeout"): native.serve(target, 1000)


def test_configuration_replacement_between_reads_cannot_reach_db_selection(tmp_path, monkeypatch):
    from jd_relational import config_file, local_configuration, managed_app
    target = tmp_path / ("jd-ui-gate-" + uuid4().hex); target.mkdir()
    manifest = write_manifest(target)
    good = SimpleNamespace(host="127.0.0.1", port=55436, database=manifest["database"],
        username="jd_test", password="jd-local-test-only", checkpoint_schema="jd_runtime",
        api_port=8767, allowed_origins=(native.ORIGIN, "http://127.0.0.1:8767"))
    wrong = SimpleNamespace(**{**vars(good), "database": "other-database"})
    data = iter([b"first", b"second"])
    monkeypatch.setattr(config_file.ConfigFile, "read", lambda self: next(data))
    monkeypatch.setattr(local_configuration, "parse_configuration", lambda raw: good if raw == b"first" else wrong)
    could_select_database = []
    def open_host(file, **kwargs):
        file.read()  # Same subsequent native read the real host performs.
        could_select_database.append(True)
        raise AssertionError("must not reach resources")
    monkeypatch.setattr(managed_app, "open_managed_app", open_host)
    with pytest.raises(ValueError, match="invalid_probe_configuration"): native.serve(target, 1)
    assert could_select_database == []


def test_initialize_existing_wrong_scope_stops_before_database_setup(tmp_path, monkeypatch):
    from jd_relational import config_file, local_configuration, configured_host
    target = tmp_path / ("jd-ui-gate-" + uuid4().hex); target.mkdir(); write_manifest(target)
    wrong = SimpleNamespace(host="127.0.0.1", port=5432, database="other-database", username="someone",
        password="not-a-fixture", checkpoint_schema="jd_runtime", api_port=8767,
        allowed_origins=(native.ORIGIN, "http://127.0.0.1:8767"))
    monkeypatch.setattr(config_file.ConfigFile, "read", lambda self: b"existing-native-config")
    monkeypatch.setattr(local_configuration, "parse_configuration", lambda raw: wrong)
    could_setup_database = []
    def initialize(file, **kwargs):
        file.read()
        could_setup_database.append(True)
        raise AssertionError("must not reach setup")
    monkeypatch.setattr(configured_host, "initialize_configuration", initialize)
    with pytest.raises(ValueError, match="invalid_probe_configuration"): native.initialize(target)
    assert could_setup_database == []


def test_later_independent_operation_does_not_overwrite_original_gate_evidence(tmp_path):
    async def scenario():
        document, operation, revision = str(uuid4()), uuid4(), uuid4(); arm(tmp_path, document)
        async def app(request, receive, send):
            gate.record_execution(document, operation, observation(document, operation, revision))
            later = uuid4()
            gate.record_execution(document, later, observation(document, later))
            (tmp_path / "gate.release.request").touch()
            await send({"type": "http.response.start", "status": 200})
        async def send(message): pass
        gate = ResponseGate(app, tmp_path, timeout=0.1)
        await gate(scope(document), None, send)
        evidence = json.loads((tmp_path / "gate.committed.json").read_text())
        assert evidence["operation_id"] == str(operation) and evidence["result_revision_id"] == str(revision)
    asyncio.run(scenario())


def test_exact_route_trace_distinguishes_lookup_from_deduplicated_post(tmp_path):
    async def scenario():
        document, operation = str(uuid4()), uuid4(); arm(tmp_path, document)
        executions = []
        async def app(request, receive, send):
            if request["method"] == "POST" and request["path"].endswith("/edits") and not executions:
                executions.append(operation)
                gate.record_execution(document, operation, observation(document, operation))
                (tmp_path / "gate.release.request").touch()
            await send({"type": "http.response.start", "status": 200})
        async def send(message): pass
        gate = ResponseGate(app, tmp_path, timeout=0.2)
        await gate(scope(document), None, send)
        await gate(scope(document, "GET", f"operations/{operation}"), None, send)
        routes = json.loads((tmp_path / "gate.routes.json").read_text())
        assert routes["edit_post_count"] == 1 and routes["original_operation_get_count"] == 1
        assert routes["operation_id"] == str(operation)
        await gate(scope(document), None, send)  # A response without another execute.
        assert executions == [operation]
        routes = json.loads((tmp_path / "gate.routes.json").read_text())
        assert routes["edit_post_count"] == 2
        for request in [scope(str(uuid4())), scope(document, "GET", "state"),
                        scope(document, "GET", "operations/" + str(uuid4()))]:
            await gate(request, None, send)
        assert json.loads((tmp_path / "gate.routes.json").read_text()) == routes
    asyncio.run(scenario())
