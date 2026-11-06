"""有資料的正式 migration 升降版與內容關係約束，獨立於保存用例。"""

from pathlib import Path
from uuid import UUID

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, text
from sqlalchemy.exc import IntegrityError

from caliburn.modules.job_description.application.errors import (
    JobDescriptionConcurrencyError,
)
from caliburn.modules.job_description.infrastructure.persistence.errors import (
    translate_persistence_error,
)
from tests.integration.content_scenarios import D1, T1
from tests.integration.content_support import content_rows, seed_root


@pytest.mark.parametrize("table", ["duties", "job_tasks", "knowledge", "skills"])
def test_name_length_migration_preserves_data_and_updates_the_limit(
    pg_engine: Engine, jd_workspace_id: UUID, table: str
) -> None:
    """舊限制拒絕255；升級保留資料，允許255並拒絕256字元。"""
    seed_root(pg_engine, jd_workspace_id)
    before = content_rows(pg_engine)
    backend = Path(__file__).resolve().parents[2]
    config = Config(str(backend / "alembic.ini"))
    with pg_engine.begin() as connection:
        config.attributes["connection"] = connection
        command.downgrade(config, "0003_workspace_deletion")
    statement = text(
        f"UPDATE {table} SET name=:name WHERE id=(SELECT id FROM {table} LIMIT 1)"
    )
    name = "😀" * 255
    with pytest.raises(IntegrityError), pg_engine.begin() as connection:
        connection.execute(statement, {"name": name})
    with pg_engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    assert content_rows(pg_engine) == before
    with pg_engine.begin() as connection:
        connection.execute(statement, {"name": name})
    after = content_rows(pg_engine)
    with pytest.raises(IntegrityError), pg_engine.begin() as connection:
        connection.execute(statement, {"name": name + "界"})
    assert content_rows(pg_engine) == after


@pytest.mark.parametrize(
    "table, predicate",
    [
        ("duties", "TRUE"),
        ("knowledge", "TRUE"),
        ("skills", "TRUE"),
        ("job_tasks", "duty_id=:duty_id"),
        ("task_outcomes", "task_id=:task_id"),
        ("task_requirements", "task_id=:task_id"),
        ("collaboration_entries", "TRUE"),
        ("job_conditions", "TRUE"),
    ],
)
def test_position_constraints_reject_duplicates_at_statement_end(
    pg_engine: Engine, jd_workspace_id: UUID, table: str, predicate: str
) -> None:
    seed_root(pg_engine, jd_workspace_id)
    with pg_engine.begin() as connection, pytest.raises(IntegrityError) as caught:
        connection.execute(
            text(f"UPDATE {table} SET position=0 WHERE {predicate}"),
            {"duty_id": D1, "task_id": T1},
        )
    translated = translate_persistence_error(
        caught.value, commit_status="not_committed"
    )
    assert isinstance(translated, JobDescriptionConcurrencyError)
    assert translated.reason == "order"


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE job_tasks SET duty_id='00000000-0000-0000-0000-000000000999'",
        "UPDATE task_knowledge SET knowledge_id='00000000-0000-0000-0000-000000000999'",
        "UPDATE task_skills SET skill_id='00000000-0000-0000-0000-000000000999'",
        "UPDATE task_outcomes SET task_id='00000000-0000-0000-0000-000000000999'",
        "UPDATE task_requirements SET task_id='00000000-0000-0000-0000-000000000999'",
        "UPDATE collaboration_entries "
        "SET job_description_id='00000000-0000-0000-0000-000000000999'",
        "UPDATE job_conditions SET kind='unknown'",
    ],
)
def test_content_identity_and_kind_constraints_reject_invalid_rows(
    pg_engine: Engine, jd_workspace_id: UUID, statement: str
) -> None:
    seed_root(pg_engine, jd_workspace_id)
    before = content_rows(pg_engine)
    with pg_engine.begin() as connection, pytest.raises(IntegrityError):
        connection.execute(text(statement))
        connection.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))
    assert content_rows(pg_engine) == before


@pytest.mark.parametrize("table", ["duties", "job_tasks", "knowledge", "skills"])
def test_database_names_preserve_raw_uniqueness_without_casefold_columns(
    pg_engine: Engine, jd_workspace_id: UUID, table: str
) -> None:
    seed_root(pg_engine, jd_workspace_id)
    with pg_engine.begin() as connection:
        identities = tuple(
            connection.scalars(text(f"SELECT id FROM {table} ORDER BY id"))
        )
        for identity, name in zip(identities, ("Straße", " STRASSE "), strict=True):
            connection.execute(
                text(f"UPDATE {table} SET name=:name WHERE id=:id"),
                {"id": identity, "name": name},
            )
        connection.execute(text(f"SET CONSTRAINTS uq_{table}_name IMMEDIATE"))
    with pg_engine.connect() as connection:
        assert set(connection.scalars(text(f"SELECT name FROM {table}"))) == {
            "Straße",
            " STRASSE ",
        }
    before = content_rows(pg_engine)
    with pg_engine.begin() as connection, pytest.raises(IntegrityError):
        connection.execute(text(f"UPDATE {table} SET name='same raw value'"))
        connection.execute(text(f"SET CONSTRAINTS uq_{table}_name IMMEDIATE"))
    assert content_rows(pg_engine) == before
