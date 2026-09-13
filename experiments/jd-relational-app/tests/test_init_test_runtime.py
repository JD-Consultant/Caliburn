"""Explicit synthetic initializer ordering; fake DB, no Windows/provider/DDL."""
from contextlib import contextmanager
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


spec = importlib.util.spec_from_file_location("init_test_runtime_probe",
    Path(__file__).resolve().parents[1] / "scripts" / "init_test_runtime.py")
initializer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(initializer)


def test_unknown_schema_is_rejected_before_connect(monkeypatch):
    monkeypatch.setattr(initializer, "Connection", SimpleNamespace(connect=lambda **_: pytest.fail("No DB")))
    with pytest.raises(ValueError):
        initializer.main("public")


@pytest.fixture
def resources(monkeypatch):
    events, state = [], {"tables": {}, "native_v": [], "store_v": [], "invalid": False,
                         "wrong_identity": False, "publication_error": False}
    native = initializer.NATIVE_TABLES
    store = {"store", "store_migrations"}
    publication = {"q019_document_memory_head", "q019_memory_publication_receipt"}
    class Result:
        def __init__(self, rows): self.rows = rows
        def fetchone(self): return self.rows[0]
        def fetchall(self): return self.rows
        def __iter__(self): return iter(self.rows)
    class Connection:
        def execute(self, statement, params=None):
            text = str(statement)
            if "current_database()" in text:
                return Result([{"db": "wrong" if state["wrong_identity"] else "caliburn_jd_relational_test",
                    "usr": "jd_test", "version": 180006}])
            if "CREATE SCHEMA" in text: events.append("schema")
            elif "SET search_path" in text: events.append("search_path")
            else: pytest.fail("Unexpected initializer SQL: " + text)
            return Result([])
    conn = Connection()
    @contextmanager
    def connect(**kwargs):
        assert kwargs["host"] == "127.0.0.1" and kwargs["port"] == 55436
        assert kwargs["dbname"] == "caliburn_jd_relational_test" and kwargs["autocommit"] is True
        events.append("connect")
        yield conn
    class Saver:
        MIGRATIONS = tuple(range(10))
        def __init__(self, connection): assert connection is conn
        def setup(self):
            events.append("saver_setup")
            state["tables"].update(dict.fromkeys(native, {})); state["native_v"] = list(range(10))
    class Store:
        MIGRATIONS = tuple(range(4))
        def __init__(self, connection): assert connection is conn
        def setup(self):
            events.append("store_setup")
            state["tables"].update(dict.fromkeys(store, {})); state["store_v"] = list(range(4))
    class SqlConnection:
        def execution_options(self, **kwargs):
            assert kwargs == {"schema_translate_map": {None: state["schema"]}}
            events.append("schema_map")
            return self
    class Engine:
        @contextmanager
        def begin(self):
            events.append("publication_begin")
            yield SqlConnection()
            events.append("publication_commit")
        def dispose(self): events.append("dispose")
    def create_engine(url, **kwargs):
        assert url.host == "127.0.0.1" and url.port == 55436 and url.database == "caliburn_jd_relational_test"
        events.append("engine")
        return Engine()
    def create_all(connection):
        assert isinstance(connection, SqlConnection)
        events.append("publication_setup")
        if state["publication_error"]: raise RuntimeError("synthetic failure")
        state["tables"].update(dict.fromkeys(publication, {}))
    def snapshot(connection, schema):
        assert connection is conn
        if schema == "public": return {"jd_document": "unchanged"}
        state["schema"] = schema
        return dict(state["tables"])
    def require_jd(connection, snapshot, *, allow_empty):
        assert not allow_empty and snapshot == {"jd_document": "unchanged"}
    def require_native(snapshot, versions, *, complete):
        events.append("native_complete" if complete else "native_preflight")
        assert set(snapshot) <= native
        if complete: assert set(snapshot) == native and versions == list(range(10))
    def require_runtime(connection, schema, snapshot, *, complete):
        events.append("runtime_complete" if complete else "runtime_preflight")
        if state["invalid"]: raise RuntimeError("unknown memory shape")
        if complete: assert set(snapshot) == native | store | publication
    monkeypatch.setattr(initializer, "Connection", SimpleNamespace(connect=connect))
    monkeypatch.setattr(initializer, "PostgresSaver", Saver)
    monkeypatch.setattr(initializer, "PostgresStore", Store)
    monkeypatch.setattr(initializer.sa, "create_engine", create_engine)
    monkeypatch.setattr(initializer.MemoryPublicationBase.metadata, "create_all", create_all)
    monkeypatch.setattr(initializer.storage_setup, "_snapshot", snapshot)
    monkeypatch.setattr(initializer.storage_setup, "_require_jd", require_jd)
    monkeypatch.setattr(initializer.storage_setup, "_require_native", require_native)
    monkeypatch.setattr(initializer.storage_setup, "_require_runtime", require_runtime)
    monkeypatch.setattr(initializer.storage_setup, "_native_versions", lambda *args: state["native_v"])
    monkeypatch.setattr(initializer.storage_setup, "_store_versions", lambda *args: state["store_v"])
    monkeypatch.setattr(initializer.storage_setup, "_other_objects", lambda *args: [])
    return state, events


def test_pure_runtime_stays_four_tables_and_never_creates_memory(resources):
    state, events = resources
    initializer.main("jd_runtime_test")
    assert set(state["tables"]) == initializer.NATIVE_TABLES
    assert "store_setup" not in events and "engine" not in events


@pytest.mark.parametrize("schema", ["jd_host_test", "jd_ai_host_test"])
def test_known_host_schema_uses_official_store_and_transactional_publication(resources, schema):
    state, events = resources
    state["tables"] = dict.fromkeys(initializer.NATIVE_TABLES, {})
    state["native_v"] = list(range(10))
    initializer.main(schema)
    assert set(state["tables"]) == initializer.HOST_TABLES
    assert "saver_setup" not in events  # Existing saved conversations are not reinitialized.
    assert events.index("runtime_preflight") < events.index("store_setup") < events.index("publication_begin")
    assert events.index("schema_map") < events.index("publication_setup") < events.index("publication_commit")
    assert events[-1] == "runtime_complete" and events.count("dispose") == 1


def test_unknown_existing_memory_profile_stops_before_any_ddl(resources):
    state, events = resources
    state["invalid"] = True
    with pytest.raises(RuntimeError, match="unknown memory shape"):
        initializer.main("jd_host_test")
    assert events == ["connect", "runtime_preflight"]


def test_wrong_fixture_identity_stops_before_schema_profile_or_ddl(resources):
    state, events = resources
    state["wrong_identity"] = True
    with pytest.raises(RuntimeError, match="Unexpected test database identity"):
        initializer.main("jd_ai_host_test")
    assert events == ["connect"]


def test_publication_failure_disposes_engine_without_claiming_complete(resources):
    state, events = resources
    state["publication_error"] = True
    with pytest.raises(RuntimeError, match="synthetic failure"):
        initializer.main("jd_host_test")
    assert "publication_commit" not in events and events[-1] == "dispose"
    assert "runtime_complete" not in events


def test_complete_host_fixture_does_not_repeat_any_setup(resources):
    state, events = resources
    state["tables"] = dict.fromkeys(initializer.HOST_TABLES, {})
    state["native_v"], state["store_v"] = list(range(10)), list(range(4))
    initializer.main("jd_host_test")
    assert not any(event.endswith("_setup") or event in {"engine", "schema"} for event in events)
    assert events[-1] == "runtime_complete"
