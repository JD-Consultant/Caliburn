"""Orchestration failure probes. Fake OS/file/DB; native integration is separate."""
from types import SimpleNamespace, ModuleType
import sys

import pytest

import jd_relational.configured_host as configured
from jd_relational.config_file import ConfigFileError
from jd_relational.local_configuration import (new_configuration, encode_configuration,
    parse_configuration, configuration_phase, ConfigurationError)


CONNECTION = dict(host="127.0.0.1", port=55436, database="synthetic", username="synthetic",
    password="private-fixture-password", checkpoint_schema="jd_managed", api_port=8014,
    allowed_origins=("http://127.0.0.1:3002",))


class File:
    def __init__(self, events, value=None):
        self.events, self.value = events, value
        self.fail_phase = None
        self.fail_after_write = False

    def read(self):
        self.events.append("read")
        if self.value is None:
            raise ConfigFileError("configuration_missing")
        return self.value

    def create(self, value):
        self.events.append("create")
        if self.value is not None:
            raise ConfigFileError("configuration_exists")
        self.value = value

    def replace(self, value, *, expected):
        phase = parse_configuration(value).phase
        self.events.append("replace_" + phase)
        if self.value != expected:
            raise ConfigFileError("configuration_changed")
        if phase == self.fail_phase and not self.fail_after_write:
            raise ConfigFileError("configuration_write_unconfirmed")
        self.value = value
        if phase == self.fail_phase:
            raise ConfigFileError("configuration_write_unconfirmed")


def settings(phase):
    value = new_configuration(**CONNECTION)
    if phase in {"initializing", "ready"}:
        value = configuration_phase(value, "initializing")
    if phase == "ready":
        value = configuration_phase(value, "ready")
    if phase == "maintenance":
        value = parse_configuration(encode_configuration(value).replace(
            b'"initialization_pending"', b'"maintenance"'))
    return value


@pytest.fixture
def setup(monkeypatch):
    events = []
    lease = SimpleNamespace(require_previous_stopped=lambda: events.append("lease_check"))
    def bootstrap(key):
        events.append("bootstrap")
        return lease
    module = ModuleType("jd_relational.storage_setup")
    def empty(value):
        assert value.phase == "initialization_pending"
        events.append("empty_check")
    def initialize(value, owner):
        assert value.phase == "initializing" and owner is lease
        events.append("setup")
    module.check_empty_database = empty
    module.setup_database = initialize
    monkeypatch.setitem(sys.modules, "jd_relational.storage_setup", module)
    monkeypatch.setattr(configured, "bootstrap_host", bootstrap)
    return events, module


def test_initialization_records_phase_before_ddl_and_retains_fixed_identity(setup):
    events, _ = setup
    file = File(events)
    ready = configured.initialize_configuration(file, connection=CONNECTION)
    assert ready.phase == "ready" and parse_configuration(file.value) == ready
    assert events == ["create", "read", "bootstrap", "lease_check", "read", "empty_check",
        "lease_check", "replace_initializing", "read", "setup", "lease_check", "replace_ready", "read"]


@pytest.mark.parametrize("phase", ["initialization_pending", "initializing"])
def test_resume_reuses_ids_signer_and_connection_without_creating_new_configuration(setup, monkeypatch, phase):
    events, _ = setup
    original = settings(phase)
    file = File(events, encode_configuration(original))
    monkeypatch.setattr(configured, "new_configuration", lambda **_: pytest.fail("No new identities on resume."))
    ready = configured.initialize_configuration(file, resume=True)
    assert "create" not in events
    assert ("empty_check" in events) == (phase == "initialization_pending")
    assert {**original.model_dump(), "phase": "ready"} == ready.model_dump()


def test_nonempty_database_does_not_enter_initializing_or_execute_setup(setup):
    events, module = setup
    file = File(events)
    def nonempty(value):
        raise ValueError("database_not_empty")
    module.check_empty_database = nonempty
    with pytest.raises(ValueError, match="database_not_empty"):
        configured.initialize_configuration(file, connection=CONNECTION)
    assert parse_configuration(file.value).phase == "initialization_pending"
    assert "setup" not in events and "replace_initializing" not in events


