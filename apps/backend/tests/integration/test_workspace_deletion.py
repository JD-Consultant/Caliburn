"""整份 Workspace 刪除的 HTTP、所有權與交易契約。"""

from collections.abc import Iterator
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from psycopg import errors as pg_errors
from psycopg.errors import LockNotAvailable
from sqlalchemy import Engine, event, text
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session
from sqlalchemy.pool import PoolProxiedConnection

from caliburn.host.app import build_app
from caliburn.modules.workspace.application.workspace_service import WorkspaceService
from caliburn.modules.workspace.infrastructure.persistence.unit_of_work import (
    SqlAlchemyWorkspaceUnitOfWork,
)
from caliburn.modules.workspace.presentation.api.router import build_workspace_router
from caliburn.shared.infrastructure.persistence.database import create_session_factory
from caliburn.shared.presentation.api.app import build_http_app
from tests.integration.content_support import CONTENT_TABLES, content_rows
from tests.reference_configuration import HOST_REFERENCE_CONFIGURATION

ALL_TABLES = ("workspaces", *CONTENT_TABLES)


@pytest.fixture
def client(pg_engine: Engine) -> Iterator[TestClient]:
    app = build_app(
        reference_configuration=HOST_REFERENCE_CONFIGURATION,
        database_url=pg_engine.url.render_as_string(hide_password=False),
    )
    with TestClient(app) as api:
        yield api


def create_populated_workspace(client: TestClient) -> dict[str, Any]:
    """以公開 API 建立所有內容種類、引用及恢復自引用。"""
    workspace = client.post("/workspaces", json={"interviewee_name": "合成受訪者"})
    assert workspace.status_code == 201
    workspace_id = workspace.json()["workspace_id"]
    created = client.get(f"/workspaces/{workspace_id}/job-description")
    assert created.status_code == 200
    current = created.json()
    url = f"/workspaces/{workspace_id}/job-descriptions/{current['job_description_id']}"

    def add(suffix: str, body: dict[str, Any]) -> dict[str, Any]:
        response = client.post(
            url + suffix, json={**body, "expected_version": current["version"]}
        )
        assert response.status_code in (200, 201), response.text
        result: dict[str, Any] = response.json()
        return result

    current = add("/duties", {"name": "訪談分析"})
    current = add(
        "/tasks",
        {
            "name": "訪談",
            "duty_id": current["duties"][0]["id"],
            "outcomes": ["紀錄"],
            "requirements": ["完整性"],
            "knowledge": [{"kind": "new", "name": "研究方法"}],
            "skills": [{"kind": "new", "name": "分析"}],
        },
    )
    current = add("/collaborations", {"collaborator_name": "主管"})
    current = add("/conditions", {"kind": "qualification", "text": "相關經驗"})
    current = add(":restore", {"target_version": current["version"]})
    return current


def test_delete_clears_all_owned_rows_and_history_but_preserves_other_workspace(
    client: TestClient, pg_engine: Engine
) -> None:
    """級聯清除完整 JD 與歷史；另一份所有列不變，刪除身分無法恢復。"""
    survivor = create_populated_workspace(client)
    before = content_rows(pg_engine, tables=ALL_TABLES)
    assert all(before.values()), "前置必須涵蓋每張所有權資料表"
    target = create_populated_workspace(client)
    workspace_url = f"/workspaces/{target['workspace_id']}"
    jd_url = f"{workspace_url}/job-descriptions/{target['job_description_id']}"

    for _ in range(2):
        deleted = client.delete(workspace_url)
        assert deleted.status_code == 204, deleted.text
        assert deleted.content == b""
    assert content_rows(pg_engine, tables=ALL_TABLES) == before
    assert client.get(workspace_url).status_code == 404
    assert client.get(workspace_url + "/job-description").status_code == 404
    for suffix in ("", "/history", "/history/1"):
        assert client.get(jd_url + suffix).status_code == 404
    assert (
        client.get(
            jd_url + "/history:compare",
            params={"before_version": 1, "after_version": 2},
        ).status_code
        == 404
    )
    assert (
        client.post(
            jd_url + ":restore",
            json={"expected_version": target["version"], "target_version": 1},
        ).status_code
        == 404
    )
    assert (
        client.get(f"/workspaces/{survivor['workspace_id']}/job-description").json()
        == survivor
    )


@pytest.mark.parametrize("stage", ["before_commit", "after_commit"])
def test_failed_delete_does_not_claim_success_or_retry(
    client: TestClient, pg_engine: Engine, stage: str
) -> None:
    """提交前故障完整回滾；提交後失去確認仍回安全錯誤且不重送。"""
    current = create_populated_workspace(client)
    before = content_rows(pg_engine, tables=ALL_TABLES)
    calls = 0

    def fail(session: Session) -> None:
        nonlocal calls
        calls += 1
        if stage == "after_commit":
            raise OperationalError(None, None, LockNotAvailable("synthetic timeout"))
        raise RuntimeError("synthetic failure: private information")

    event.listen(Session, stage, fail)
    try:
        response = client.delete(f"/workspaces/{current['workspace_id']}")
    finally:
        event.remove(Session, stage, fail)
    assert response.status_code == 500
    assert response.json() == {"detail": {"code": "internal_error"}}
    assert calls == 1
    after = content_rows(pg_engine, tables=ALL_TABLES)
    assert after == (
        before if stage == "before_commit" else dict.fromkeys(ALL_TABLES, ())
    )


