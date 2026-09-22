"""Explicit Memory initialization in the fixed synthetic PostgreSQL test DB.

Four tables in jd_memory_core_test only. Never runs during App open or tests;
does not drop, clear, migrate old data, or change the host's installed profile.
"""
from langgraph.store.postgres import PostgresStore
from psycopg import Connection, sql
from psycopg.rows import dict_row
import sqlalchemy as sa

from caliburn_memory.publication import Base
from jd_relational.storage.schema import JD_TABLE_NAMES


SCHEMA = "jd_memory_core_test"
TABLES = {"store", "store_migrations", *Base.metadata.tables}


def tables(conn, schema):
    return {row["tablename"] for row in conn.execute(
        "SELECT tablename FROM pg_tables WHERE schemaname=%s", (schema,))}


def main():
    with Connection.connect(host="127.0.0.1", port=55436, dbname="caliburn_jd_relational_test",
        user="jd_test", password="jd-local-test-only", connect_timeout=5,
        autocommit=True, row_factory=dict_row, prepare_threshold=0) as conn:
        identity = conn.execute("SELECT current_database() AS db, current_user AS usr, "
            "current_setting('server_version_num')::integer AS version").fetchone()
        if identity != {"db": "caliburn_jd_relational_test", "usr": "jd_test", "version": 180006}:
            raise RuntimeError("Unexpected isolated database; no Memory setup applied.")
        if tables(conn, "public") != JD_TABLE_NAMES | {"alembic_version"}:
            raise RuntimeError("Unexpected JD schema; no Memory setup applied.")
        if not tables(conn, SCHEMA).issubset(TABLES):
            raise RuntimeError("Unexpected test Memory tables; no setup applied.")
        conn.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {} AUTHORIZATION CURRENT_USER").format(
            sql.Identifier(SCHEMA)))
        conn.execute(sql.SQL("SET search_path TO {} , public").format(sql.Identifier(SCHEMA)))
        store = PostgresStore(conn)
        # Official Store setup needs autocommit for concurrent native indexes.
        store.setup()
        engine = sa.create_engine(sa.URL.create("postgresql+psycopg", username="jd_test",
            password="jd-local-test-only", host="127.0.0.1", port=55436,
            database="caliburn_jd_relational_test"), hide_parameters=True,
            connect_args={"options": "-csearch_path=jd_memory_core_test,public", "connect_timeout": 5})
        try:
            Base.metadata.create_all(engine)
        finally:
            engine.dispose()
        if tables(conn, SCHEMA) != TABLES:
            raise RuntimeError("Memory setup did not produce the four expected tables.")
        versions = [row["v"] for row in conn.execute("SELECT v FROM store_migrations ORDER BY v")]
        if versions != list(range(len(store.MIGRATIONS))):
            raise RuntimeError("Unexpected official Store migration state.")
        if tables(conn, "public") != JD_TABLE_NAMES | {"alembic_version"}:
            raise RuntimeError("Public JD table ownership changed unexpectedly.")
    print("PostgreSQL 18.6: jd_memory_core_test has 2 native Store + 2 publication tables; JD unchanged.")


if __name__ == "__main__":
    main()
