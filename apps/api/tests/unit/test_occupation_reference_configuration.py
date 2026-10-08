"""Reference tools are opt-in; their HTTP resource belongs to the App lifespan."""

from contextlib import AsyncExitStack, asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import httpx2
import pytest
from fastapi import FastAPI
from psycopg import AsyncConnection

from caliburn import bootstrap
from caliburn import settings as configuration
from caliburn.adapters.database_settings import DatabaseSettings
from caliburn.adapters.occupation_references import OccupationReferenceClient
from caliburn.app_composition import AppComposition


@pytest.fixture
def isolated_environment(monkeypatch):
    for name in (
        "CALIBURN_DATABASE_URL",
        "OPENAI_API_KEY",
        "CALIBURN_PDF_FONT_PATH",
        "CALIBURN_DEV_ORIGIN",
        "CALIBURN_WEB_BUILD_DIRECTORY",
        "CALIBURN_OCCUPATION_REFERENCE_URL",
        "CALIBURN_OCCUPATION_REFERENCE_REQUEST_TIMEOUT_SECONDS",
    ):
        monkeypatch.delenv(name, raising=False)


def test_reference_service_is_disabled_by_default(isolated_environment):
    assert configuration.Settings().occupation_references is None
    assert configuration.Settings.from_environment().occupation_references is None


@pytest.mark.parametrize(
    "origin",
    [
        "http://127.0.0.1:8090",
        "http://ocs-indexer:8000",
        "https://references.example",
        "https://references.example/",
        "http://[::1]:8000",
    ],
)
def test_explicit_http_origins_include_docker_hosts(origin):
    setting = configuration.OccupationReferenceSettings(base_url=origin)
    assert setting.base_url == origin
    assert setting.request_timeout_seconds == 30.0


@pytest.mark.parametrize(
    "origin",
    [
        "",
        "ocs-indexer:8000",
        "//ocs-indexer:8000",
        "ftp://ocs-indexer:8000",
        "http://",
        "http://indexer/api",
        "http://user:secret@indexer",
        "http://@indexer",
        "http://indexer?key=secret",
        "http://indexer?",
        "http://indexer#route",
        "http://indexer#",
        " http://indexer",
        "http://bad host",
        "http://indexer\n",
        "http://indexer\\other",
        "http://indexer:0",
        "http://indexer:65536",
        "http://indexer:not-a-port",
        "http://indexer:",
        "http://[not-an-ip]:8000",
    ],
)
def test_invalid_origin_is_rejected_before_any_client_exists(origin):
    with pytest.raises(ValueError, match="origin"):
        configuration.OccupationReferenceSettings(base_url=origin)


@pytest.mark.parametrize("timeout", [0, -1.0, float("inf"), float("-inf"), float("nan"), True])
def test_reference_timeout_must_be_finite_and_positive(timeout):
    with pytest.raises(ValueError, match="timeout"):
        configuration.OccupationReferenceSettings(
            base_url="http://ocs-indexer:8000", request_timeout_seconds=timeout
        )


def test_environment_enables_only_the_explicit_reference_configuration(
    isolated_environment, monkeypatch
):
    monkeypatch.setenv("CALIBURN_OCCUPATION_REFERENCE_URL", "http://ocs-indexer:8000")
    monkeypatch.setenv("CALIBURN_OCCUPATION_REFERENCE_REQUEST_TIMEOUT_SECONDS", "12.5")
    configured = configuration.Settings.from_environment()
    assert configured.occupation_references == configuration.OccupationReferenceSettings(
        base_url="http://ocs-indexer:8000", request_timeout_seconds=12.5
    )
    assert configured.model is None
    assert configured.database is None


def test_reference_timeout_alone_does_not_enable_the_service(isolated_environment, monkeypatch):
    monkeypatch.setenv("CALIBURN_OCCUPATION_REFERENCE_REQUEST_TIMEOUT_SECONDS", "12.5")
    assert configuration.Settings.from_environment().occupation_references is None


@pytest.mark.parametrize("timeout", ["not-a-number", "0", "nan", "inf"])
def test_invalid_configured_environment_timeout_fails(isolated_environment, monkeypatch, timeout):
    monkeypatch.setenv("CALIBURN_OCCUPATION_REFERENCE_URL", "http://ocs-indexer:8000")
    monkeypatch.setenv("CALIBURN_OCCUPATION_REFERENCE_REQUEST_TIMEOUT_SECONDS", timeout)
    with pytest.raises(ValueError):
        configuration.Settings.from_environment()


