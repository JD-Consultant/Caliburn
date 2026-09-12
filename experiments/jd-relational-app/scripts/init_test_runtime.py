"""Explicit native LangGraph initialization in the fixed synthetic test DB.

The 13 JD tables remain owned by public/Alembic. Only jd_runtime_test receives
the four native PostgresSaver tables. This script never drops or clears data.
"""

from langgraph.checkpoint.postgres import PostgresSaver
from psycopg import Connection, sql
from psycopg.rows import dict_row

from jd_relational.storage.schema import JD_TABLE_NAMES


RUNTIME_SCHEMA = "jd_runtime_test"
NATIVE_TABLES = {"checkpoint_migrations", "checkpoints", "checkpoint_blobs", "checkpoint_writes"}


def _tables(connection, schema):
    return {row["tablename"] for row in connection.execute(
        "SELECT tablename FROM pg_tables WHERE schemaname = %s", (schema,))}


def main():
    # Public synthetic-test credentials, not product configuration.
    with Connection.connect(host="127.0.0.1", port=55436,
        dbname="caliburn_jd_relational_test", user="jd_test", password="jd-local-test-only",
        connect_timeout=5, autocommit=True, row_factory=dict_row, prepare_threshold=0) as conn:
        identity = conn.execute("SELECT current_database() AS db, current_user AS usr, "
            "current_setting('server_version_num')::integer AS version").fetchone()
        if identity != {"db": "caliburn_jd_relational_test", "usr": "jd_test", "version": 180006}:
            raise RuntimeError("Unexpected test database identity/version; no runtime setup applied.")
        if _tables(conn, "public") != JD_TABLE_NAMES | {"alembic_version"}:
            raise RuntimeError("Unexpected public tables; initialize the JD test database separately.")
        revisions = conn.execute("SELECT version_num FROM public.alembic_version").fetchall()
        if revisions != [{"version_num": "20260913_0001"}]:
            raise RuntimeError("Unexpected JD migration; no runtime setup applied.")
        existing = _tables(conn, RUNTIME_SCHEMA)
        if not existing.issubset(NATIVE_TABLES):
            raise RuntimeError("Unexpected runtime tables; no runtime setup applied.")
        conn.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {} AUTHORIZATION CURRENT_USER").format(
            sql.Identifier(RUNTIME_SCHEMA)))
        conn.execute(sql.SQL("SET search_path TO {}, public").format(sql.Identifier(RUNTIME_SCHEMA)))
        # Saver migrations include CREATE INDEX CONCURRENTLY: native setup must
        # run with autocommit, outside a caller-owned transaction.
        saver = PostgresSaver(conn)
        saver.setup()
        if _tables(conn, RUNTIME_SCHEMA) != NATIVE_TABLES:
            raise RuntimeError("Native setup did not produce the expected four runtime tables.")
        versions = [row["v"] for row in conn.execute(
            "SELECT v FROM jd_runtime_test.checkpoint_migrations ORDER BY v")]
        if versions != list(range(len(saver.MIGRATIONS))):
            raise RuntimeError("Unexpected native Saver migration version; no data was cleared.")
        if _tables(conn, "public") != JD_TABLE_NAMES | {"alembic_version"}:
            raise RuntimeError("Public JD table ownership changed unexpectedly.")
    print("PostgreSQL 18.6: jd_runtime_test contains 4 native Saver tables; public JD schema unchanged.")


if __name__ == "__main__":
    main()
