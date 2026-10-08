"""App 組裝值不共用可變設定，啟動失敗仍沿原 lifespan 釋放資源。"""

from contextlib import asynccontextmanager
from dataclasses import FrozenInstanceError, replace
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from psycopg import AsyncConnection

from caliburn import bootstrap
from caliburn.adapters.graph_checkpointer import create_graph_serializer
from caliburn.agents.job_consultant.configuration import ConsultantConfiguration
from caliburn.settings import DatabaseSettings, ModelSettings, Settings


def test_composition_defaults_are_immutable_and_app_creation_does_not_open_resources():
    from caliburn.app_composition import AppComposition

    defaults = AppComposition()
    assert defaults.consultant_configuration == ConsultantConfiguration()
    assert defaults.interview_plans_enabled is True
    factory = Mock(side_effect=AssertionError("Construction must not open I/O"))
    candidate = replace(defaults, create_responses_client=factory, open_checkpointer=factory)
    bootstrap.create_app(Settings(), composition=candidate)
    factory.assert_not_called()
    with pytest.raises(FrozenInstanceError):
        candidate.interview_plans_enabled = False


@pytest.mark.parametrize("failure", ["client", "runner"])
async def test_startup_failure_closes_resources_already_owned_by_lifespan(monkeypatch, failure):
    from caliburn.app_composition import AppComposition

    events = []
    settings = DatabaseSettings(url="postgresql://localhost/composition_test")

    async def close_database():
        events.append("database closed")

    database = SimpleNamespace(
        settings=settings,
        sessions=Mock(),
        verify_schema=AsyncMock(),
        close=close_database,
    )
    monkeypatch.setattr(bootstrap, "Database", lambda _settings: database)
    native = SimpleNamespace(
        conn=Mock(spec=AsyncConnection), pipe=None, serde=create_graph_serializer()
    )

    @asynccontextmanager
    async def open_checkpointer(database_settings):
        assert database_settings is settings
        events.append("saver opened")
        try:
            yield native
        finally:
            events.append("saver closed")

    async def close_sdk():
        events.append("sdk closed")

    def create_client(model):
        events.append("client requested")
        if failure == "client":
            raise RuntimeError("synthetic construction failure")
        return SimpleNamespace(close=close_sdk)

    if failure == "runner":
        monkeypatch.setattr(
            bootstrap,
            "ConsultantRunner",
            Mock(side_effect=RuntimeError("synthetic construction failure")),
        )
    app = bootstrap.create_app(
        Settings(database=settings, model=ModelSettings(api_key="synthetic")),
        composition=AppComposition(
            create_responses_client=create_client, open_checkpointer=open_checkpointer
        ),
    )
    with pytest.raises(RuntimeError, match="synthetic construction failure"):
        async with app.router.lifespan_context(app):
            pytest.fail("Failed construction cannot enter a running App")
    assert events == [
        "saver opened",
        "client requested",
        *(["sdk closed"] if failure == "runner" else []),
        "saver closed",
        "database closed",
    ]
    assert app.state.consultant_supervisor is None
    assert app.state.memory_supervisor is None


async def test_default_checkpointer_closes_connection_if_setup_fails(monkeypatch):
    from caliburn import app_composition

    events = []

    async def setup():
        events.append("setup")
        raise RuntimeError("synthetic setup failure")

    @asynccontextmanager
    async def connect(*args, **kwargs):
        assert kwargs["serde"] is not None
        events.append("opened")
        try:
            yield SimpleNamespace(setup=setup)
        finally:
            events.append("closed")

    monkeypatch.setattr(app_composition.AsyncPostgresSaver, "from_conn_string", connect)
    with pytest.raises(RuntimeError, match="synthetic setup failure"):
        async with app_composition.AppComposition().open_checkpointer(
            DatabaseSettings(url="postgresql://localhost/composition_test")
        ):
            pytest.fail("An uninitialized saver must not escape its factory")
    assert events == ["opened", "setup", "closed"]
