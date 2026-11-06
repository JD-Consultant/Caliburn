"""共用 HTTP 邊界的錯誤資料保護。"""

import json

import pytest
from fastapi import APIRouter, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel, ConfigDict

from caliburn.modules.workspace.application.persistence import WorkspaceUnitOfWork
from caliburn.modules.workspace.application.workspace_service import WorkspaceService
from caliburn.modules.workspace.presentation.api.router import build_workspace_router
from caliburn.shared.presentation.api.app import build_http_app
from caliburn.shared.presentation.api.schemas import ErrorResponse


def unavailable_uow() -> WorkspaceUnitOfWork:
    raise RuntimeError("postgresql://secret-password; SELECT private_employee")


class ReportRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    report_ids: list[int]
    report_title: str


@pytest.fixture
def report_router() -> APIRouter:
    """使用另一個模組的實際 HTTP body 驗證欄位政策。"""
    router = APIRouter()

    @router.post("/reports")
    def create_report(body: ReportRequest) -> ReportRequest:
        return body

    return router


def test_validation_fields_are_hidden_without_explicit_policy(
    report_router: APIRouter,
) -> None:
    """預設不公開任何模組欄位，包含其他模組曾使用的欄位名。"""
    with TestClient(build_http_app(report_router)) as client:
        response = client.post(
            "/reports",
            json={
                "report_ids": ["private-input"],
                "report_title": 123,
                "workspace_id": 1,
            },
        )

    assert response.status_code == 422
    assert response.json() == {
        "detail": {
            "code": "invalid_request",
            "errors": [
                {"loc": ["body", "unknown", 0], "code": "int_type"},
                {"loc": ["body", "unknown"], "code": "string_type"},
                {"loc": ["body", "unknown"], "code": "extra_forbidden"},
            ],
        }
    }


def test_router_validation_fields_can_be_explicitly_published(
    report_router: APIRouter,
) -> None:
    """傳入政策才公開該模組欄位，未知名稱與輸入仍受遮蔽。"""
    app = build_http_app(
        report_router, public_validation_fields=frozenset({"report_ids"})
    )
    with TestClient(app) as client:
        response = client.post(
            "/reports",
            json={
                "report_ids": ["private-input"],
                "report_title": "有效標題",
                "private-field": "private-input",
            },
        )

    assert response.status_code == 422
    assert response.json() == {
        "detail": {
            "code": "invalid_request",
            "errors": [
                {"loc": ["body", "report_ids", 0], "code": "int_type"},
                {"loc": ["body", "unknown"], "code": "extra_forbidden"},
            ],
        }
    }


def test_validation_field_policies_are_isolated_between_apps(
    report_router: APIRouter,
) -> None:
    """同時建立不同 app 時，公開欄位不會相互覆寫或合併。"""
    ids_app = build_http_app(
        report_router, public_validation_fields=frozenset({"report_ids"})
    )
    title_app = build_http_app(
        report_router, public_validation_fields=frozenset({"report_title"})
    )
    with TestClient(ids_app) as ids_client, TestClient(title_app) as title_client:
        for client, expected_fields in [
            (ids_client, ["report_ids", "unknown"]),
            (title_client, ["unknown", "report_title"]),
            (ids_client, ["report_ids", "unknown"]),
        ]:
            response = client.post(
                "/reports", json={"report_ids": ["private-input"], "report_title": 123}
            )
            assert response.status_code == 422
            assert [
                error["loc"][1] for error in response.json()["detail"]["errors"]
            ] == expected_fields


def test_app_title_is_supplied_by_composition(report_router: APIRouter) -> None:
    """共用 HTTP 可用自己的 OpenAPI 標題組裝另一個模組。"""
    with TestClient(build_http_app(report_router, title="Report API")) as client:
        response = client.get("/openapi.json")

    assert response.status_code == 200
    assert response.json()["info"]["title"] == "Report API"


@pytest.mark.parametrize(
    "body",
    [
        {"interviewee_name": {"private-employee": "secret-value"}},
        {"interviewee_name": "合成人員", "secret-value": "private-employee"},
        {"interviewee_name": "\t\n"},
        ["secret-value"],
        None,
    ],
)
def test_validation_response_never_echoes_input(body: object) -> None:
    """輸入錯誤只回穩定代碼與安全位置，不回員工輸入或例外內容。"""
    with TestClient(
        build_http_app(build_workspace_router(WorkspaceService(unavailable_uow)))
    ) as client:
        response = client.post("/workspaces", json=body)
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_request"
    assert (
        ErrorResponse.model_validate(response.json()).detail.code == "invalid_request"
    )
    assert "secret-value" not in response.text
    assert "private-employee" not in response.text
    for error in response.json()["detail"]["errors"]:
        assert set(error) == {"loc", "code"}


