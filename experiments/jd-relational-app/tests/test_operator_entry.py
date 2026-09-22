"""What the operator sees when starting the App, and what it must never say.

The entry point owns one configuration location and never takes an override,
so these cases point it at a temporary directory instead. Nothing here starts a
server, opens a provider or writes to the real installation path.
"""

import os
from pathlib import Path
from types import SimpleNamespace

import pytest

import jd_relational.__main__ as entry
from jd_relational.__main__ import main
from jd_relational.local_configuration import (
    configuration_phase,
    encode_configuration,
    new_configuration,
)

SECRETS = ("jd-local-test-only", "password", "postgresql://", "sk-", "127.0.0.1:55436")


@pytest.fixture
def nowhere(tmp_path, monkeypatch):
    """A configuration location that does not exist, and must stay that way."""
    location = tmp_path / "Caliburn" / "JDRelational" / "host.v1.dpapi"
    monkeypatch.setattr(entry, "default_config_path", lambda: location)
    yield location
    assert not location.exists(), "reporting a missing configuration must not create one"
    assert not location.parent.exists(), "nor its folder"


def test_status_on_a_machine_with_no_installation_explains_and_creates_nothing(nowhere, capsys):
    assert main(["status"]) == 1
    printed = capsys.readouterr()
    assert "尚未找到本機設定" in printed.err
    assert printed.out == ""


def test_serve_without_a_configuration_refuses_instead_of_installing(nowhere, capsys):
    assert main(["serve"]) == 1
    assert "尚未找到本機設定" in capsys.readouterr().err


def test_an_unexpected_failure_never_prints_its_own_message(nowhere, capsys, monkeypatch):
    """A driver error can carry a DSN, a password or a key. None may reach the screen."""
    def explode(*args, **kwargs):
        raise RuntimeError("connection to server at 127.0.0.1:55436 failed: "
                           "password authentication failed for user jd-local-test-only")

    monkeypatch.setattr(entry.ConfigFile, "read", explode)
    nowhere.parent.mkdir(parents=True)
    nowhere.write_bytes(b"synthetic")
    try:
        assert main(["status"]) == 1
        printed = capsys.readouterr()
        assert "操作未完成" in printed.err
        for secret in SECRETS:
            assert secret not in printed.err and secret not in printed.out, secret
    finally:
        nowhere.unlink()
        nowhere.parent.rmdir()
        nowhere.parent.parent.rmdir()


def test_an_interrupted_operation_stops_without_claiming_anything(nowhere, capsys, monkeypatch):
    def interrupted(*args, **kwargs):
        raise KeyboardInterrupt()

    monkeypatch.setattr(entry.ConfigFile, "read", interrupted)
    assert main(["status"]) == 130
    printed = capsys.readouterr()
    assert "操作已中止" in printed.err and "實際保存狀態" in printed.err


def test_every_known_failure_has_its_own_plain_message():
    # A code with no message would fall back to the generic line, which tells
    # the operator nothing about what to do next.
    for code, message in entry._MESSAGES.items():
        assert message.strip() and not message.startswith(code)
        assert not any(secret in message for secret in SECRETS[:3]), code


def test_the_entry_accepts_only_its_own_actions(nowhere):
    with pytest.raises(SystemExit) as stop:
        main(["restore-everything"])
    assert stop.value.code == 2


def test_serving_is_separate_from_initialising(nowhere, capsys, monkeypatch):
    """serve must never quietly initialise; that is an explicit, separate act."""
    called = []
    monkeypatch.setattr(entry, "initialize_configuration",
                        lambda *args, **kwargs: called.append(kwargs))
    assert main(["serve"]) == 1
    assert called == [], "serve initialised something"
    assert "尚未找到本機設定" in capsys.readouterr().err


def configured(phase="ready"):
    value = new_configuration(
        host="127.0.0.1",
        port=55436,
        database="synthetic",
        username="synthetic",
        password="private-fixture-password",
        checkpoint_schema="jd_runtime",
        api_port=8014,
        allowed_origins=("http://127.0.0.1:3002",),
    )
    if phase == "ready":
        value = configuration_phase(value, "initializing")
        value = configuration_phase(value, "ready")
    return value


def test_api_origin_projects_only_the_ready_loopback_endpoint(capsys, monkeypatch):
    """A launcher gets the configured API endpoint without reading secrets itself."""
    raw = encode_configuration(configured())
    monkeypatch.setattr(entry, "ConfigFile", lambda _path: SimpleNamespace(read=lambda: raw))

    assert main(["api-origin"]) == 0

    printed = capsys.readouterr()
    assert printed.out == "http://127.0.0.1:8014\n"
    assert printed.err == ""
    for secret in SECRETS:
        assert secret not in printed.out and secret not in printed.err


def test_api_origin_refuses_an_installation_that_is_not_ready(capsys, monkeypatch):
    raw = encode_configuration(configured("initialization_pending"))
    monkeypatch.setattr(entry, "ConfigFile", lambda _path: SimpleNamespace(read=lambda: raw))

    assert main(["api-origin"]) == 1

    printed = capsys.readouterr()
    assert printed.out == ""
    assert "初始化尚未完成" in printed.err
