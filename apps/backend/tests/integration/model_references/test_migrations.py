"""直接核對已採四欄 schema 的 DDL 契約；不用全域 metadata 接線假設。"""

from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import Engine, inspect, text
from sqlalchemy.exc import IntegrityError

from caliburn.modules.model_references import ReferenceTarget
from caliburn.modules.model_references.persistence import SqlAlchemyModelReferences
from caliburn.shared.infrastructure.persistence.database import create_session_factory
from caliburn.shared.infrastructure.persistence.orm_base import OrmBase


def test_migration_roundtrip_has_exact_mapping_schema(pg_engine: Engine) -> None:
    backend = Path(__file__).resolve().parents[3]
    config = Config(str(backend / "alembic.ini"))
    with pg_engine.begin() as connection:
        config.attributes["connection"] = connection
        command.downgrade(config, "0007_memory")
        assert "model_references" not in inspect(connection).get_table_names()
        command.upgrade(config, "0008_model_references")
        schema = inspect(connection)
        columns = {
            column["name"]: column for column in schema.get_columns("model_references")
        }
        assert set(columns) == {
            "reference_number",
            "workspace_id",
            "resource_kind",
            "resource_id",
        }
        assert all(not column["nullable"] for column in columns.values())
        assert columns["reference_number"]["identity"]["always"] is True
        assert columns["reference_number"]["identity"]["cycle"] is False
        assert schema.get_pk_constraint("model_references")["constrained_columns"] == [
            "reference_number"
        ]
        (unique,) = schema.get_unique_constraints("model_references")
        assert unique["column_names"] == [
            "workspace_id",
            "resource_kind",
            "resource_id",
        ]
        (foreign_key,) = schema.get_foreign_keys("model_references")
        assert foreign_key["referred_table"] == "workspaces"
        assert foreign_key["referred_columns"] == ["id"]
        assert foreign_key["options"]["ondelete"] == "CASCADE"
        migration = MigrationContext.configure(
            connection,
            opts={
                "include_object": lambda obj, name, kind, reflected, compare_to: (
                    kind != "table" or name == "model_references"
                )
            },
        )
        assert compare_metadata(migration, OrmBase.metadata) == []


@pytest.mark.parametrize(
    "violation", ["duplicate", "unknown_kind", "unknown_workspace"]
)
def test_database_constraints_reject_invalid_mapping(
    pg_engine: Engine, jd_workspace_id: UUID, violation: str
) -> None:
    references = SqlAlchemyModelReferences(create_session_factory(pg_engine))
    target = ReferenceTarget("task", uuid4())
    saved = references.get_or_create_refs(jd_workspace_id, [target])

    with pytest.raises(IntegrityError):
        with pg_engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO model_references "
                    "(workspace_id, resource_kind, resource_id) "
                    "VALUES (:workspace, :kind, :resource)"
                ),
                {
                    "workspace": uuid4()
                    if violation == "unknown_workspace"
                    else jd_workspace_id,
                    "kind": "plan" if violation == "unknown_kind" else "task",
                    "resource": target.resource_id,
                },
            )
    assert references.get_or_create_refs(jd_workspace_id, [target]) == saved