def test_malformed_json_returns_safe_validation_error() -> None:
    """JSON 解析錯誤不回顯無效 body。"""
    with TestClient(
        build_http_app(build_workspace_router(WorkspaceService(unavailable_uow)))
    ) as client:
        response = client.post(
            "/workspaces",
            content='{"secret-value":',
            headers={"Content-Type": "application/json"},
        )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_request"
    assert "secret-value" not in response.text


@pytest.mark.parametrize(
    "body",
    [
        b'{"interviewee_name":"\xff"}',
        b'{"interviewee_name":' + b"1" * 5000 + b"}",
    ],
    ids=["invalid_utf8", "oversized_integer"],
)
def test_body_decode_failure_returns_safe_error_envelope(body: bytes) -> None:
    """框架無法解碼 body 的 400 也須符合公開錯誤格式。"""
    with TestClient(
        build_http_app(build_workspace_router(WorkspaceService(unavailable_uow)))
    ) as client:
        response = client.post(
            "/workspaces",
            content=body,
            headers={"Content-Type": "application/json"},
        )

    assert response.status_code == 400
    assert response.json() == {"detail": {"code": "invalid_request"}}


def test_other_http_errors_keep_framework_body_and_headers() -> None:
    """400 的正規化不得改寫其他模組的已知 HTTP 拒絕。"""
    router = APIRouter()

    @router.get("/conflict")
    def conflict() -> None:
        raise HTTPException(
            status_code=409,
            detail={"code": "custom_conflict"},
            headers={"Retry-After": "5"},
        )

    with TestClient(build_http_app(router)) as client:
        response = client.get("/conflict")

    assert response.status_code == 409
    assert response.json() == {"detail": {"code": "custom_conflict"}}
    assert response.headers["Retry-After"] == "5"


def test_openapi_describes_actual_error_contract() -> None:
    """OpenAPI 宣告的 400／422／404／500 須與安全錯誤 envelope 相同。"""
    with TestClient(
        build_http_app(build_workspace_router(WorkspaceService(unavailable_uow)))
    ) as client:
        document = client.get("/openapi.json").json()
    paths = document["paths"]
    for path, method, status in [
        ("/workspaces", "post", "400"),
        ("/workspaces", "post", "422"),
        ("/workspaces", "post", "500"),
        ("/workspaces/{workspace_id}", "get", "404"),
        ("/workspaces/{workspace_id}", "patch", "404"),
    ]:
        schema = paths[path][method]["responses"][status]["content"][
            "application/json"
        ]["schema"]
        assert schema["$ref"] == "#/components/schemas/ErrorResponse"
    location = document["components"]["schemas"]["ValidationIssue"]["properties"][
        "loc"
    ]["items"]["anyOf"]
    integer_location = next(item for item in location if item["type"] == "integer")
    assert integer_location["minimum"] == 0
    assert integer_location["maximum"] == 9007199254740991


def test_internal_error_is_generic_and_not_retried(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """一次儲存失敗只執行一次，不向客戶端洩漏 SQL 或連線設定。"""
    attempts = 0

    def fail() -> WorkspaceUnitOfWork:
        nonlocal attempts
        attempts += 1
        return unavailable_uow()

    with TestClient(
        build_http_app(build_workspace_router(WorkspaceService(fail))),
        raise_server_exceptions=False,
    ) as client:
        response = client.post("/workspaces", json={"interviewee_name": "合成人員"})
    assert response.status_code == 500
    assert response.json() == {"detail": {"code": "internal_error"}}
    assert ErrorResponse.model_validate(response.json()).detail.code == "internal_error"
    assert attempts == 1
    recorded = json.loads(caplog.records[-1].message)
    assert recorded["request_id"] == response.headers["X-Request-ID"]
    assert recorded["method"] == "POST"
    assert recorded["route"] == "/workspaces"
    assert recorded["error_type"] == "RuntimeError"
    assert recorded["frames"][-1]["function"] == "unavailable_uow"
    assert "secret-password" not in caplog.text
    assert "private_employee" not in caplog.text
