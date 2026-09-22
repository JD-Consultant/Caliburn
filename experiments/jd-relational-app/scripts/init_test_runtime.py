"""Explicit native LangGraph initialization in the fixed synthetic test DB.

The 13 JD tables remain owned by public/Alembic. jd_runtime_test keeps four
native Saver tables; the two dedicated host schemas also require the adopted
Memory tables. This explicit fixture preparation never drops or clears data.
"""

import argparse

from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.store.postgres import PostgresStore
from caliburn_memory.publication import Base as MemoryPublicationBase
from psycopg import Connection, sql
from psycopg.rows import dict_row
import sqlalchemy as sa

from jd_relational import storage_setup, storage_memory_profile


RUNTIME_SCHEMA = "jd_runtime_test"
NATIVE_TABLES = {"checkpoint_migrations", "checkpoints", "checkpoint_blobs", "checkpoint_writes"}
HOST_SCHEMAS = {"jd_host_test", "jd_ai_host_test"}
HOST_TABLES = NATIVE_TABLES | storage_memory_profile.STORE_TABLES | storage_memory_profile.PUBLICATION_TABLES
SCHEMAS = (RUNTIME_SCHEMA, *sorted(HOST_SCHEMAS))


def _check(connection, schema, *, complete):
    snapshot = storage_setup._snapshot(connection, schema)
    if schema in HOST_SCHEMAS:
        storage_setup._require_runtime(connection, schema, snapshot, complete=complete)
    else:
        storage_setup._require_native(snapshot,
            storage_setup._native_versions(connection, schema, snapshot), complete=complete)
    if storage_setup._other_objects(connection, {schema}):
        raise RuntimeError("Unexpected runtime objects; no automatic repair is permitted.")
    return snapshot


def _publication(schema):
    engine = sa.create_engine(sa.URL.create("postgresql+psycopg", username="jd_test",
        password="jd-local-test-only", host="127.0.0.1", port=55436,
        database="caliburn_jd_relational_test"), hide_parameters=True,
        connect_args={"connect_timeout": 5, "options": "-csearch_path=public"})
    try:
        with engine.begin() as transaction:
            MemoryPublicationBase.metadata.create_all(transaction.execution_options(
                schema_translate_map={None: schema}))
    finally:
        engine.dispose()


def main(schema=RUNTIME_SCHEMA):
    if schema not in SCHEMAS:
        raise ValueError("Only fixed isolated test runtime schemas are supported.")
    # Public synthetic-test credentials, not product configuration.
    with Connection.connect(host="127.0.0.1", port=55436,
        dbname="caliburn_jd_relational_test", user="jd_test", password="jd-local-test-only",
        connect_timeout=5, autocommit=True, row_factory=dict_row, prepare_threshold=0) as conn:
        identity = conn.execute("SELECT current_database() AS db, current_user AS usr, "
            "current_setting('server_version_num')::integer AS version").fetchone()
        if identity != {"db": "caliburn_jd_relational_test", "usr": "jd_test", "version": 180006}:
            raise RuntimeError("Unexpected test database identity/version; no runtime setup applied.")
        storage_setup._require_jd(conn, storage_setup._snapshot(conn, "public"), allow_empty=False)
        existing = _check(conn, schema, complete=False)
        if not existing:
            conn.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {} AUTHORIZATION CURRENT_USER").format(
                sql.Identifier(schema)))
        conn.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
        # Saver migrations include CREATE INDEX CONCURRENTLY: native setup must
        # run with autocommit, outside a caller-owned transaction.
        if len(storage_setup._native_versions(conn, schema, existing)) < len(PostgresSaver.MIGRATIONS):
            PostgresSaver(conn).setup()
        if schema in HOST_SCHEMAS:
            if len(storage_setup._store_versions(conn, schema, existing)) < storage_memory_profile.STORE_VERSION_COUNT:
                PostgresStore(conn).setup()
            if not (set(existing) & storage_memory_profile.PUBLICATION_TABLES):
                _publication(schema)
        storage_setup._require_jd(conn, storage_setup._snapshot(conn, "public"), allow_empty=False)
        _check(conn, schema, complete=True)
    total = 8 if schema in HOST_SCHEMAS else 4
    print(f"PostgreSQL 18.6: {schema} contains {total} validated runtime tables; public JD unchanged; no data cleared.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schema", choices=SCHEMAS, default=RUNTIME_SCHEMA)
    main(parser.parse_args().schema)
