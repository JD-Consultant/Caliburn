"""Bounded setup gates; no provider or database in this module."""
from types import SimpleNamespace

import pytest

from jd_relational.local_configuration import configuration_phase, new_configuration
from jd_relational import storage_setup as setup


def settings(phase="initialization_pending"):
    value = new_configuration(host="127.0.0.1", port=55436, database="synthetic",
        username="synthetic", password="private-secret", checkpoint_schema="jd_runtime",
        api_port=3002, allowed_origins=("http://127.0.0.1:3001",))
    if phase != "initialization_pending":
        value = configuration_phase(value, "initializing")
    if phase == "ready":
        value = configuration_phase(value, "ready")
    return value


@pytest.mark.parametrize("phase", ["initialization_pending", "ready"])
def test_setup_rejects_wrong_phase_without_connecting(monkeypatch, phase):
    monkeypatch.setattr(setup, "_connect", lambda *_: pytest.fail("No connection before phase gate"))
    with pytest.raises(setup.StorageSetupError, match="^initialization_required$"):
        setup.setup_database(settings(phase), True)


@pytest.mark.parametrize("lease", [True, False, None, SimpleNamespace(require_previous_stopped=lambda: None)])
def test_setup_requires_native_lease_not_boolean_or_duck_proof(monkeypatch, lease):
    monkeypatch.setattr(setup, "_connect", lambda *_: pytest.fail("No connection without real lease"))
    with pytest.raises(setup.StorageSetupError, match="^host_lease_invalid$"):
        setup.setup_database(settings("initializing"), lease)


def test_empty_check_is_only_for_pending_configuration(monkeypatch):
    monkeypatch.setattr(setup, "_connect", lambda *_: pytest.fail("No connection before phase gate"))
    with pytest.raises(setup.StorageSetupError, match="^initialization_required$"):
        setup.check_empty_database(settings("ready"))


def test_connection_failure_never_exposes_secret(monkeypatch):
    def fail(*args):
        raise RuntimeError("private-secret in connection failure")
    monkeypatch.setattr(setup, "_connect", fail)
    with pytest.raises(setup.StorageSetupError) as caught:
        setup.check_empty_database(settings())
    assert caught.value.code == "storage_unavailable"
    assert "private-secret" not in str(caught.value)
    assert caught.value.__suppress_context__


@pytest.fixture
def version_table():
    return {"checkpoint_migrations": {
        "columns": {"v": ("integer", True)},
        "defaults": {},
        "constraints": {"checkpoint_migrations_pkey": ("p", ("v",))},
        "indexes": {"checkpoint_migrations_pkey": (("v",), True, None)},
    }}


def test_native_empty_and_first_ddl_before_version_are_resumable(version_table):
    setup._require_native({}, [], complete=False)
    setup._require_native(version_table, [], complete=False)
    setup._require_native(version_table, [0], complete=False)


@pytest.mark.parametrize("versions", [[1], [0, 2], [-1], [False], list(range(11))])
def test_native_rejects_noncontiguous_future_or_coerced_versions(version_table, versions):
    with pytest.raises(setup.StorageSetupError, match="^schema_mismatch$"):
        setup._require_native(version_table, versions, complete=False)


def test_native_does_not_accept_missing_already_recorded_table(version_table):
    with pytest.raises(setup.StorageSetupError, match="^schema_mismatch$"):
        setup._require_native(version_table, [0, 1], complete=False)


def test_native_rejects_same_name_wrong_shape(version_table):
    version_table["checkpoint_migrations"]["columns"]["v"] = ("text", True)
    with pytest.raises(setup.StorageSetupError, match="^schema_mismatch$"):
        setup._require_native(version_table, [0], complete=False)


def test_native_rejects_objects_more_than_next_ddl_ahead(version_table):
    version_table["checkpoint_blobs"] = {"columns": {}, "constraints": {}, "indexes": {}}
    with pytest.raises(setup.StorageSetupError, match="^schema_mismatch$"):
        setup._require_native(version_table, [0], complete=False)


def test_partial_native_state_is_never_installed(version_table):
    with pytest.raises(setup.StorageSetupError, match="^schema_mismatch$"):
        setup._require_native(version_table, [0], complete=True)


def test_native_lease_must_belong_to_configured_installation(monkeypatch):
    from jd_relational.windows_host import HostLease
    proof = object.__new__(HostLease)
    proof._instance_key = "different-installation"
    monkeypatch.setattr(HostLease, "require_previous_stopped", lambda self: None)
    monkeypatch.setattr(setup, "_connect", lambda *_: pytest.fail("Wrong lease must not connect"))
    with pytest.raises(setup.StorageSetupError, match="^host_lease_invalid$"):
        setup.setup_database(settings("initializing"), proof)


class Rows(list):
    def fetchone(self):
        return self[0] if self else None

    def fetchall(self):
        return list(self)


def test_invalid_concurrent_index_is_rejected_before_any_native_setup():
    class Conn:
        def execute(self, statement, params=None):
            assert statement.startswith("SELECT")
            if "relkind AS kind" in statement:
                return Rows([{"name": "checkpoints", "kind": "r"},
                    {"name": "checkpoints_thread_id_idx", "kind": "i"}])
            if "FROM pg_catalog.pg_attribute" in statement or "FROM pg_catalog.pg_constraint" in statement:
                return Rows()
            assert "FROM pg_catalog.pg_index" in statement
            return Rows([{"tbl": "checkpoints", "name": "checkpoints_thread_id_idx",
                "valid": False, "ready": True, "live": True}])
    with pytest.raises(setup.StorageSetupError, match="^initialization_recovery_required$"):
        setup._snapshot(Conn(), "jd_runtime")


def test_installed_check_suppresses_raw_database_cause():
    class Conn:
        def execute(self, *args):
            raise RuntimeError("private-secret")
    with pytest.raises(setup.StorageSetupError) as caught:
        setup.check_installed(Conn(), "jd_runtime")
    assert caught.value.code == "storage_unavailable"
    assert str(caught.value) == "storage_unavailable"
    assert caught.value.__suppress_context__


def test_canonical_profile_is_tied_to_this_fixed_migration():
    import hashlib
    from pathlib import Path
    profile = setup._ddl_profile()
    migration = Path(__file__).resolve().parents[1] / "migrations/versions/0001_jd_relational_initial.py"
    assert profile["source_migration_sha256"] == hashlib.sha256(migration.read_bytes()).hexdigest()
    schema = Path(__file__).resolve().parents[1] / "src/jd_relational/storage/schema.py"
    assert profile["source_schema_sha256"] == hashlib.sha256(schema.read_bytes()).hexdigest()
    assert profile["checks"]["jd_revision"]["ck_jd_revision_format_version"] == "CHECK ((format_version = 3))"
    assert profile["partial_indexes"]["jd_revision"]["uq_jd_revision_initial"] == "(origin = 'initial'::text)"


def test_saver_only_database_is_not_ready_for_memory_host(monkeypatch):
    monkeypatch.setattr(setup, "_identity", lambda *_: None)
    monkeypatch.setattr(setup, "_require_jd", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(setup, "_snapshot", lambda _connection, schema:
        {} if schema == "public" else setup._native_expected(9))
    monkeypatch.setattr(setup, "_native_versions", lambda *_: list(range(10)))
    monkeypatch.setattr(setup, "_other_objects", lambda *_: False)
    with pytest.raises(setup.StorageSetupError, match="^schema_mismatch$"):
        setup.check_installed(object(), "jd_runtime")
