"""唯讀 Plan API 透過正式組裝與真 PostgreSQL 顯示目前內容。"""

import json
from collections.abc import Iterator
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from caliburn.host.app import build_app
from caliburn.modules.plan.application.plans import (
    initialize_plan,
    patch_plan,
    restore_plan,
)
from caliburn.modules.plan.infrastructure.persistence.unit_of_work import (
    SqlAlchemyPlanUnitOfWork,
)
from caliburn.shared.infrastructure.persistence.database import create_session_factory
from tests.reference_configuration import HOST_REFERENCE_CONFIGURATION


@pytest.fixture
def plan_client(pg_engine: Engine) -> Iterator[TestClient]:
    app = build_app(
        reference_configuration=HOST_REFERENCE_CONFIGURATION,
        database_url=pg_engine.url.render_as_string(hide_password=False),
    )
    with TestClient(app) as client:
        yield client


def create_workspace(client: TestClient) -> UUID:
    response = client.post("/workspaces", json={"interviewee_name": "Plan 合成測試"})
    assert response.status_code == 201, response.text
    return UUID(response.json()["workspace_id"])


def test_current_read_tracks_saved_edits_and_restore_without_agent(
    plan_client: TestClient, pg_engine: Engine
) -> None:
    workspace_id = create_workspace(plan_client)
    url = f"/workspaces/{workspace_id}/plan"
    response = plan_client.get(url)
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {
        "workspace_id": str(workspace_id),
        "version": None,
        "body": None,
    }

    sessions = create_session_factory(pg_engine)

    def uow_factory() -> SqlAlchemyPlanUnitOfWork:
        return SqlAlchemyPlanUnitOfWork(sessions)

    initialize_plan(workspace_id=workspace_id, uow_factory=uow_factory)
    assert plan_client.get(url).json()["version"] == 1
    edited = patch_plan(
        workspace_id=workspace_id,
        expected_version=1,
        diff="@@\n+ 先確認目標 🙂\n*** End of File",
        uow_factory=uow_factory,
    )
    assert edited.plan.body == " 先確認目標 🙂"
    assert plan_client.get(url).json() == {
        "workspace_id": str(workspace_id),
        "version": 2,
        "body": " 先確認目標 🙂",
    }
    patch_plan(
        workspace_id=workspace_id,
        expected_version=2,
        diff="@@\n- 先確認目標 🙂\n",
        uow_factory=uow_factory,
    )
    assert plan_client.get(url).json()["body"] == ""
    restore_plan(
        workspace_id=workspace_id,
        expected_version=3,
        target_version=1,
        uow_factory=uow_factory,
    )
    restored = plan_client.get(url)
    assert restored.json() == {
        "workspace_id": str(workspace_id),
        "version": 4,
        "body": None,
    }
    assert restored.headers["cache-control"] == "no-store"


def test_read_distinguishes_missing_workspace_and_invalid_id(
    plan_client: TestClient,
) -> None:
    response = plan_client.get(f"/workspaces/{uuid4()}/plan")
    assert response.status_code == 404
    assert response.json() == {"detail": {"code": "workspace_not_found"}}
    invalid = plan_client.get("/workspaces/private-invalid-id/plan")
    assert invalid.status_code == 422
    assert "private-invalid-id" not in invalid.text


@pytest.mark.parametrize(
    "failure, error_type",
    [("missing_snapshot", "PlanDataError"), ("query_failure", "PlanQueryError")],
)
def test_failed_read_never_returns_empty_success(
    plan_client: TestClient,
    pg_engine: Engine,
    failure: str,
    error_type: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    workspace_id = create_workspace(plan_client)
    sessions = create_session_factory(pg_engine)
    initialize_plan(
        workspace_id=workspace_id,
        uow_factory=lambda: SqlAlchemyPlanUnitOfWork(sessions),
    )
    patch_plan(
        workspace_id=workspace_id,
        expected_version=1,
        diff="@@\n+private-plan-body\n*** End of File",
        uow_factory=lambda: SqlAlchemyPlanUnitOfWork(sessions),
    )
    with pg_engine.begin() as connection:
        if failure == "missing_snapshot":
            connection.execute(text("DELETE FROM plan_versions"))
        else:
            # 只改本例隨機 schema，讓正式查詢遇到真實 SQL 錯誤。
            connection.execute(text("ALTER TABLE plans RENAME TO unavailable_plans"))
    response = plan_client.get(f"/workspaces/{workspace_id}/plan")
    assert response.status_code == 503, response.text
    assert response.json() == {"detail": {"code": "plan_unavailable"}}
    request_id = response.headers["X-Request-ID"]
    assert request_id
    failures = [
        json.loads(record.getMessage())
        for record in caplog.records
        if record.name == "caliburn.shared.presentation.api.diagnostics"
    ]
    assert any(
        entry["request_id"] == request_id
        and entry["status_code"] == 503
        and entry["error_type"] == error_type
        and entry["method"] == "GET"
        and entry["route"] == "/workspaces/{workspace_id}/plan"
        for entry in failures
    )
    for private_value in (
        "private-plan-body",
        "SELECT ",
        "does not exist",
        "unavailable_plans",
    ):
        assert private_value not in caplog.text
