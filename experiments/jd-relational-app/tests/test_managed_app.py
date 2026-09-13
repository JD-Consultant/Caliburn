"""Composition and lifecycle probes with synthetic resources, no real OS/DB."""
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest

import jd_relational.managed_app as managed
import jd_relational.__main__ as entry
from jd_relational.local_configuration import encode_configuration
from test_configured_host import settings


@pytest.fixture
def composed(monkeypatch):
    events = []
    def startup(**kwargs):
        events.append("startup")
    def close(**kwargs):
        events.append("close")
        return True
    value = settings("ready")
    opened = SimpleNamespace(settings=value, codec=object(), close=close,
        host=SimpleNamespace(graph=object(), engine=object(), memory_engine=object(), runtime=SimpleNamespace(storage=object(), finish_startup=startup)))
    monkeypatch.setattr(managed, "open_configured_host", lambda *_, **__: opened)
    monkeypatch.setattr(managed, "HistoryReader", lambda _: object())
    monkeypatch.setattr(managed, "ReadService", lambda *args: object())
    monkeypatch.setattr(managed, "ChangeReadService", lambda *args: object())
    sources = SimpleNamespace(resolve=lambda *args: pytest.fail("Composition must not read sources."))
    def source_owner(checkpoints, codec):
        assert checkpoints is opened.host.graph
        assert codec.dataset_id == value.dataset_id
        return sources
    monkeypatch.setattr(managed, "AiRunCheckpoints", lambda graph: graph)
    monkeypatch.setattr(managed, "ConversationSourceService", source_owner)
    def manual(*args, source_resolver):
        assert source_resolver is sources.resolve
        return object()
    monkeypatch.setattr(managed, "ManualService", manual)
    monkeypatch.setattr(managed, "CatalogService", lambda *args: SimpleNamespace(list=lambda **_: {
        "dataset_id": value.dataset_id, "documents": [], "next_after": None}))
    def ai(owner, codec, *, conversation_sources, memory_engine, execution_enabled):
        assert owner is opened.host.runtime and codec is opened.codec
        assert conversation_sources is sources
        assert memory_engine is opened.host.memory_engine
        assert execution_enabled is False
        events.append("ai-owner")
        return SimpleNamespace(checkpoints=object())
    monkeypatch.setattr(managed, "AiRuntime", ai)
    monkeypatch.setattr(managed, "ChatHistoryService", lambda *args: object())
    monkeypatch.setattr(managed, "ChatService", lambda *args: object())
    return events, opened


def test_resources_recovered_before_first_request_and_drained_on_exit(composed):
    events, _ = composed
    app = managed.open_managed_app(object(), consultant=object())
    assert events == ["ai-owner"]
    assert app.ai_runtime is not None
    with TestClient(app.app, base_url="http://127.0.0.1") as client:
        assert events == ["ai-owner", "startup"]
        # Invalid dataset is rejected without calling a fake writer.
        response = client.post("/api/documents", content="bad-body", headers={
            "Origin": "http://127.0.0.1:3002", "X-JD-Dataset": str(uuid4())})
        assert response.status_code == 409
    assert events == ["ai-owner", "startup", "close"]


def test_startup_failure_is_sanitized_and_drain_still_occurs(composed):
    events, opened = composed
    def failure(**kwargs):
        raise RuntimeError("private-connection-password")
    opened.host.runtime.finish_startup = failure
    app = managed.open_managed_app(object(), consultant=object())
    with pytest.raises(RuntimeError, match="^jd_query_startup_failed$") as error:
        with TestClient(app.app):
            pytest.fail("No serving before recovery.")
    assert error.value.__suppress_context__
    assert events == ["ai-owner", "close"]


def test_composition_failure_does_not_leak_open_host_or_raw_error(composed, monkeypatch):
    events, _ = composed
    def failure(*args, **kwargs):
        raise RuntimeError("private-configuration")
    monkeypatch.setattr(managed, "create_configured_api", failure)
    with pytest.raises(managed.ManagedAppError, match="^app_composition_failed$"):
        managed.open_managed_app(object(), consultant=object())
    assert events == ["ai-owner", "close"]


def test_manual_only_consultant_explicitly_refuses_interview_invocation():
    from jd_relational.inspection_model import InspectionExecutionDisabled
    with pytest.raises(InspectionExecutionDisabled) as error:
        managed.unavailable_consultant().invoke({"messages": []})
    assert str(error.value) == error.value.code == "execution_disabled"


@pytest.fixture
def cli(monkeypatch):
    events = []
    value = settings("ready")
    file = SimpleNamespace(read=lambda: encode_configuration(value))
    monkeypatch.setattr(entry, "default_config_path", lambda: "os-fixed-path")
    def make_file(path):
        assert path == "os-fixed-path"
        events.append("file")
        return file
    monkeypatch.setattr(entry, "ConfigFile", make_file)
    return events, file


def test_status_only_reads_configuration_and_does_not_claim_database_readiness(cli, monkeypatch, capsys):
    events, _ = cli
    monkeypatch.setattr(entry, "initialize_configuration", lambda *_, **__: pytest.fail("No init."))
    monkeypatch.setattr(entry, "open_managed_app", lambda *_, **__: pytest.fail("No host."))
    assert entry.main(["status"]) == 0
    assert events == ["file"]
    assert "serve 仍會檢查" in capsys.readouterr().out


def test_cli_error_never_prints_private_exception(cli, capsys):
    _, file = cli
    def failure():
        raise ValueError("private-password-and-file-name")
    file.read = failure
    assert entry.main(["status"]) == 1
    assert "private-password" not in capsys.readouterr().err


def test_resume_does_not_ask_for_new_connection_or_id(cli, monkeypatch):
    _, file = cli
    monkeypatch.setattr(entry, "_connection_input", lambda: pytest.fail("Keep original config."))
    calls = []
    monkeypatch.setattr(entry, "initialize_configuration", lambda f, **kwargs: calls.append((f, kwargs)))
    assert entry.main(["resume-init"]) == 0
    assert calls == [(file, {"connection": None, "resume": True})]


def test_serve_is_single_loopback_process_and_drains(cli, monkeypatch):
    events, file = cli
    import uvicorn
    app = object()
    fake = SimpleNamespace(app=app, port=8014, close=lambda: events.append("close") or True)
    monkeypatch.setattr(entry, "open_managed_app", lambda f, **kwargs: fake)
    def run(passed, **kwargs):
        assert passed is app and kwargs == dict(host="127.0.0.1", port=8014, workers=1,
            reload=False, access_log=False, proxy_headers=False, log_level="warning")
        events.append("server")
    monkeypatch.setattr(uvicorn, "run", run)
    assert entry.main(["serve"]) == 0
    assert events == ["file", "server", "close"]


def test_init_refuses_noninteractive_secret_input(monkeypatch):
    monkeypatch.setattr(entry.sys, "stdin", SimpleNamespace(isatty=lambda: False))
    with pytest.raises(ValueError, match="interactive_initialization_required"):
        entry._connection_input()
