"""Schema version readiness and actual DDL/model agreement against PostgreSQL."""

import asyncio
import os
import subprocess
import sys
from uuid import uuid4

import psycopg
import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from caliburn.adapters.database import API_ROOT, Base, DatabaseSchemaError, migration_config
from caliburn.bootstrap import create_app
from caliburn.settings import DatabaseSettings, Settings

pytestmark = pytest.mark.postgres


def test_jd_upgrade_initializes_prior_target_files_only_once(
    empty_database_settings: DatabaseSettings,
) -> None:
    settings = empty_database_settings
    file_ids = [uuid4(), uuid4()]
    engine = create_engine(
        settings.sqlalchemy_url, connect_args={"options": f"-c search_path={settings.schema}"}
    )
    try:
        with engine.begin() as connection:
            config = migration_config()
            config.attributes.update(connection=connection, schema=settings.schema)
            command.upgrade(config, "0004_job_file_renames")
            for file_id in file_ids:
                connection.execute(
                    text(
                        "INSERT INTO job_files (job_file_id, creation_command_id, "
                        "initial_display_name, display_name, employee_name) "
                        "VALUES (:file_id, :command_id, '合成升級', '合成升級', '合成員工')"
                    ),
                    {"file_id": file_id, "command_id": uuid4()},
                )
            command.upgrade(config, "head")
            original = connection.execute(
                text(
                    "SELECT job_file_id, initial_revision_id, current_revision_id "
                    "FROM job_descriptions ORDER BY job_file_id"
                )
            ).all()
            assert {row.job_file_id for row in original} == set(file_ids)
            assert len({row.initial_revision_id for row in original}) == 2
            assert all(row.initial_revision_id == row.current_revision_id for row in original)
            assert (
                connection.execute(
                    text(
                        "SELECT count(*) FROM jd_revisions WHERE parent_revision_id IS NULL "
                        "AND job_title IS NULL AND organization_unit IS NULL "
                        "AND reports_to IS NULL AND purpose IS NULL"
                    )
                ).scalar_one()
                == 2
            )
            command.upgrade(config, "head")
            assert (
                connection.execute(
                    text(
                        "SELECT job_file_id, initial_revision_id, current_revision_id "
                        "FROM job_descriptions ORDER BY job_file_id"
                    )
                ).all()
                == original
            )
            assert connection.execute(text("SELECT count(*) FROM jd_revisions")).scalar_one() == 2
            assert connection.execute(text("SELECT count(*) FROM jd_operations")).scalar_one() == 0
    finally:
        engine.dispose()


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
            base_url="http://127.0.0.1:8100",
            headers={"Origin": "http://127.0.0.1:8100"},
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
            base_url="http://127.0.0.1:8100",
            headers={"Origin": "http://127.0.0.1:8100"},
            backend_options={"loop_factory": asyncio.SelectorEventLoop},
        ),
    ):
        pytest.fail("Explicit migration is required")
    with psycopg.connect(empty_database_settings.url) as connection:
        assert connection.execute(
            "SELECT count(*) FROM information_schema.tables WHERE table_schema = %s",
            (empty_database_settings.schema,),
        ).fetchone() == (0,)
