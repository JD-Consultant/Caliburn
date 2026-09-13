"""Resource-order/failure probes; fake OS and DB, never assign pytest to a Job."""

from types import SimpleNamespace
from uuid import uuid4

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.store.memory import InMemoryStore
import pytest

import jd_relational.host_runtime as host
from jd_relational.windows_host import HostError


URL = "postgresql+psycopg://synthetic:private-password@127.0.0.1:55436/test"


def child():
    graph = StateGraph(MessagesState)
    graph.add_node("consultant", lambda state: pytest.fail("No model/graph invocation is allowed."))
    graph.add_edge(START, "consultant")
    graph.add_edge("consultant", END)
    return graph.compile()


@pytest.mark.parametrize("url,schema,consultant", [
    ("sqlite:///local.db", "jd_runtime", True),
    ("postgresql+psycopg://user@remote.invalid/test", "jd_runtime", True),
    (URL + "?options=hidden", "jd_runtime", True),
    (URL, "public", True), (URL, "pg_temp", True), (URL, "jd;DROP", True),
    (URL, "jd_runtime", False),
])
def test_invalid_configuration_has_no_native_or_db_side_effect(monkeypatch, url, schema, consultant):
    def forbidden(*args, **kwargs):
        pytest.fail("Configuration rejection must precede bootstrap/resources.")
    monkeypatch.setattr(host, "bootstrap_host", forbidden)
    monkeypatch.setattr(host.sa, "create_engine", forbidden)
    with pytest.raises(host.HostStorageError, match="^invalid_host_configuration$"):
        host.open_manual_host(str(uuid4()), url, checkpoint_schema=schema,
                              consultant=child() if consultant else None)


def test_existing_host_blocks_before_any_app_database_resource(monkeypatch):
    def busy(*args):
        raise HostError("host_already_running")
    def forbidden(*args, **kwargs):
        pytest.fail("A competing host must not open database resources.")
    monkeypatch.setattr(host, "bootstrap_host", busy)
    monkeypatch.setattr(host.sa, "create_engine", forbidden)
    with pytest.raises(HostError, match="^host_already_running$"):
        host.open_manual_host(str(uuid4()), URL, checkpoint_schema="jd_runtime", consultant=child())


class Connection:
    def __init__(self, events, name="connection"):
        self.events, self.missing, self.name = events, False, name

    def execute(self, statement, params=None):
        pytest.fail("Resource-order tests stub the shared read-only prerequisite helper.")

    def close(self):
        self.events.append(self.name + "_closed")


@pytest.fixture
def resources(monkeypatch):
    events = []
    engine = SimpleNamespace(dialect=SimpleNamespace(name="postgresql", driver="psycopg"),
                             dispose=lambda: events.append("engine_disposed"))
    memory_engine = SimpleNamespace(pool=object())
    engine.pool = memory_engine.pool
    def options(**kwargs):
        assert kwargs == {"schema_translate_map": {None: "jd_runtime"}}
        events.append("memory_engine")
        return memory_engine
    engine.execution_options = options
    connection = Connection(events)
    store_connection = Connection(events, "store_connection")
    lease = SimpleNamespace(require_previous_stopped=lambda: events.append("lease_check"))
    def bootstrap(key):
        events.append("bootstrap")
        return lease
    def create_engine(*args, **kwargs):
        assert events[:2] == ["bootstrap", "lease_check"]
        events.append("engine")
        return engine
    def connect(**kwargs):
        is_store = "connection" in events
        events.append("connection")
        assert kwargs["autocommit"] is True and kwargs["prepare_threshold"] == 0
        assert kwargs["options"] == "-csearch_path=jd_runtime"
        return store_connection if is_store else connection
    def check(connection, schema):
        events.append("schema_checked")
        assert schema == "jd_runtime"
        if connection.missing:
            raise ValueError("synthetic schema failure")
    class Saver(InMemorySaver):
        MIGRATIONS = ("synthetic native migration",)
        def __init__(self, connection, **kwargs):
            super().__init__()
    class Store(InMemoryStore):
        def __init__(self, connection):
            super().__init__()
            assert connection is store_connection
    monkeypatch.setattr(host, "bootstrap_host", bootstrap)
    monkeypatch.setattr(host.sa, "create_engine", create_engine)
    monkeypatch.setattr(host, "Connection", SimpleNamespace(connect=connect))
    monkeypatch.setattr(host, "PostgresSaver", Saver)
    monkeypatch.setattr(host, "PostgresStore", Store)
    monkeypatch.setattr(host, "check_installed", check)
    return events, connection


