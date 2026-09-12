"""Resource-order/failure probes; fake OS and DB, never assign pytest to a Job."""

from types import SimpleNamespace
from uuid import uuid4

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, MessagesState, StateGraph
import pytest

import jd_relational.host_runtime as host
from jd_relational.storage.schema import JD_TABLE_NAMES
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


class Rows(list):
    def fetchone(self):
        return self[0]

    def fetchall(self):
        return list(self)


class Connection:
    def __init__(self, events):
        self.events, self.missing = events, False

    def execute(self, statement, params=None):
        assert statement.startswith("SELECT"), "Host must not initialize or mutate schemas."
        if "server_version_num" in statement:
            return Rows([{"v": 180006}])
        if "pg_tables" in statement:
            names = JD_TABLE_NAMES | {"alembic_version"} if params is None else {
                "checkpoints", "checkpoint_blobs", "checkpoint_writes", "checkpoint_migrations"}
            return Rows({"tablename": name} for name in ([] if self.missing else names))
        if "alembic_version" in statement:
            return Rows([{"version_num": "20260913_0001"}])
        assert "checkpoint_migrations" in statement
        return Rows([{"v": 0}])

    def close(self):
        self.events.append("connection_closed")


@pytest.fixture
def resources(monkeypatch):
    events = []
    engine = SimpleNamespace(dialect=SimpleNamespace(name="postgresql", driver="psycopg"),
                             dispose=lambda: events.append("engine_disposed"))
    connection = Connection(events)
    lease = SimpleNamespace(require_previous_stopped=lambda: events.append("lease_check"))
    def bootstrap(key):
        events.append("bootstrap")
        return lease
    def create_engine(*args, **kwargs):
        assert events[:2] == ["bootstrap", "lease_check"]
        events.append("engine")
        return engine
    def connect(**kwargs):
        events.append("connection")
        assert kwargs["autocommit"] is True and kwargs["prepare_threshold"] == 0
        return connection
    class Saver(InMemorySaver):
        MIGRATIONS = ("synthetic native migration",)
        def __init__(self, connection, **kwargs):
            super().__init__()
    monkeypatch.setattr(host, "bootstrap_host", bootstrap)
    monkeypatch.setattr(host.sa, "create_engine", create_engine)
    monkeypatch.setattr(host, "Connection", SimpleNamespace(connect=connect))
    monkeypatch.setattr(host, "PostgresSaver", Saver)
    return events, connection


def test_native_bootstrap_precedes_resources_and_open_is_not_write_readiness(resources, monkeypatch):
    events, _ = resources
    opened = host.open_manual_host(str(uuid4()), URL, checkpoint_schema="jd_runtime", consultant=child())
    assert not opened.runtime.ready
    with monkeypatch.context() as patch:
        patch.setattr(opened.runtime, "close", lambda **kwargs: False)
        assert not opened.close(timeout=0.01)
        assert "connection_closed" not in events and "engine_disposed" not in events
    assert opened.close(timeout=1)
    assert events[-2:] == ["connection_closed", "engine_disposed"]


def test_missing_schema_is_rejected_without_setup_and_resources_are_closed(resources):
    events, connection = resources
    connection.missing = True
    with pytest.raises(host.HostStorageError, match="^host_storage_unavailable$") as error:
        host.open_manual_host(str(uuid4()), URL, checkpoint_schema="jd_runtime", consultant=child())
    assert error.value.__suppress_context__ and "private-password" not in str(error.value)
    assert events[-2:] == ["connection_closed", "engine_disposed"]
