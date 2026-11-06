"""Agent HTTP 的明示啟用契約。"""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from caliburn.host.app import build_app
from tests.reference_configuration import (
    HOST_REFERENCE_CONFIGURATION,
    write_reference_configuration,
)


def test_unconfigured_agent_is_unavailable_without_model_calls() -> None:
    app = build_app(
        reference_configuration=HOST_REFERENCE_CONFIGURATION,
        database_url="postgresql+psycopg://localhost:1/offline",
    )
    with TestClient(app) as client:
        response = client.post(
            "/workspaces/00000000-0000-0000-0000-000000000001/agent/turns",
            json={
                "turn_id": "00000000-0000-0000-0000-000000000002",
                "input": "合成輸入",
            },
        )
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "agent_unavailable"


def test_main_rejects_incomplete_agent_configuration(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from caliburn.host.entrypoint import create_app

    path = tmp_path / "agent.json"
    path.write_text(
        '{"agent_id":"test","resume_version":"v1","model":"offline-model"}',
        encoding="utf-8",
    )
    monkeypatch.setenv(
        "CALIBURN_REBUILD_DATABASE_URL", "postgresql+psycopg://localhost:1/offline"
    )
    monkeypatch.setenv("CALIBURN_REBUILD_AGENT_CONFIG", str(path))
    monkeypatch.setenv(
        "CALIBURN_REBUILD_REFERENCE_CONFIG",
        str(write_reference_configuration(tmp_path)),
    )
    monkeypatch.delenv("CALIBURN_REBUILD_AGENT_CHECKPOINT_CONNINFO", raising=False)
    with pytest.raises(ValueError, match="CALIBURN_REBUILD_AGENT_CHECKPOINT_CONNINFO"):
        create_app()


@pytest.mark.parametrize(
    "extra, timeout_seconds", [("", 120.0), (',"sdk_timeout_seconds":12.5', 12.5)]
)
def test_configured_sdk_disables_retries_and_sets_network_timeout(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, extra: str, timeout_seconds: float
) -> None:
    import asyncio

    from caliburn.host.agent_settings import load_agent_configuration

    monkeypatch.setenv("OPENAI_API_KEY", "offline-test-key")
    path = tmp_path / "agent.json"
    path.write_text(
        '{"agent_id":"test","resume_version":"v1","model":"offline-model"'
        + extra
        + "}",
        encoding="utf-8",
    )
    config = load_agent_configuration(path, checkpoint_conninfo="host=localhost")

    async def check() -> None:
        async with config.client_factory() as client:
            assert client.max_retries == 0
            assert client.timeout == timeout_seconds

    asyncio.run(check(), loop_factory=asyncio.SelectorEventLoop)


@pytest.mark.parametrize("capacity", [1, 2])
def test_host_loads_positive_active_turn_capacity(
    tmp_path: Path, capacity: int
) -> None:
    from caliburn.host.agent_settings import load_agent_configuration

    path = tmp_path / "agent.json"
    path.write_text(
        '{"agent_id":"test","resume_version":"v1","model":"offline-model","max_active_turns":'
        + str(capacity)
        + "}",
        encoding="utf-8",
    )
    config = load_agent_configuration(path, checkpoint_conninfo="host=localhost")
    assert config.max_active_turns == capacity


@pytest.mark.parametrize("capacity", ["0", "-1", "1.5", "true", '"2"'])
def test_host_rejects_invalid_active_turn_capacity(
    tmp_path: Path, capacity: str
) -> None:
    from caliburn.host.agent_settings import load_agent_configuration

    path = tmp_path / "agent.json"
    path.write_text(
        '{"agent_id":"test","resume_version":"v1","model":"offline-model","max_active_turns":'
        + capacity
        + "}",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="設定檔"):
        load_agent_configuration(path, checkpoint_conninfo="host=localhost")


@pytest.mark.parametrize("capacity", [0, -1])
def test_programmatic_host_rejects_nonpositive_active_turn_capacity(
    capacity: int,
) -> None:
    from caliburn.host.agent_settings import AgentConfiguration

    with pytest.raises(ValueError, match="max_active_turns"):
        AgentConfiguration(
            agent_id="test",
            resume_version="v1",
            checkpoint_conninfo="host=localhost",
            model_settings={"model": "offline-model"},
            max_active_turns=capacity,
        )


@pytest.mark.parametrize("version", [None, '""', '"   "', "1", "true", '"v1\\u0000"'])
def test_host_rejects_invalid_resume_version(
    tmp_path: Path, version: str | None
) -> None:
    from caliburn.host.agent_settings import load_agent_configuration

    path = tmp_path / "agent.json"
    extra = "" if version is None else ',"resume_version":' + version
    path.write_text(
        '{"agent_id":"test","model":"offline-model"' + extra + "}",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="設定檔"):
        load_agent_configuration(path, checkpoint_conninfo="host=localhost")


@pytest.mark.parametrize("version", ["", "   ", "\t\n", "v1\0"])
def test_programmatic_host_rejects_invalid_resume_version(version: str) -> None:
    from caliburn.host.agent_settings import AgentConfiguration

    with pytest.raises(ValueError, match="resume_version"):
        AgentConfiguration(
            agent_id="test",
            resume_version=version,
            checkpoint_conninfo="host=localhost",
            model_settings={"model": "offline-model"},
        )


def test_host_preserves_valid_resume_version_exactly(tmp_path: Path) -> None:
    from caliburn.host.agent_settings import (
        AgentConfiguration,
        load_agent_configuration,
    )

    path = tmp_path / "agent.json"
    path.write_text(
        '{"agent_id":"test","resume_version":" v1 ","model":"offline-model"}',
        encoding="utf-8",
    )
    loaded = load_agent_configuration(path, checkpoint_conninfo="host=localhost")
    configured = AgentConfiguration(
        agent_id="test",
        resume_version=" v1 ",
        checkpoint_conninfo="host=localhost",
        model_settings={"model": "offline-model"},
    )
    assert loaded.resume_version == " v1 "
    assert configured.resume_version == " v1 "


@pytest.mark.parametrize("selection", [None, [], ["candidate", "shared"]])
def test_host_preserves_explicit_plugin_selection(
    tmp_path: Path, selection: list[str] | None
) -> None:
    from caliburn.host.agent_settings import load_agent_configuration

    path = tmp_path / "agent.json"
    path.write_text(
        json.dumps(
            {
                "agent_id": "test",
                "resume_version": "v1",
                "model": "offline-model",
                "bundles": [
                    {"module": "example.prompts", "plugins": selection},
                    {"module": "example.defaults"},
                ],
            }
        ),
        encoding="utf-8",
    )
    configured = load_agent_configuration(path, checkpoint_conninfo="host=localhost")
    assert configured.bundles[0].plugins == (
        tuple(selection) if selection is not None else None
    )
    assert configured.bundles[1].plugins is None