@pytest.fixture
def runtime(monkeypatch):
    sdk = SimpleNamespace(close=AsyncMock())
    composition = AppComposition(create_responses_client=Mock(return_value=sdk))
    consultant = Mock()
    situation = Mock()
    understanding = Mock()
    monkeypatch.setattr(bootstrap, "ConsultantRunner", consultant)
    monkeypatch.setattr(bootstrap, "WorkSituationAnalystRunner", situation)
    monkeypatch.setattr(bootstrap, "WorkUnderstandingAnalystRunner", understanding)
    supervisor = SimpleNamespace(start=AsyncMock(), close=AsyncMock())
    memory_supervisor = SimpleNamespace(start=AsyncMock(), close=AsyncMock())
    monkeypatch.setattr(bootstrap, "ConsultantSupervisor", Mock(return_value=supervisor))
    monkeypatch.setattr(bootstrap, "MemorySupervisor", Mock(return_value=memory_supervisor))
    database = SimpleNamespace(
        sessions=Mock(),
        settings=DatabaseSettings(url="postgresql://localhost/caliburn_test"),
    )
    app = FastAPI()
    bootstrap._reset_runtime_state(app, database)
    return SimpleNamespace(
        app=app,
        database=database,
        sdk=sdk,
        consultant=consultant,
        situation=situation,
        understanding=understanding,
        supervisor=supervisor,
        model=configuration.ModelSettings(api_key="synthetic-never-sent"),
        saver=Mock(),
        composition=composition,
    )


async def test_disabled_runtime_constructs_no_reference_client_and_leaves_memory_disabled(
    runtime, monkeypatch
):
    client_factory = Mock(
        side_effect=AssertionError("Disabled references must not create HTTP I/O")
    )
    monkeypatch.setattr(httpx2, "AsyncClient", client_factory)
    async with AsyncExitStack() as resources:
        await bootstrap._start_model_runtime(
            runtime.app,
            runtime.model,
            runtime.database,
            runtime.saver,
            resources,
            composition=runtime.composition,
        )
        assert runtime.consultant.call_args.kwargs.get("occupation_references") is None
        assert runtime.situation.call_args.kwargs.get("excluded_work_enabled", False) is False
        assert runtime.understanding.call_args.kwargs.get("excluded_work_enabled", False) is False
        deletion = runtime.app.state.job_file_workflow
        assert deletion.consultant_supervisor is runtime.app.state.consultant_supervisor
        assert deletion.memory_supervisor is runtime.app.state.memory_supervisor
    client_factory.assert_not_called()
    runtime.sdk.close.assert_awaited_once()


@pytest.mark.parametrize("startup_fails", [False, True])
async def test_enabled_runtime_binds_one_http_client_and_closes_it_on_every_exit(
    runtime, monkeypatch, startup_fails
):
    client_type = httpx2.AsyncClient
    clients = []
    client_arguments = []

    def forbid_requests(request):
        raise AssertionError("Configuration tests must not send requests")

    def create_client(**kwargs):
        client_arguments.append(kwargs)
        client = client_type(**kwargs, transport=httpx2.MockTransport(forbid_requests))
        clients.append(client)
        return client

    monkeypatch.setattr(httpx2, "AsyncClient", create_client)
    reference_settings = configuration.OccupationReferenceSettings(
        base_url="http://ocs-indexer:8000", request_timeout_seconds=12.5
    )
    if startup_fails:
        runtime.supervisor.start.side_effect = RuntimeError("Synthetic startup failure")

    async def start():
        async with AsyncExitStack() as resources:
            await bootstrap._start_model_runtime(
                runtime.app,
                runtime.model,
                runtime.database,
                runtime.saver,
                resources,
                composition=runtime.composition,
                occupation_references=reference_settings,
            )
            assert not clients[0].is_closed

    if startup_fails:
        with pytest.raises(RuntimeError, match="Synthetic startup failure"):
            await start()
    else:
        await start()
    assert len(clients) == 1
    assert client_arguments == [
        {
            "base_url": "http://ocs-indexer:8000",
            "timeout": 12.5,
            "trust_env": False,
            "follow_redirects": False,
        }
    ]
    adapter = runtime.consultant.call_args.kwargs["occupation_references"]
    assert isinstance(adapter, OccupationReferenceClient)
    assert adapter.client is clients[0]
    assert runtime.situation.call_args.kwargs["excluded_work_enabled"] is True
    assert runtime.understanding.call_args.kwargs["excluded_work_enabled"] is True
    assert clients[0].is_closed
    runtime.sdk.close.assert_awaited_once()


async def test_database_startup_forwards_the_explicit_reference_configuration(runtime, monkeypatch):
    @asynccontextmanager
    async def saver_context(*args, **kwargs):
        yield runtime.saver

    runtime.saver.setup = AsyncMock()
    runtime.saver.conn = Mock(spec=AsyncConnection)
    runtime.saver.pipe = None
    monkeypatch.setattr(bootstrap.AsyncPostgresSaver, "from_conn_string", saver_context)
    start_model = AsyncMock()
    monkeypatch.setattr(bootstrap, "_start_model_runtime", start_model)
    reference_settings = configuration.OccupationReferenceSettings("http://ocs-indexer:8000")
    configured = configuration.Settings(
        model=runtime.model, occupation_references=reference_settings
    )
    async with AsyncExitStack() as resources:
        await bootstrap._start_database_runtime(
            runtime.app, configured, runtime.database, resources, composition=runtime.composition
        )
    assert start_model.call_args.kwargs["occupation_references"] is reference_settings
