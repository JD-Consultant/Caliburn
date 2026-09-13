"""Bounded Memory schema profiles; no database or provider in these tests."""
import pytest

from jd_relational import storage_memory_profile as profile, storage_setup as setup
from test_storage_setup import Rows


@pytest.mark.parametrize("last,ahead", [(-1, False), (-1, True), (0, False), (0, True),
    (1, False), (1, True), (2, False), (2, True), (3, False)])
def test_known_store_prefix_or_single_ddl_ahead_is_resumable(last, ahead):
    setup._require_store(profile.store_expected(last + int(ahead)), list(range(last + 1)), complete=False)


def test_empty_store_is_only_allowed_during_initialization():
    setup._require_store({}, [], complete=False)
    with pytest.raises(setup.StorageSetupError, match="^schema_mismatch$"):
        setup._require_store({}, [], complete=True)


@pytest.mark.parametrize("versions", [[1], [0, 2], [False], list(range(5))])
def test_unknown_or_noncontiguous_store_versions_are_rejected(versions):
    with pytest.raises(setup.StorageSetupError, match="^schema_mismatch$"):
        setup._require_store(profile.store_expected(3), versions, complete=False)


def test_more_than_one_store_ddl_ahead_is_not_adopted():
    with pytest.raises(setup.StorageSetupError, match="^schema_mismatch$"):
        setup._require_store(profile.store_expected(2), [0], complete=False)


@pytest.mark.parametrize("fault", ["column", "default", "predicate", "unknown_index"])
def test_same_name_store_wrong_shape_is_rejected(fault):
    snapshot = profile.store_expected(3)
    if fault == "column":
        snapshot["store"]["columns"]["ttl_minutes"] = ("bigint", False)
    elif fault == "default":
        snapshot["store"]["defaults"]["created_at"] = "now()"
    elif fault == "predicate":
        snapshot["store"]["indexes"]["idx_store_expires_at"] = (("expires_at",), False, "(expires_at IS NULL)")
    else:
        snapshot["store"]["indexes"]["unexpected"] = (("key",), False, None)
    with pytest.raises(setup.StorageSetupError, match="^schema_mismatch$"):
        setup._require_store(snapshot, list(range(4)), complete=True)


def runtime_ports(monkeypatch, snapshot, *, saver_versions=10, store_versions=4):
    monkeypatch.setattr(setup, "_native_versions", lambda *_: list(range(saver_versions)))
    monkeypatch.setattr(setup, "_store_versions", lambda *_: list(range(store_versions)))
    memory = {name: table for name, table in snapshot.items() if name in profile.STORE_TABLES | profile.PUBLICATION_TABLES}
    monkeypatch.setattr(profile, "read_index_options", lambda *_: profile.index_options_expected(memory))


def test_complete_runtime_requires_all_eight_known_tables(monkeypatch):
    snapshot = {**setup._native_expected(9), **profile.store_expected(3), **profile.publication_expected()}
    assert len(snapshot) == 8
    runtime_ports(monkeypatch, snapshot)
    setup._require_runtime(object(), "jd_runtime", snapshot, complete=True)
    snapshot.pop("q019_memory_publication_receipt")
    with pytest.raises(setup.StorageSetupError, match="^schema_mismatch$"):
        setup._require_runtime(object(), "jd_runtime", snapshot, complete=False)


def test_later_memory_objects_do_not_hide_unfinished_saver(monkeypatch):
    snapshot = {**setup._native_expected(8), **profile.store_expected(3)}
    runtime_ports(monkeypatch, snapshot, saver_versions=9)
    with pytest.raises(setup.StorageSetupError, match="^schema_mismatch$"):
        setup._require_runtime(object(), "jd_runtime", snapshot, complete=False)


@pytest.mark.parametrize("fault", ["opclass", "descending"])
def test_same_column_prefix_index_requires_native_operator_and_order(monkeypatch, fault):
    snapshot = {**setup._native_expected(9), **profile.store_expected(3), **profile.publication_expected()}
    runtime_ports(monkeypatch, snapshot)
    options = profile.index_options_expected({**profile.store_expected(3), **profile.publication_expected()})
    options["store_prefix_idx"] = ((('pg_catalog', 'text_ops'),), (0,)) if fault == "opclass" else (
        (('pg_catalog', 'text_pattern_ops'),), (3,))
    monkeypatch.setattr(profile, "read_index_options", lambda *_: options)
    with pytest.raises(setup.StorageSetupError, match="^schema_mismatch$"):
        setup._require_runtime(object(), "jd_runtime", snapshot, complete=True)


def test_store_migration_receipts_are_not_memory_data():
    class Connection:
        def execute(self, statement):
            assert "store_migrations" not in statement.as_string()
            return Rows()
    setup._require_no_data(Connection(), "jd_runtime", profile.store_expected(3))


def test_existing_memory_data_blocks_initialization_resume():
    class Connection:
        def execute(self, statement):
            return Rows([{"present": 1}])
    with pytest.raises(setup.StorageSetupError, match="^initialization_recovery_required$"):
        setup._require_no_data(Connection(), "jd_runtime", profile.publication_expected())