@pytest.mark.parametrize("after_write", [False, True])
def test_initializing_file_write_failure_never_starts_ddl(setup, after_write):
    events, _ = setup
    file = File(events)
    file.fail_phase, file.fail_after_write = "initializing", after_write
    with pytest.raises(ConfigFileError, match="configuration_write_unconfirmed"):
        configured.initialize_configuration(file, connection=CONNECTION)
    assert "setup" not in events
    assert parse_configuration(file.value).phase == ("initializing" if after_write else "initialization_pending")


def test_setup_failure_retains_resume_phase_and_does_not_claim_ready(setup):
    events, module = setup
    file = File(events)
    def failure(*args):
        raise ValueError("storage_unavailable")
    module.setup_database = failure
    with pytest.raises(ValueError, match="storage_unavailable"):
        configured.initialize_configuration(file, connection=CONNECTION)
    assert parse_configuration(file.value).phase == "initializing"
    assert "replace_ready" not in events


@pytest.mark.parametrize("after_write", [False, True])
def test_ready_publication_failure_is_unconfirmed_and_new_read_establishes_phase(setup, after_write):
    events, _ = setup
    file = File(events)
    file.fail_phase, file.fail_after_write = "ready", after_write
    with pytest.raises(ConfigFileError, match="configuration_write_unconfirmed"):
        configured.initialize_configuration(file, connection=CONNECTION)
    assert "setup" in events
    assert parse_configuration(file.value).phase == ("ready" if after_write else "initializing")


def test_file_change_while_waiting_for_host_stops_before_database(setup, monkeypatch):
    events, _ = setup
    file = File(events, encode_configuration(settings("initializing")))
    def bootstrap(key):
        file.value = encode_configuration(settings("initializing"))
        return SimpleNamespace(require_previous_stopped=lambda: None)
    monkeypatch.setattr(configured, "bootstrap_host", bootstrap)
    with pytest.raises(ConfigurationError, match="configuration_changed"):
        configured.initialize_configuration(file, resume=True)
    assert "setup" not in events


@pytest.mark.parametrize("phase,code", [("ready", "configuration_already_ready"),
    ("maintenance", "configuration_maintenance")])
def test_resume_closed_phase_does_not_bootstrap_or_setup(setup, phase, code):
    events, _ = setup
    file = File(events, encode_configuration(settings(phase)))
    with pytest.raises(ConfigurationError, match=code):
        configured.initialize_configuration(file, resume=True)
    assert events == ["read"]


@pytest.mark.parametrize("phase", [None, "initialization_pending", "initializing", "maintenance"])
def test_ordinary_open_does_not_initialize_missing_or_incomplete_configuration(monkeypatch, phase):
    file = File([], None if phase is None else encode_configuration(settings(phase)))
    monkeypatch.setattr(configured, "open_manual_host", lambda *_, **__: pytest.fail("No database/native host."))
    with pytest.raises((ConfigFileError, ConfigurationError)):
        configured.open_configured_host(file, consultant=object())
    assert file.events == ["read"]


def test_ordinary_open_uses_fixed_values_and_rechecks_file_at_host_boundary(monkeypatch):
    value = settings("ready")
    file = File([], encode_configuration(value))
    def opened(key, url, *, checkpoint_schema, consultant, _configuration_check):
        assert key == value.installation_id and url == value.database_url()
        assert checkpoint_schema == value.checkpoint_schema
        _configuration_check()
        return SimpleNamespace(close=lambda **_: True)
    monkeypatch.setenv("DATABASE_URL", "must-not-use-environment")
    monkeypatch.setattr(configured, "open_manual_host", opened)
    result = configured.open_configured_host(file, consultant=object())
    assert result.settings == value and result.close()
    assert file.events == ["read", "read"]
    assert "private-fixture-password" not in repr(result)


def test_ordinary_open_file_changed_while_waiting_is_rejected(monkeypatch):
    value = settings("ready")
    file = File([], encode_configuration(value))
    def opened(*args, _configuration_check, **kwargs):
        file.value = encode_configuration(settings("ready"))
        _configuration_check()
        pytest.fail("Configuration changed before database resources.")
    monkeypatch.setattr(configured, "open_manual_host", opened)
    with pytest.raises(ConfigurationError, match="configuration_changed"):
        configured.open_configured_host(file, consultant=object())
