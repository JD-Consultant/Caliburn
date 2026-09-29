"""Schema version readiness and actual DDL/model agreement against PostgreSQL."""

import asyncio
import os
import subprocess
import sys

import psycopg
import pytest
from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from caliburn.adapters.database import API_ROOT, Base, DatabaseSchemaError
from caliburn.bootstrap import create_app
from caliburn.settings import DatabaseSettings, Settings

pytestmark = pytest.mark.postgres


def test_migrations_match_owned_metadata(
    database_settings: DatabaseSettings, database_connection: psycopg.Connection
) -> None:
    engine = create_engine(
        database_settings.sqlalchemy_url,
        connect_args={"options": f"-c search_path={database_settings.schema}"},
    )
    try:
        with engine.connect() as connection:
            context = MigrationContext.configure(connection)
            assert compare_metadata(context, Base.metadata) == []
    finally:
        engine.dispose()
    # Alembic autogenerate does not compare every CHECK; verify constraint names explicitly.
    names = {
        row[0]
        for row in database_connection.execute(
            "SELECT conname FROM pg_constraint WHERE connamespace = %s::regnamespace",
            (database_settings.schema,),
        )
    }
    for table in Base.metadata.tables.values():
        for constraint in table.constraints:
            assert constraint.name in names


def test_wrong_migration_head_fails_startup_without_automatically_migrating(
    database_settings: DatabaseSettings, database_connection: psycopg.Connection
) -> None:
    database_connection.execute("UPDATE alembic_version SET version_num = 'unknown_head'")
    with (
        pytest.raises(DatabaseSchemaError, match="migrations"),
        TestClient(
            create_app(Settings(database=database_settings)),
            backend_options={"loop_factory": asyncio.SelectorEventLoop},
        ),
    ):
        pytest.fail("Startup must not succeed with mismatched schema")
    assert database_connection.execute("SELECT version_num FROM alembic_version").fetchone() == (
        "unknown_head",
    )


def test_documented_migration_cli_is_repeatable_and_has_no_pending_schema_changes(
    empty_database_settings: DatabaseSettings,
) -> None:
    env = os.environ.copy()
    env["CALIBURN_DATABASE_URL"] = empty_database_settings.url
    env["CALIBURN_DATABASE_SCHEMA"] = empty_database_settings.schema
    for arguments in (("upgrade", "head"), ("upgrade", "head"), ("check",)):
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "-c", str(API_ROOT / "alembic.ini"), *arguments],
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30,
        )
        assert result.returncode == 0, result.stderr + result.stdout


def test_empty_namespace_does_not_start_or_create_tables(
    empty_database_settings: DatabaseSettings,
) -> None:
    with (
        pytest.raises(DatabaseSchemaError),
        TestClient(
            create_app(Settings(database=empty_database_settings)),
            backend_options={"loop_factory": asyncio.SelectorEventLoop},
        ),
    ):
        pytest.fail("Explicit migration is required")
    with psycopg.connect(empty_database_settings.url) as connection:
        assert connection.execute(
            "SELECT count(*) FROM information_schema.tables WHERE table_schema = %s",
            (empty_database_settings.schema,),
        ).fetchone() == (0,)
