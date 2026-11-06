"""公開建立用例透過真 PostgreSQL 保存空 JD。"""

from pathlib import Path
from uuid import UUID, uuid7

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, inspect, text

from caliburn.modules.job_description.application.errors import (
    JobDescriptionAlreadyExistsError,
    JobDescriptionPersistenceError,
    JobDescriptionWorkspaceNotFoundError,
)
from caliburn.modules.job_description.application.job_descriptions import (
    create_job_description,
)
from caliburn.modules.job_description.domain.models.job_description import (
    JobDescription,
)
from caliburn.modules.job_description.infrastructure.persistence.unit_of_work import (
    SqlAlchemyJobDescriptionUnitOfWork,
)
from caliburn.modules.workspace.application.workspace_service import WorkspaceService
from caliburn.modules.workspace.infrastructure.persistence.unit_of_work import (
    SqlAlchemyWorkspaceUnitOfWork,
)
from caliburn.shared.infrastructure.persistence.database import create_session_factory


def test_create_empty_job_description_is_committed(pg_engine: Engine) -> None:
    """成功結果的身分、內容與版本可由獨立交易讀回。"""
    sessions = create_session_factory(pg_engine)
    workspace = WorkspaceService(
        lambda: SqlAlchemyWorkspaceUnitOfWork(sessions)
    ).create(interviewee_name="建立 JD 測試")

    result = create_job_description(
        workspace_id=workspace.workspace_id,
        uow_factory=lambda: SqlAlchemyJobDescriptionUnitOfWork(sessions),
    )

    assert result.job_description_id.version == 7
    assert result.workspace_id == workspace.workspace_id
    assert result.version == 1
    assert result.collaborations == ()
    assert result.conditions == ()
    assert (
        result.job_title,
        result.organization_unit,
        result.reports_to,
        result.purpose,
        result.baseline_competency_level,
    ) == (None, None, None, None, None)
    with pg_engine.connect() as observer:
        row = observer.execute(text("SELECT * FROM job_descriptions")).mappings().one()
    assert dict(row) == {
        "id": result.job_description_id,
        "workspace_id": workspace.workspace_id,
        "job_title": None,
        "organization_unit": None,
        "reports_to": None,
        "purpose": None,
        "baseline_competency_level": None,
        "version": 1,
    }


def test_missing_workspace_is_rejected_without_saving(pg_engine: Engine) -> None:
    """缺 Workspace 的建立被明確拒絕，沒有 JD 或自動建立 Workspace。"""
    with pytest.raises(JobDescriptionWorkspaceNotFoundError) as error:
        create_job_description(
            workspace_id=uuid7(),
            uow_factory=lambda: SqlAlchemyJobDescriptionUnitOfWork(
                create_session_factory(pg_engine)
            ),
        )
    assert error.value.__cause__ is not None
    with pg_engine.connect() as observer:
        assert observer.scalar(text("SELECT count(*) FROM job_descriptions")) == 0
        assert observer.scalar(text("SELECT count(*) FROM workspaces")) == 0


def test_duplicate_creation_preserves_the_existing_root(
    pg_engine: Engine, jd_workspace_id: UUID
) -> None:
    """同 Workspace 再建立明確衝突，原根身分、內容與版本均不變。"""
    sessions = create_session_factory(pg_engine)
    first = create_job_description(
        workspace_id=jd_workspace_id,
        uow_factory=lambda: SqlAlchemyJobDescriptionUnitOfWork(sessions),
    )
    with pytest.raises(JobDescriptionAlreadyExistsError) as error:
        create_job_description(
            workspace_id=jd_workspace_id,
            uow_factory=lambda: SqlAlchemyJobDescriptionUnitOfWork(sessions),
        )
    assert error.value.__cause__ is not None
    with pg_engine.connect() as observer:
        saved = observer.execute(
            text("SELECT id, workspace_id, version, purpose FROM job_descriptions")
        ).one()
    assert tuple(saved) == (first.job_description_id, jd_workspace_id, 1, None)


