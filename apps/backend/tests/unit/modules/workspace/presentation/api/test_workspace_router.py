"""HTTP 契約測試；記憶體替身不代表真 PostgreSQL 已驗證。"""

from collections.abc import Iterator
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from caliburn.modules.workspace.application.workspace_service import WorkspaceService
from caliburn.modules.workspace.domain.interviewee_name import (
    IntervieweeName,
)
from caliburn.modules.workspace.domain.workspace import Workspace
from caliburn.modules.workspace.presentation.api.router import build_workspace_router
from caliburn.modules.workspace.presentation.api.schemas import (
    PUBLIC_VALIDATION_FIELDS,
)
from caliburn.shared.presentation.api.app import build_http_app

from ...application.fakes import (
    FakeUnitOfWork,
    FakeUnitOfWorkFactory,
)


@pytest.fixture
def api() -> Iterator[tuple[TestClient, FakeUnitOfWorkFactory]]:
    """以真服務與記憶體交易替身組裝 HTTP 邊界。"""
    factory = FakeUnitOfWorkFactory()
    app = build_http_app(
        build_workspace_router(WorkspaceService(factory)),
        public_validation_fields=PUBLIC_VALIDATION_FIELDS,
    )
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client, factory


def test_create_returns_location_and_preserves_name(
    api: tuple[TestClient, FakeUnitOfWorkFactory],
) -> None:
    """建立應回 201、可讀 Location、UUIDv7 與原樣姓名。"""
    client, _ = api

    created = client.post("/workspaces", json={"interviewee_name": "  王小明\t"})

    assert created.status_code == 201
    payload = created.json()
    assert set(payload) == {"workspace_id", "interviewee_name"}
    assert UUID(payload["workspace_id"]).version == 7
    assert payload["interviewee_name"] == "  王小明\t"
    found = client.get(created.headers["Location"])
    assert found.status_code == 200
    assert found.json() == payload


def test_rename_delete_and_other_workspace_isolation(
    api: tuple[TestClient, FakeUnitOfWorkFactory],
) -> None:
    """改名保留身分，刪除可重複且不影響另一份 Workspace。"""
    client, _ = api
    first = client.post("/workspaces", json={"interviewee_name": "原名"})
    other = client.post("/workspaces", json={"interviewee_name": "另一份"})
    assert first.status_code == other.status_code == 201
    location = first.headers["Location"]

    renamed = client.patch(location, json={"interviewee_name": "  新名  "})

    assert renamed.status_code == 200
    assert renamed.json() == {
        "workspace_id": first.json()["workspace_id"],
        "interviewee_name": "  新名  ",
    }
    assert client.get(location).json() == renamed.json()
    for _ in range(2):
        deleted = client.delete(location)
        assert deleted.status_code == 204
        assert deleted.content == b""
    assert client.get(location).status_code == 404
    assert client.get(other.headers["Location"]).json() == other.json()


@pytest.mark.parametrize("method", ["GET", "PATCH"])
def test_missing_workspace_returns_not_found(
    api: tuple[TestClient, FakeUnitOfWorkFactory], method: str
) -> None:
    """不存在與儲存故障須分別回 404 與伺服器錯誤。"""
    client, _ = api

    response = client.request(
        method,
        "/workspaces/00000000-0000-0000-0000-000000000001",
        json={"interviewee_name": "有效姓名"} if method == "PATCH" else None,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == {"code": "workspace_not_found"}


def test_list_defaults_to_twenty_items(
    api: tuple[TestClient, FakeUnitOfWorkFactory],
) -> None:
    """省略 limit 仍有界，空資料則回空清單與空游標。"""
    client, factory = api
    empty = client.get("/workspaces")
    assert empty.status_code == 200
    assert empty.json() == {"items": [], "next_cursor": None}
    for number in range(1, 22):
        workspace = Workspace(
            id=UUID(int=number),
            interviewee_name=IntervieweeName(value="有效姓名"),
        )
        factory.saved[workspace.id] = workspace

    response = client.get("/workspaces")

    assert response.status_code == 200
    assert len(response.json()["items"]) == 20
    assert response.json()["items"][0] == {
        "workspace_id": "00000000-0000-0000-0000-000000000015",
        "interviewee_name": "有效姓名",
    }
    assert response.json()["next_cursor"] == "00000000-0000-0000-0000-000000000002"


@pytest.mark.parametrize("method", ["POST", "PATCH"])
@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"interviewee_name": ""},
        {"interviewee_name": "\t\n\u3000\u001c"},
        {"interviewee_name": 123},
        {"interviewee_name": None},
        {"interviewee_name": "有效姓名", "unknown": "員工原文"},
        ["員工原文"],
    ],
)
def test_invalid_body_is_rejected_before_opening_transaction(
    api: tuple[TestClient, FakeUnitOfWorkFactory], method: str, payload: object
) -> None:
    """形狀、型別與姓名無效時均回 422 且不開交易。"""
    client, factory = api
    path = "/workspaces"
    if method == "PATCH":
        path += "/00000000-0000-0000-0000-000000000001"

    response = client.request(method, path, json=payload)

    assert response.status_code == 422
    assert factory.units == []


