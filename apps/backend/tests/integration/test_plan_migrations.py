"""在隔離 schema 驗證 Plan 遷移、資料庫約束與 Workspace 級聯。"""

from functools import partial
from pathlib import Path
from uuid import UUID

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, inspect, text
from sqlalchemy.exc import IntegrityError

from caliburn.modules.plan.application.errors import WorkspaceNotFoundError
from caliburn.modules.plan.application.plans import initialize_plan, patch_plan
from caliburn.modules.plan.infrastructure.persistence.queries import (
    SqlAlchemyPlanQueries,
)
from caliburn.modules.plan.infrastructure.persistence.unit_of_work import (
    SqlAlchemyPlanUnitOfWork,
)
from caliburn.modules.workspace.application.workspace_service import WorkspaceService
from caliburn.modules.workspace.infrastructure.persistence.unit_of_work import (
    SqlAlchemyWorkspaceUnitOfWork,
)
from caliburn.shared.infrastructure.persistence.database import create_session_factory


def test_plan_migration_roundtrip_matches_metadata_and_cascade_contract(
    pg_engine: Engine,
) -> None:
    backend = Path(__file__).resolve().parents[2]
    config = Config(str(backend / "alembic.ini"))
    with pg_engine.begin() as connection:
        config.attributes["connection"] = connection
        command.downgrade(config, "0004_jd_name_length")
        assert not {"plans", "plan_versions"} & set(
            inspect(connection).get_table_names()
        )
        command.upgrade(config, "head")
        command.check(config)
        schema = inspect(connection)
        for table, parent in (("plans", "workspaces"), ("plan_versions", "plans")):
            assert {column["name"] for column in schema.get_columns(table)} == {
                "workspace_id",
                "version",
                "body",
            }
            (foreign_key,) = schema.get_foreign_keys(table)
            assert foreign_key["referred_table"] == parent
            assert foreign_key["options"]["ondelete"] == "CASCADE"
            assert {
                constraint["name"] for constraint in schema.get_check_constraints(table)
            } == {
                f"ck_{table}_version",
                f"ck_{table}_body_length",
            }
        assert schema.get_pk_constraint("plan_versions")["constrained_columns"] == [
            "workspace_id",
            "version",
        ]


@pytest.mark.parametrize("table", ["plans", "plan_versions"])
@pytest.mark.parametrize(
    ("column", "value"),
    [("version", 0), ("version", 9_007_199_254_740_992), ("body", "x" * 16_001)],
)
def test_database_rejects_invalid_stored_values(
    pg_engine: Engine, jd_workspace_id: UUID, table: str, column: str, value: int | str
) -> None:
    initialize_plan(
        workspace_id=jd_workspace_id,
        uow_factory=lambda: SqlAlchemyPlanUnitOfWork(create_session_factory(pg_engine)),
    )
    with pytest.raises(IntegrityError):
        with pg_engine.begin() as connection:
            connection.execute(
                text(f"UPDATE {table} SET {column}=:value WHERE workspace_id=:id"),
                {"value": value, "id": jd_workspace_id},
            )
    assert (
        SqlAlchemyPlanQueries(pg_engine)
        .get_current(workspace_id=jd_workspace_id)
        .version
        == 1
    )


def test_workspace_delete_cascades_only_its_plan_and_saved_versions(
    pg_engine: Engine, jd_workspace_id: UUID
) -> None:
    sessions = create_session_factory(pg_engine)
    workspaces = WorkspaceService(lambda: SqlAlchemyWorkspaceUnitOfWork(sessions))
    other = workspaces.create(interviewee_name="保留 Workspace")
    factory = partial(SqlAlchemyPlanUnitOfWork, sessions)
    initialize_plan(workspace_id=jd_workspace_id, uow_factory=factory)
    patch_plan(
        workspace_id=jd_workspace_id,
        expected_version=1,
        diff="@@\n+刪除的內容\n*** End of File",
        uow_factory=factory,
    )
    remaining = initialize_plan(workspace_id=other.workspace_id, uow_factory=factory)

    workspaces.delete(workspace_id=jd_workspace_id)

    queries = SqlAlchemyPlanQueries(pg_engine)
    with pytest.raises(WorkspaceNotFoundError):
        queries.get_current(workspace_id=jd_workspace_id)
    assert queries.get_current(workspace_id=other.workspace_id) == remaining
    with pg_engine.connect() as connection:
        assert (
            connection.scalar(
                text("SELECT count(*) FROM plan_versions WHERE workspace_id=:id"),
                {"id": jd_workspace_id},
            )
            == 0
        )
