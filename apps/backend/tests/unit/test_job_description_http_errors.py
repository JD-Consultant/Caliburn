"""HTTP 邊界不得把程式錯誤當成輸入錯誤，或猜測提交結果。"""

import json
import logging
from typing import Literal
from uuid import uuid7

import pytest
from fastapi import APIRouter, Request
from fastapi.testclient import TestClient
from pydantic import BaseModel, ValidationError

from caliburn.host.app import build_app
from caliburn.modules.job_description.application.errors import (
    ConcurrencyReason,
    JobDescriptionConcurrencyError,
    JobDescriptionHistoryDataError,
    JobDescriptionPersistenceError,
)
from caliburn.modules.job_description.domain.models.job_description import (
    JobDescription,
)
from caliburn.modules.job_description.presentation.api.errors import (
    ERROR_RESPONSES,
    JobDescriptionRoute,
)
from caliburn.modules.job_description.presentation.api.routes.duties import (
    build_duties_router,
)
from caliburn.shared.presentation.api.app import build_http_app
from caliburn.shared.presentation.api.diagnostics import logger
from tests.reference_configuration import HOST_REFERENCE_CONFIGURATION
from tests.unit.modules.job_description.application.recording_uow import (
    RecordingUnitOfWork,
)


@pytest.mark.parametrize("status", ["not_committed", "unknown", "committed"])
def test_persistence_error_reports_known_commit_status(
    status: Literal["not_committed", "unknown", "committed"],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """三種提交事實皆保留，日誌與回應不得包含底層訊息。"""
    router = APIRouter(route_class=JobDescriptionRoute, responses=ERROR_RESPONSES)

    @router.post("/write")
    def write() -> None:
        try:
            raise RuntimeError("private SQL and input")
        except RuntimeError as error:
            raise JobDescriptionPersistenceError(commit_status=status) from error

    with TestClient(build_http_app(router)) as client:
        response = client.post("/write")
    assert response.status_code == 500
    assert response.json() == {
        "detail": {"code": "jd_persistence_error", "commit_status": status}
    }
    assert response.headers["X-Request-ID"]
    assert "private SQL and input" not in response.text + caplog.text
    entry = json.loads(caplog.records[-1].message)
    assert entry["error_type"] == "JobDescriptionPersistenceError"


def test_internal_validation_error_is_not_a_client_error() -> None:
    """用例後的 Pydantic 程式錯誤不得偽裝成用戶輸入 422。"""

    class InternalResult(BaseModel):
        number: int

    with pytest.raises(ValidationError) as caught:
        InternalResult.model_validate({"number": "private input"})
    router = APIRouter(route_class=JobDescriptionRoute)

    @router.post("/write")
    def write() -> None:
        raise caught.value

    with TestClient(build_http_app(router)) as client:
        response = client.post("/write")
    assert response.status_code == 500
    assert response.json() == {
        "detail": {"code": "internal_error", "commit_status": "unknown"}
    }
    assert "private input" not in response.text


@pytest.mark.parametrize(
    "reason", ["version", "serialization", "deadlock", "lock_timeout", "order"]
)
def test_concurrency_is_a_rejected_write(reason: ConcurrencyReason) -> None:
    """舊版衝突是確定未提交，不是未知結果或背景受理。"""
    router = APIRouter(route_class=JobDescriptionRoute)

    @router.post("/write")
    def write() -> None:
        raise JobDescriptionConcurrencyError("internal conflict detail", reason=reason)

    with TestClient(build_http_app(router)) as client:
        response = client.post("/write")
    assert response.status_code == 409
    assert response.json() == {
        "detail": {
            "code": "jd_concurrency_conflict",
            "commit_status": "not_committed",
            "reason": reason,
        }
    }


def test_corrupt_history_is_not_missing_history() -> None:
    """讀版損壞是技術錯誤，不回不存在或虛構寫入狀態。"""
    router = APIRouter(route_class=JobDescriptionRoute)

    @router.get("/history")
    def read_history() -> None:
        raise JobDescriptionHistoryDataError("invalid rows")

    with TestClient(build_http_app(router)) as client:
        response = client.get("/history")
    assert response.status_code == 500
    assert response.json() == {"detail": {"code": "jd_history_data_error"}}


@pytest.mark.parametrize("stage", ["location", "serialization"])
def test_response_failure_after_commit_preserves_committed(
    stage: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Location 與框架序列化都在提交後；失敗不能遺失已知提交事實。"""
    root = JobDescription(id=uuid7(), workspace_id=uuid7())
    uow = RecordingUnitOfWork(root)
    app = build_http_app(build_duties_router(lambda: uow))

    @app.get(
        "/workspaces/{workspace_id}/job-descriptions/{job_description_id}",
        name="get_job_description",
    )
    def read_description(workspace_id: str, job_description_id: str) -> None:
        """提供 Location 反解目標，讓本測例隔離提交後故障。"""

    def fail_location(*args: object, **kwargs: object) -> str:
        raise RuntimeError("private location failure")

    async def fail_serialization(**kwargs: object) -> None:
        raise RuntimeError("private serialization failure")

    if stage == "location":
        monkeypatch.setattr(Request, "url_for", fail_location)
    else:
        monkeypatch.setattr("fastapi.routing.serialize_response", fail_serialization)
    with TestClient(app) as client:
        response = client.post(
            f"/workspaces/{root.workspace_id}/job-descriptions/{root.id}/duties",
            json={"expected_version": 4, "name": "測試職責"},
        )
    assert uow.committed and uow.closed
    assert response.status_code == 500
    assert response.json()["detail"]["commit_status"] == "committed"
    assert "private" not in response.text


def test_logging_failure_does_not_replace_the_error_response() -> None:
    """日誌輸出失敗仍保留安全 JSON、追查 ID 與提交狀態。"""
    router = APIRouter(route_class=JobDescriptionRoute)

    @router.post("/write")
    def write() -> None:
        raise JobDescriptionPersistenceError(commit_status="committed")

    class BrokenHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            raise OSError("private log failure")

    handler = BrokenHandler()
    logger.addHandler(handler)
    try:
        with TestClient(
            build_http_app(router), raise_server_exceptions=False
        ) as client:
            response = client.post("/write")
    finally:
        logger.removeHandler(handler)
    assert response.status_code == 500
    assert response.json()["detail"]["commit_status"] == "committed"
    assert response.headers["X-Request-ID"]
    assert "private" not in response.text


@pytest.mark.parametrize(
    "body",
    [
        b'{"correlation_id":"\xff"}',
        b'{"correlation_id":' + b"1" * 5000 + b"}",
        b'{"correlation_id":',
    ],
    ids=["invalid_utf8", "oversized_integer", "invalid_json"],
)
def test_body_decode_error_uses_the_documented_envelope(body: bytes) -> None:
    """JSON 解碼的框架 400 也必須使用安全錯誤 envelope。"""
    app = build_app(
        reference_configuration=HOST_REFERENCE_CONFIGURATION,
        database_url="postgresql+psycopg://localhost:1/unreachable",
    )
    with TestClient(app) as client:
        response = client.post(
            f"/workspaces/{uuid7()}/job-description",
            content=body,
            headers={"Content-Type": "application/json"},
        )
    assert response.status_code == 400
    assert response.json() == {
        "detail": {"code": "invalid_request", "commit_status": "not_committed"}
    }
    assert (
        "400"
        in app.openapi()["paths"]["/workspaces/{workspace_id}/job-description"]["post"][
            "responses"
        ]
    )


def test_request_validation_reports_rejection_without_echoing_input() -> None:
    """輸入驗證先於用例，明示未提交並沿共用規則隱藏私有欄位。"""
    app = build_app(
        reference_configuration=HOST_REFERENCE_CONFIGURATION,
        database_url="postgresql+psycopg://localhost:1/unreachable",
    )
    with TestClient(app) as client:
        response = client.post(
            f"/workspaces/{uuid7()}/job-description",
            json={"private_field": "private input"},
        )
    assert response.status_code == 422
    assert response.json()["detail"] == {
        "code": "invalid_request",
        "commit_status": "not_committed",
        "errors": [{"loc": ["body", "unknown"], "code": "extra_forbidden"}],
    }
    assert "private" not in response.text
