"""The diagnostic tells a migrated database from one that still needs `pnpm app:migrate`."""

import asyncio

import pytest

from caliburn.adapters.database_settings import DatabaseSettings
from caliburn.settings import Settings
from caliburn.status import describe_settings

pytestmark = pytest.mark.postgres


def describe(settings: DatabaseSettings) -> tuple[list[str], bool]:
    # psycopg async needs the selector loop on Windows, as the server itself runs it.
    return asyncio.run(
        describe_settings(Settings(database=settings)), loop_factory=asyncio.SelectorEventLoop
    )


def test_a_migrated_schema_is_reported_at_head(database_settings: DatabaseSettings) -> None:
    lines, healthy = describe(database_settings)

    assert healthy and "migrations at head" in lines[0]


def test_a_schema_without_migrations_asks_for_the_migration_command(
    empty_database_settings: DatabaseSettings,
) -> None:
    lines, healthy = describe(empty_database_settings)

    assert not healthy
    assert "NOT usable" in lines[0] and "pnpm app:migrate" in lines[0]