@pytest.mark.parametrize("committed,sqlstate", [(False, "08007"), (True, "40003")])
def test_unconfirmed_delete_commit_returns_safe_error_for_both_database_outcomes(
    client: TestClient,
    pg_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
    committed: bool,
    sqlstate: str,
) -> None:
    """在提交邊界注入失去確認；已刪及未刪都回 500，不冒充真實斷網。"""
    current = create_populated_workspace(client)
    before = content_rows(pg_engine, tables=ALL_TABLES)
    sessions = create_session_factory(pg_engine)
    service = WorkspaceService(lambda: SqlAlchemyWorkspaceUnitOfWork(sessions))
    app = build_http_app(build_workspace_router(service))
    original_commit = pg_engine.dialect.do_commit
    calls = 0

    def lose_reply(connection: PoolProxiedConnection) -> None:
        nonlocal calls
        calls += 1
        if committed:
            original_commit(connection)
        raise pg_errors.lookup(sqlstate)("合成提交回覆未知")

    with TestClient(app) as deleting, monkeypatch.context() as injection:
        injection.setattr(pg_engine.dialect, "do_commit", lose_reply)
        response = deleting.delete(f"/workspaces/{current['workspace_id']}")
    assert response.status_code == 500
    assert response.json() == {"detail": {"code": "internal_error"}}
    assert calls == 1
    assert content_rows(pg_engine, tables=ALL_TABLES) == (
        dict.fromkeys(ALL_TABLES, ()) if committed else before
    )


def test_delete_lock_timeout_rolls_back_all_rows_and_returns_retryable_conflict(
    client: TestClient, pg_engine: Engine
) -> None:
    """JD 正在編修時刪除有限等待，逾時完整回滾；解鎖後明確重試成功。"""
    current = create_populated_workspace(client)
    before = content_rows(pg_engine, tables=ALL_TABLES)
    sessions = create_session_factory(pg_engine)
    service = WorkspaceService(
        lambda: SqlAlchemyWorkspaceUnitOfWork(sessions, lock_timeout_ms=100)
    )
    app = build_http_app(build_workspace_router(service))
    url = f"/workspaces/{current['workspace_id']}"
    with pg_engine.connect() as editing, TestClient(app) as deleting:
        editing.execute(
            text("SELECT id FROM job_descriptions WHERE id=:id FOR UPDATE"),
            {"id": UUID(current["job_description_id"])},
        )
        response = deleting.delete(url)
        assert response.status_code == 409, response.text
        assert response.json() == {
            "detail": {
                "code": "workspace_concurrency_conflict",
                "reason": "lock_timeout",
            }
        }
        assert content_rows(pg_engine, tables=ALL_TABLES) == before
        editing.rollback()
        # 解鎖不會觸發背景刪除；必須有另一個明確請求。
        assert client.get(url).status_code == 200
        assert deleting.delete(url).status_code == 204
    assert not any(content_rows(pg_engine, tables=ALL_TABLES).values())


def test_ownership_migration_preserves_existing_data_and_enables_complete_delete(
    client: TestClient, pg_engine: Engine
) -> None:
    """完整內容回到舊約束後，升級保留資料並能清除；metadata 與實庫一致。"""
    # 現行 Host 建立需要完整 schema；本例只回退待驗的資料庫約束，
    # 不要求現行 App 在尚無 Interview 表的歷史 schema 上建立資料。
    current = create_populated_workspace(client)
    backend = Path(__file__).resolve().parents[2]
    config = Config(str(backend / "alembic.ini"))
    with pg_engine.begin() as connection:
        config.attributes["connection"] = connection
        command.downgrade(config, "0002_jd_full_snapshots")
    before = content_rows(pg_engine, tables=ALL_TABLES)
    url = f"/workspaces/{current['workspace_id']}"
    assert client.delete(url).status_code == 500
    assert content_rows(pg_engine, tables=ALL_TABLES) == before
    with pg_engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
        command.check(config)
    assert content_rows(pg_engine, tables=ALL_TABLES) == before
    assert client.delete(url).status_code == 204
    assert not any(content_rows(pg_engine, tables=ALL_TABLES).values())


def test_delete_is_independent_of_ownership_trigger_creation_order(
    client: TestClient, pg_engine: Engine
) -> None:
    """K/S 先清除也必須成功，不能依賴 Task 級聯碰巧先於引用檢查。"""
    current = create_populated_workspace(client)
    with pg_engine.begin() as connection:
        connection.execute(
            text("ALTER TABLE job_tasks DROP CONSTRAINT fk_job_tasks_jd")
        )
        connection.execute(
            text(
                "ALTER TABLE job_tasks ADD CONSTRAINT fk_job_tasks_jd "
                "FOREIGN KEY (job_description_id) REFERENCES job_descriptions(id) "
                "ON DELETE CASCADE"
            )
        )
    response = client.delete(f"/workspaces/{current['workspace_id']}")
    assert response.status_code == 204, response.text
    assert not any(content_rows(pg_engine, tables=ALL_TABLES).values())


@pytest.mark.parametrize("table", ["knowledge", "skills"])
def test_deferred_definition_reference_still_rejects_dangling_links_at_commit(
    client: TestClient, pg_engine: Engine, table: str
) -> None:
    """延後只改變檢查時點，單獨刪除被引用 K/S 仍不得提交。"""
    create_populated_workspace(client)
    before = content_rows(pg_engine, tables=ALL_TABLES)
    with pg_engine.connect() as connection:
        connection.execute(text(f"DELETE FROM {table}"))
        with pytest.raises(IntegrityError):
            connection.commit()
        connection.rollback()
    assert content_rows(pg_engine, tables=ALL_TABLES) == before