@pytest.mark.parametrize("limit", ["0", "101", "1.5", "wrong"])
def test_invalid_page_limit_is_rejected(
    api: tuple[TestClient, FakeUnitOfWorkFactory], limit: str
) -> None:
    """分頁筆數只允許 1 至 100，無效值不會開交易。"""
    client, factory = api

    response = client.get("/workspaces", params={"limit": limit})

    assert response.status_code == 422
    assert factory.units == []


@pytest.mark.parametrize(
    "identity",
    [
        "invalid",
        "00000000000000000000000000000001",
        "urn:uuid:00000000-0000-0000-0000-000000000001",
    ],
)
def test_uuid_path_and_cursor_require_hyphenated_format(
    api: tuple[TestClient, FakeUnitOfWorkFactory], identity: str
) -> None:
    """HTTP UUID 只接受契約的連字號格式，不接受 compact 或 URN。"""
    client, factory = api

    assert client.get(f"/workspaces/{identity}").status_code == 422
    assert client.get("/workspaces", params={"after": identity}).status_code == 422
    assert factory.units == []


def test_commit_failure_is_not_success_or_retried() -> None:
    """提交異常不能回成功、洩露原錯誤或自動重送。"""
    unit = FakeUnitOfWork(
        {}, commit_error=RuntimeError("postgresql://secret@db SELECT employee_payload")
    )
    app = build_http_app(build_workspace_router(WorkspaceService(lambda: unit)))

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post("/workspaces", json={"interviewee_name": "員工原文"})

    assert response.status_code == 500
    assert unit.commit_attempts == 1
    assert "secret" not in response.text
    assert "SELECT" not in response.text
    assert "員工原文" not in response.text


def test_persisted_domain_validation_error_is_not_client_error() -> None:
    """既有資料還原失敗不能被 HTTP 當成使用者輸入錯誤。"""
    with pytest.raises(ValueError) as error:
        IntervieweeName(value="\t")
    unit = FakeUnitOfWork({})
    unit.workspaces.read_error = error.value
    app = build_http_app(build_workspace_router(WorkspaceService(lambda: unit)))

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.patch(
            "/workspaces/00000000-0000-0000-0000-000000000001",
            json={"interviewee_name": "有效姓名"},
        )

    assert response.status_code == 500


@pytest.mark.parametrize("method", ["POST", "PATCH"])
@pytest.mark.parametrize(
    "json_body",
    [
        b'{"interviewee_name":"employee_secret_payload\\u0000"}',
        b'{"interviewee_name":"employee_secret_payload\\ud800"}',
        b'{"interviewee_name":"employee_secret_payload\\udfff"}',
    ],
)
def test_unrepresentable_text_is_rejected_before_opening_transaction(
    api: tuple[TestClient, FakeUnitOfWorkFactory], method: str, json_body: bytes
) -> None:
    """NUL 與孤立 surrogate 不符合 UTF-8 Text 儲存格式，須先回 422。"""
    client, factory = api
    path = "/workspaces"
    if method == "PATCH":
        path += "/00000000-0000-0000-0000-000000000001"

    response = client.request(
        method, path, content=json_body, headers={"Content-Type": "application/json"}
    )

    assert response.status_code == 422
    assert factory.units == []
    assert "employee_secret_payload" not in response.text


def test_emoji_name_is_valid_and_preserved(
    api: tuple[TestClient, FakeUnitOfWorkFactory],
) -> None:
    """UTF-8 可表示的 emoji 與姓名空格仍須原樣保存並讀回。"""
    client, _ = api

    created = client.post("/workspaces", json={"interviewee_name": "  工程師 👩🏽‍💻  "})

    assert created.status_code == 201
    assert created.json()["interviewee_name"] == "  工程師 👩🏽‍💻  "
    assert client.get(created.headers["Location"]).json() == created.json()


@pytest.mark.parametrize(
    "payload",
    [
        ["私密員工原文"],
        {"interviewee_name": ["私密員工原文"]},
        {"interviewee_name": "有效姓名", "私密員工原文": True},
    ],
)
def test_validation_error_does_not_echo_employee_payload(
    api: tuple[TestClient, FakeUnitOfWorkFactory], payload: object
) -> None:
    """錯誤欄位名稱與錯誤輸入都可能帶原文，422 不得原樣回顯。"""
    client, _ = api

    response = client.post("/workspaces", json=payload)

    assert response.status_code == 422
    assert "私密員工原文" not in str(response.json())