def test_unrecognized_constraint_is_a_technical_failure(
    pg_engine: Engine, jd_workspace_id: UUID
) -> None:
    """根主鍵碰撞不能假裝成 Workspace 已有 JD，且不覆寫原根。"""
    sessions = create_session_factory(pg_engine)
    other_workspace = WorkspaceService(
        lambda: SqlAlchemyWorkspaceUnitOfWork(sessions)
    ).create(interviewee_name="另一個 Workspace")
    first = create_job_description(
        workspace_id=jd_workspace_id,
        uow_factory=lambda: SqlAlchemyJobDescriptionUnitOfWork(sessions),
    )
    with pytest.raises(JobDescriptionPersistenceError) as error:
        with SqlAlchemyJobDescriptionUnitOfWork(sessions) as uow:
            uow.job_descriptions.add(
                JobDescription(
                    id=first.job_description_id,
                    workspace_id=other_workspace.workspace_id,
                )
            )
            uow.commit()
    assert error.value.commit_status == "not_committed"
    assert error.value.__cause__ is not None
    with pg_engine.connect() as observer:
        assert observer.execute(
            text("SELECT id, workspace_id FROM job_descriptions")
        ).one() == (first.job_description_id, jd_workspace_id)


def test_jd_transaction_uses_read_committed_without_changing_workspace(
    pg_engine: Engine, jd_workspace_id: UUID
) -> None:
    """JD 首個 SQL 已採 READ COMMITTED，且不變更同池其他 Workspace 交易。"""
    sessions = create_session_factory(pg_engine)
    session = sessions()
    with SqlAlchemyJobDescriptionUnitOfWork(lambda: session) as uow:
        assert session.scalar(text("SHOW transaction_isolation")) == "read committed"
        assert session.scalar(text("SHOW lock_timeout")) != "0"
        uow.job_descriptions.add(
            JobDescription(id=uuid7(), workspace_id=jd_workspace_id)
        )
        uow.commit()
    with sessions() as workspace_session:
        assert (
            workspace_session.scalar(text("SHOW transaction_isolation"))
            == "read committed"
        )
        assert workspace_session.scalar(text("SHOW lock_timeout")) == "0"


def test_flushed_root_is_not_committed_by_add_or_normal_exit(
    pg_engine: Engine, jd_workspace_id: UUID
) -> None:
    """add 保留根 ID 並 flush 取得版本，但正常退出未提交的 UoW 仍回滾。"""
    root = JobDescription(id=uuid7(), workspace_id=jd_workspace_id)
    session = create_session_factory(pg_engine)()
    with SqlAlchemyJobDescriptionUnitOfWork(lambda: session) as uow:
        assert uow.job_descriptions.add(root) == 1
        assert session.execute(
            text("SELECT id, version FROM job_descriptions")
        ).one() == (root.id, 1)
        with pg_engine.connect() as observer:
            assert observer.scalar(text("SELECT count(*) FROM job_descriptions")) == 0
    with pg_engine.connect() as observer:
        assert observer.scalar(text("SELECT count(*) FROM job_descriptions")) == 0


def test_jd_migration_recreates_metadata_and_named_constraints(
    pg_engine: Engine,
) -> None:
    """真 migration 可降升版，根欄位、具名約束與 ORM metadata 一致。"""
    backend = Path(__file__).resolve().parents[2]
    config = Config(str(backend / "alembic.ini"))
    with pg_engine.begin() as connection:
        config.attributes["connection"] = connection
        command.downgrade(config, "0001_create_workspaces")
        assert "job_descriptions" not in inspect(connection).get_table_names()
        assert "workspaces" in inspect(connection).get_table_names()
        command.upgrade(config, "head")
        command.check(config)
        schema = inspect(connection)
        assert {
            item["name"] for item in schema.get_unique_constraints("job_descriptions")
        } == {"uq_job_descriptions_workspace_id", "uq_job_descriptions_id_workspace"}
        foreign_keys = schema.get_foreign_keys("job_descriptions")
        assert len(foreign_keys) == 1
        assert foreign_keys[0]["name"] == "fk_job_descriptions_workspace_id"
        assert foreign_keys[0]["referred_table"] == "workspaces"
        assert foreign_keys[0]["options"]["ondelete"] == "CASCADE"
        assert {
            item["name"] for item in schema.get_check_constraints("job_descriptions")
        } == {
            "ck_job_descriptions_version_positive",
            "ck_job_descriptions_baseline_competency_level",
        }