def test_native_bootstrap_precedes_resources_and_open_is_not_write_readiness(resources, monkeypatch):
    events, _ = resources
    opened = host.open_manual_host(str(uuid4()), URL, checkpoint_schema="jd_runtime", consultant=child())
    assert opened.store_connection is not opened.saver_connection
    assert opened.graph.store is opened.store
    assert opened.memory_engine.pool is opened.engine.pool
    assert not opened.runtime.ready
    with monkeypatch.context() as patch:
        patch.setattr(opened.runtime, "close", lambda **kwargs: False)
        assert not opened.close(timeout=0.01)
        assert not any(event.endswith("_closed") for event in events) and "engine_disposed" not in events
    assert opened.close(timeout=1)
    assert events[-3:] == ["store_connection_closed", "connection_closed", "engine_disposed"]


@pytest.mark.parametrize("failure", ["store", "graph"])
def test_partial_memory_open_closes_both_connections_and_shared_pool(resources, monkeypatch, failure):
    events, _ = resources
    def fail(*args, **kwargs):
        raise ValueError("private database detail")
    monkeypatch.setattr(host, "PostgresStore" if failure == "store" else "build_document_graph", fail)
    with pytest.raises(host.HostStorageError, match="^host_storage_unavailable$"):
        host.open_manual_host(str(uuid4()), URL, checkpoint_schema="jd_runtime", consultant=child())
    assert events[-3:] == ["store_connection_closed", "connection_closed", "engine_disposed"]


def test_store_close_failure_does_not_skip_remaining_cleanup(resources, monkeypatch):
    events, _ = resources
    opened = host.open_manual_host(str(uuid4()), URL, checkpoint_schema="jd_runtime", consultant=child())
    def fail():
        events.append("store_close_failed")
        raise OSError("private driver cause")
    monkeypatch.setattr(opened.store_connection, "close", fail)
    assert opened.close(timeout=1) is False
    assert events[-3:] == ["store_close_failed", "connection_closed", "engine_disposed"]


def test_configuration_recheck_failure_precedes_database_resources(monkeypatch):
    from jd_relational.local_configuration import ConfigurationError
    events = []
    monkeypatch.setattr(host, "bootstrap_host", lambda _: SimpleNamespace(
        require_previous_stopped=lambda: events.append("lease_checked")))
    monkeypatch.setattr(host.sa, "create_engine", lambda *_, **__: pytest.fail("No database resource."))
    def changed():
        events.append("configuration_checked")
        raise ConfigurationError("configuration_changed")
    with pytest.raises(ConfigurationError, match="configuration_changed"):
        host.open_manual_host(str(uuid4()), URL, checkpoint_schema="jd_runtime", consultant=child(),
            _configuration_check=changed)
    assert events == ["lease_checked", "configuration_checked"]


def test_missing_schema_is_rejected_without_setup_and_resources_are_closed(resources):
    events, connection = resources
    connection.missing = True
    with pytest.raises(host.HostStorageError, match="^host_storage_unavailable$") as error:
        host.open_manual_host(str(uuid4()), URL, checkpoint_schema="jd_runtime", consultant=child())
    assert error.value.__suppress_context__ and "private-password" not in str(error.value)
    assert events[-2:] == ["connection_closed", "engine_disposed"]
