"""Windows process bootstrap before any App database resource is opened.

The executable calls finish_startup before serving mutations, and drains this
host before normal process exit. OS handles remain process-owned until exit.
No model, environment configuration, schema setup, or graph replay occurs here.
"""

from dataclasses import dataclass
import re

from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.graph.state import CompiledStateGraph
from langgraph.store.postgres import PostgresStore
from psycopg import Connection
from psycopg.rows import dict_row
import sqlalchemy as sa

from .manual_runtime import ManualRuntime
from .runtime_checkpoints import DocumentCheckpoints, build_document_graph
from .storage.service import JdStorage
from .storage_setup import check_installed
from .windows_host import HostLease, bootstrap_host


class HostStorageError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


@dataclass(repr=False)
class ManualHost:
    lease: HostLease
    engine: sa.Engine
    saver_connection: Connection
    graph: CompiledStateGraph
    checkpoints: DocumentCheckpoints
    runtime: ManualRuntime
    store_connection: Connection
    store: PostgresStore
    memory_engine: sa.Engine

    def close(self, *, timeout=10) -> bool:
        if not self.runtime.close(timeout=timeout):
            return False  # Live admission/recovery/writer still needs these resources.
        closed = True
        for cleanup in (self.store_connection.close, self.saver_connection.close, self.engine.dispose):
            try:
                cleanup()
            except Exception:
                closed = False
        return closed


def open_manual_host(instance_key: str, database_url: str, *, checkpoint_schema: str,
                     consultant: CompiledStateGraph, _configuration_check=None) -> ManualHost:
    """One configured local dataset per stable installation key, no migrations.

    Call only in a dedicated App process. Failure after bootstrap requires that
    process to exit; it must not try another installation key in the same process.
    """
    try:
        url = sa.make_url(database_url)
        if (url.drivername != "postgresql+psycopg" or url.host not in {"127.0.0.1", "localhost"}
                or not url.database or not url.username or url.query
                or type(checkpoint_schema) is not str
                or re.fullmatch(r"[a-z][a-z0-9_]{0,62}", checkpoint_schema) is None
                or checkpoint_schema in {"public", "pg_catalog", "information_schema"}
                or checkpoint_schema.startswith("pg_")
                or not isinstance(consultant, CompiledStateGraph)
                or _configuration_check is not None and not callable(_configuration_check)):
            raise ValueError()
    except Exception:
        raise HostStorageError("invalid_host_configuration") from None
    lease = bootstrap_host(instance_key)
    if _configuration_check is not None:
        lease.require_previous_stopped()
        _configuration_check()  # Still no database resource has been opened.
    engine, connection, store_connection = None, None, None
    try:
        lease.require_previous_stopped()
        engine = sa.create_engine(url, hide_parameters=True, connect_args={
            "connect_timeout": 5, "options": "-csearch_path=public"})
        connection = Connection.connect(host=url.host, port=url.port or 5432,
            dbname=url.database, user=url.username, password=url.password,
            options=f"-csearch_path={checkpoint_schema}", connect_timeout=5,
            autocommit=True, row_factory=dict_row, prepare_threshold=0)
        # Read-only prerequisite checks: setup remains an explicit operator action.
        check_installed(connection, checkpoint_schema)
        # Separate framework owners must not interleave pipelines/transactions
        # on the same psycopg connection. Both still belong to this host drain.
        store_connection = Connection.connect(host=url.host, port=url.port or 5432,
            dbname=url.database, user=url.username, password=url.password,
            options=f"-csearch_path={checkpoint_schema}", connect_timeout=5,
            autocommit=True, row_factory=dict_row, prepare_threshold=0)
        store = PostgresStore(store_connection)
        # One fixed schema map per publication Session; same pool as JD, without
        # modifying the JD engine's public search_path or global ORM metadata.
        memory_engine = engine.execution_options(schema_translate_map={None: checkpoint_schema})
        saver = PostgresSaver(connection, serde=JsonPlusSerializer(allowed_msgpack_modules=None))
        graph = build_document_graph(consultant, saver, store=store)
        checkpoints = DocumentCheckpoints(graph)
        owner = ManualRuntime(checkpoints, lambda authority: JdStorage(engine, authority), previous_host=lease)
        return ManualHost(lease, engine, connection, graph, checkpoints, owner,
                          store_connection, store, memory_engine)
    except Exception:
        for cleanup in (store_connection.close if store_connection is not None else None,
                        connection.close if connection is not None else None,
                        engine.dispose if engine is not None else None):
            if cleanup is not None:
                try:
                    cleanup()
                except Exception:
                    pass
        raise HostStorageError("host_storage_unavailable") from None
