"""Fresh namespaces in an explicitly selected local test database; never reuse app tables."""

import asyncio
import os
from collections.abc import Iterator
from uuid import uuid4

import psycopg
import pytest
from alembic import command
from fastapi.testclient import TestClient
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict
from sqlalchemy import create_engine

from caliburn.adapters.database import migration_config
from caliburn.bootstrap import create_app
from caliburn.settings import DatabaseSettings, Settings


@pytest.fixture
def empty_database_settings() -> Iterator[DatabaseSettings]:
    dsn = os.environ.get("CALIBURN_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("Set CALIBURN_TEST_DATABASE_URL to an isolated local database ending in _test")
    info = conninfo_to_dict(dsn)
    if info.get("host") not in {"127.0.0.1", "localhost", "::1"} or not info.get(
        "dbname", ""
    ).endswith("_test"):
        pytest.fail("Integration tests require an explicit loopback test database")
    schema = "t02_" + uuid4().hex
    settings = DatabaseSettings(url=dsn, schema=schema)
    with psycopg.connect(dsn, autocommit=True) as connection:
        connection.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
        try:
            yield settings
        finally:
            # Only the freshly created test namespace, including its own migration head.
            connection.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))


@pytest.fixture
def database_settings(empty_database_settings: DatabaseSettings) -> DatabaseSettings:
    settings = empty_database_settings
    engine = create_engine(
        settings.sqlalchemy_url, connect_args={"options": f"-c search_path={settings.schema}"}
    )
    try:
        with engine.begin() as migration_connection:
            config = migration_config()
            config.attributes.update(connection=migration_connection, schema=settings.schema)
            command.upgrade(config, "head")
    finally:
        engine.dispose()
    return settings


@pytest.fixture
def client(database_settings: DatabaseSettings) -> Iterator[TestClient]:
    with TestClient(
        create_app(Settings(database=database_settings)),
        backend_options={"loop_factory": asyncio.SelectorEventLoop},
    ) as test_client:
        yield test_client


@pytest.fixture
def database_connection(database_settings: DatabaseSettings) -> Iterator[psycopg.Connection]:
    with psycopg.connect(
        database_settings.url,
        options=f"-c search_path={database_settings.schema}",
        autocommit=True,
    ) as connection:
        yield connection
