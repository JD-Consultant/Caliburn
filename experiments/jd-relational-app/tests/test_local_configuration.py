"""Strict private configuration, with no file, database or environment fallback."""
import base64
import json
import traceback
from uuid import uuid4

import pytest

from jd_relational.local_configuration import (ConfigurationError, new_configuration,
    parse_configuration, encode_configuration, configuration_phase)


def new():
    return new_configuration(host="127.0.0.1", port=55436, database="synthetic_database",
        username="synthetic_user", password="synthetic-private-password", checkpoint_schema="jd_runtime",
        api_port=8007, allowed_origins=("http://127.0.0.1:3007",))


def test_explicit_initial_values_roundtrip_and_secret_free_repr():
    value = new()
    assert value.phase == "initialization_pending"
    assert value.installation_id != value.dataset_id
    assert len(value.signing_key_bytes()) == 32
    encoded = encode_configuration(value)
    loaded = parse_configuration(encoded)
    assert encode_configuration(loaded) == encoded
    assert "synthetic" not in repr(value) and "synthetic" not in str(value)
    assert value.signing_key not in repr(value)
    assert "synthetic-private-password" not in repr(value.database_url())


@pytest.mark.parametrize("key,value", [("format_version", True), ("format_version", 2),
    ("format_version", 1.0), ("phase", "automatic-repair"), ("dataset_id", "not-uuid"),
    ("installation_id", str(uuid4()).upper()), ("signing_key", "eA=="),
    ("port", True), ("port", 0), ("host", "remote.invalid"), ("api_port", 65536),
    ("checkpoint_schema", "public"), ("checkpoint_schema", "pg_temp"),
    ("username", ""), ("database", "a\x00b"),
    ("allowed_origins", ["http://127.0.0.1:3007/"]), ("allowed_origins", []),
    ("allowed_origins", ["https://remote.invalid"]), ("unexpected", "secret")])
def test_invalid_configuration_is_rejected_without_private_context(key, value):
    raw = json.loads(encode_configuration(new()))
    raw[key] = value
    with pytest.raises(ConfigurationError, match="^configuration_invalid$") as info:
        parse_configuration(json.dumps(raw).encode())
    assert "synthetic-private-password" not in ''.join(traceback.format_exception(info.value))


@pytest.mark.parametrize("raw", [b'', b'null', b'[]', b'{"phase":"ready","phase":"ready"}',
    b'{"x":NaN}', b'\xff', b'x' * 65537], ids=['empty', 'null', 'list', 'duplicate', 'constant', 'unicode', 'oversize'])
def test_malformed_configuration_stops(raw):
    with pytest.raises(ConfigurationError):
        parse_configuration(raw)


def test_phase_changes_preserve_the_fixed_configuration_and_ignore_environment(monkeypatch):
    initial = new()
    for variable in ("DATABASE_URL", "JD_DATABASE_URL", "PGPASSWORD", "OPENAI_API_KEY"):
        monkeypatch.setenv(variable, "must-not-be-read")
    active = configuration_phase(configuration_phase(initial, "initializing"), "ready")
    a, b = json.loads(encode_configuration(initial)), json.loads(encode_configuration(active))
    assert {key: val for key, val in a.items() if key != "phase"} == {
        key: val for key, val in b.items() if key != "phase"}
    with pytest.raises(ConfigurationError, match="^configuration_phase_conflict$"):
        configuration_phase(initial, "ready")
