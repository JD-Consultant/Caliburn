"""FastAPI 到真實 PostgreSQL 的公開 CRUD 契約。"""

from collections.abc import Iterator
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from psycopg import Connection
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from caliburn.host.app import build_app
from caliburn.modules.workspace.infrastructure.persistence.orm_models import (
    WorkspaceRow,
)
from tests.reference_configuration import HOST_REFERENCE_CONFIGURATION


@pytest.fixture
def api_client(pg_engine: Engine) -> Iterator[TestClient]:
    app = build_app(
        reference_configuration=HOST_REFERENCE_CONFIGURATION,
        database_url=pg_engine.url.render_as_string(hide_password=False),
    )
    with TestClient(app) as client:
        yield client


def test_workspace_crud_survives_independent_requests(
    api_client: TestClient, pg_engine: Engine
) -> None:
    """建立、重新查詢、改名與重複刪除都反映已提交資料。"""
    created = api_client.post("/workspaces", json={"interviewee_name": " 林小明 "})
    assert created.status_code == 201
    resource = created.json()
    identifier = UUID(resource["workspace_id"])
    assert identifier.version == 7
    assert resource["interviewee_name"] == " 林小明 "
    location = created.headers["Location"]
    assert api_client.get(location).json() == resource

    with Session(pg_engine) as observer:
        row = observer.get(WorkspaceRow, identifier)
        assert row is not None and row.interviewee_name == " 林小明 "

    renamed = api_client.patch(location, json={"interviewee_name": "王小華"})
    assert renamed.status_code == 200
    assert renamed.json() == {
        "workspace_id": str(identifier),
        "interviewee_name": "王小華",
    }
    assert api_client.get(location).json() == renamed.json()
    for _ in range(2):
        deleted = api_client.delete(location)
        assert deleted.status_code == 204 and deleted.content == b""
    assert api_client.get(location).status_code == 404
    assert (
        api_client.patch(location, json={"interviewee_name": "不復活"}).status_code
        == 404
    )
    with Session(pg_engine) as observer:
        assert observer.get(WorkspaceRow, identifier) is None


def test_same_name_creates_distinct_workspaces_and_pages_remain_bounded(
    api_client: TestClient,
) -> None:
    """同名建立不去重，分頁游標即使被刪除仍可接續。"""
    identifiers = [
        api_client.post("/workspaces", json={"interviewee_name": "合成人員"}).json()[
            "workspace_id"
        ]
        for _ in range(4)
    ]
    assert len(set(identifiers)) == 4
    first = api_client.get("/workspaces", params={"limit": 2}).json()
    assert [row["workspace_id"] for row in first["items"]] == sorted(
        identifiers, reverse=True
    )[:2]
    cursor = first["next_cursor"]
    assert cursor == first["items"][-1]["workspace_id"]
    assert api_client.delete(f"/workspaces/{cursor}").status_code == 204
    second = api_client.get("/workspaces", params={"limit": 2, "after": cursor}).json()
    assert [row["workspace_id"] for row in second["items"]] == sorted(
        identifiers, reverse=True
    )[2:]
    assert second["next_cursor"] is None


def test_invalid_requests_do_not_write(
    pg_engine: Engine, api_client: TestClient
) -> None:
    """外部無效資料回 422，資料庫不留下部分建立或更新。"""
    for body in [{}, {"interviewee_name": "\u3000\t"}, {"interviewee_name": 123}]:
        assert api_client.post("/workspaces", json=body).status_code == 422
    invalid_query_params: list[dict[str, str | int]] = [
        {"limit": 0},
        {"limit": 101},
        {"after": "not-a-uuid"},
    ]
    for params in invalid_query_params:
        assert api_client.get("/workspaces", params=params).status_code == 422
    assert api_client.get(f"/workspaces/{uuid4()}").status_code == 404
    with Session(pg_engine) as observer:
        assert observer.scalar(select(func.count()).select_from(WorkspaceRow)) == 0


@pytest.mark.parametrize(
    "stage, saved_count", [("before_commit", 0), ("after_commit", 1)]
)
def test_commit_failure_is_not_success_or_automatic_retry(
    api_client: TestClient,
    pg_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
    stage: str,
    saved_count: int,
) -> None:
    """提交前失敗回滾；提交後失去確認可已保存，兩者都不自動再建。"""
    calls = 0
    commit = Connection.commit

    def fail(connection: Connection[Any]) -> None:
        nonlocal calls
        calls += 1
        if stage == "after_commit":
            commit(connection)
        raise RuntimeError("synthetic commit failure with private details")

    # Host 外層交易才是實際提交；內層 Session.commit 不會提交資料庫。
    with monkeypatch.context() as patch:
        patch.setattr(Connection, "commit", fail)
        response = api_client.post("/workspaces", json={"interviewee_name": "合成人員"})
    assert response.status_code == 500
    assert response.json() == {"detail": {"code": "internal_error"}}
    assert calls == 1
    with Session(pg_engine) as observer:
        assert (
            observer.scalar(select(func.count()).select_from(WorkspaceRow))
            == saved_count
        )
