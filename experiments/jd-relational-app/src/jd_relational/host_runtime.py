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
from psycopg import Connection
from psycopg.rows import dict_row
import sqlalchemy as sa

from .manual_runtime import ManualRuntime
from .runtime_checkpoints import DocumentCheckpoints, build_document_graph
from .storage.schema import JD_TABLE_NAMES
from .storage.service import JdStorage
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

    def close(self, *, timeout=10) -> bool:
        if not self.runtime.close(timeout=timeout):
            return False  # Live admission/recovery/writer still needs these resources.
        try:
            self.saver_connection.close()
            self.engine.dispose()
        except Exception:
            return False
        return True


def open_manual_host(instance_key: str, database_url: str, *, checkpoint_schema: str,
                     consultant: CompiledStateGraph) -> ManualHost:
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
                or not isinstance(consultant, CompiledStateGraph)):
            raise ValueError()
    except Exception:
        raise HostStorageError("invalid_host_configuration") from None
    lease = bootstrap_host(instance_key)
    engine, connection = None, None
    try:
        lease.require_previous_stopped()
        engine = sa.create_engine(url, hide_parameters=True, connect_args={
            "connect_timeout": 5, "options": "-csearch_path=public"})
        connection = Connection.connect(host=url.host, port=url.port or 5432,
            dbname=url.database, user=url.username, password=url.password,
            options=f"-csearch_path={checkpoint_schema},public", connect_timeout=5,
            autocommit=True, row_factory=dict_row, prepare_threshold=0)
        # Read-only prerequisite checks: setup remains an explicit operator action.
        identity = connection.execute("SELECT current_setting('server_version_num')::integer AS v").fetchone()
        if identity["v"] != 180006:
            raise ValueError()
        public = {row["tablename"] for row in connection.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public'")}
        runtime = {row["tablename"] for row in connection.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname = %s", (checkpoint_schema,))}
        if (public != JD_TABLE_NAMES | {"alembic_version"}
                or runtime != {"checkpoints", "checkpoint_blobs", "checkpoint_writes", "checkpoint_migrations"}
                or connection.execute("SELECT version_num FROM public.alembic_version").fetchall()
                    != [{"version_num": "20260913_0001"}]):
            raise ValueError()
        saver = PostgresSaver(connection, serde=JsonPlusSerializer(allowed_msgpack_modules=None))
        versions = [row["v"] for row in connection.execute("SELECT v FROM checkpoint_migrations ORDER BY v")]
        if versions != list(range(len(saver.MIGRATIONS))):
            raise ValueError()
        graph = build_document_graph(consultant, saver)
        checkpoints = DocumentCheckpoints(graph)
        owner = ManualRuntime(checkpoints, lambda authority: JdStorage(engine, authority), previous_host=lease)
        return ManualHost(lease, engine, connection, graph, checkpoints, owner)
    except Exception:
        for cleanup in (connection.close if connection is not None else None,
                        engine.dispose if engine is not None else None):
            if cleanup is not None:
                try:
                    cleanup()
                except Exception:
                    pass
        raise HostStorageError("host_storage_unavailable") from None
