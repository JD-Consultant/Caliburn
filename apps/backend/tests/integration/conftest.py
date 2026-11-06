"""每個測試使用專用 PostgreSQL 內的獨立 schema。"""

import os
from collections.abc import Iterator
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, text

from caliburn.modules.workspace.application.workspace_service import WorkspaceService
from caliburn.modules.workspace.infrastructure.persistence.unit_of_work import (
    SqlAlchemyWorkspaceUnitOfWork,
)
from caliburn.shared.infrastructure.persistence.database import (
    create_database_engine,
    create_session_factory,
)
from tests.database_configuration import validated_test_database_url

BACKEND_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def jd_workspace_id(pg_engine: Engine) -> UUID:
    """透過 Workspace 公開用例準備 JD 測試的已提交前置。"""
    sessions = create_session_factory(pg_engine)
    return (
        WorkspaceService(lambda: SqlAlchemyWorkspaceUnitOfWork(sessions))
        .create(interviewee_name="JD 合成測試")
        .workspace_id
    )


@pytest.fixture(scope="session")
def test_database_engine() -> Iterator[Engine]:
    raw_url = os.environ.get("CALIBURN_REBUILD_TEST_DATABASE_URL")
    if not raw_url:
        pytest.skip("Set CALIBURN_REBUILD_TEST_DATABASE_URL for real PostgreSQL tests")
    url = validated_test_database_url(raw_url)
    engine = create_database_engine(url)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def pg_engine(test_database_engine: Engine) -> Iterator[Engine]:
    # 名稱僅由固定前綴與 UUID hex 構成；不接受外部 SQL identifier。
    schema = f"workspace_test_{uuid4().hex}"
    with test_database_engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    url = test_database_engine.url.update_query_dict(
        {"options": f"-csearch_path={schema}"}
    )
    engine = create_database_engine(url)
    try:
        config = Config(str(BACKEND_ROOT / "alembic.ini"))
        with engine.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
        yield engine
    finally:
        engine.dispose()
        with test_database_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
