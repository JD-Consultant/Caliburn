"""用正式 router 與 response schema 驗完成輪只讀差異的 HTTP 契約。"""

from dataclasses import replace
from uuid import uuid7

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from caliburn.modules.job_description.application.errors import (
    JobDescriptionHistoryDataError,
    JobDescriptionHistoryNotFoundError,
    JobDescriptionQueryError,
)
from caliburn.modules.job_description.application.persistence import (
    JobDescriptionUnitOfWork,
)
from caliburn.modules.job_description.presentation.api.routes.turn_history import (
    build_turn_history_router,
)
from tests.unit.modules.job_description.application.test_turn_history import (
    CompletedReader,
    SavedHistory,
)


def client(history: SavedHistory, reader: CompletedReader) -> TestClient:
    app = FastAPI()
    app.include_router(
        build_turn_history_router(
            queries=history, completed_turn_reader=reader, uow_factory=no_writes
        )
    )
    return TestClient(app)


def no_writes() -> JobDescriptionUnitOfWork:
    raise AssertionError("完成輪差異查讀不應建立可寫 UoW")


def path(history: SavedHistory) -> str:
    versions = history.versions
    return (
        f"/workspaces/{versions.workspace_id}/job-descriptions/"
        f"{versions.job_description_id}/turns/{versions.turn_id}/changes"
    )


def test_completed_turn_endpoint_returns_full_fixed_contents_and_difference() -> None:
    history = SavedHistory()
    with client(history, CompletedReader(history.versions)) as connection:
        response = connection.get(path(history))
    assert response.status_code == 200, response.text
    body = response.json()
    versions = history.versions
    assert body["workspace_id"] == str(versions.workspace_id)
    assert body["job_description_id"] == str(versions.job_description_id)
    assert body["turn_id"] == str(versions.turn_id)
    assert body["before_version"] == body["difference"]["before_version"] == 2
    assert body["after_version"] == body["difference"]["after_version"] == 5
    assert body["before"]["purpose"] == "原職務目的"
    assert body["after"]["purpose"] == "輪次完成目的"
    for section in (
        "duties",
        "tasks",
        "knowledge",
        "skills",
        "collaborations",
        "conditions",
        "citations",
    ):
        assert body["before"][section]
        assert body["after"][section]
    assert body["before"]["baseline_competency_level"] == 3
    assert "correlation_id" not in body


def test_same_version_returns_complete_content_with_empty_difference() -> None:
    history = SavedHistory()
    reader = CompletedReader(replace(history.versions, after_version=2))
    with client(history, reader) as connection:
        response = connection.get(path(history))
    assert response.status_code == 200
    body = response.json()
    assert body["before"] == body["after"]
    assert body["difference"]["items"] == body["difference"]["collections"] == []


@pytest.mark.parametrize("missing", [True, False])
def test_unavailable_or_wrong_jd_completion_returns_safe_not_found(
    missing: bool,
) -> None:
    history = SavedHistory()
    reader = CompletedReader(
        None if missing else replace(history.versions, job_description_id=uuid7())
    )
    with client(history, reader) as connection:
        response = connection.get(path(history))
    assert response.status_code == 404
    assert response.json() == {"detail": {"code": "jd_turn_not_found"}}
    assert history.reads == []


@pytest.mark.parametrize(
    "error_type", [JobDescriptionHistoryNotFoundError, JobDescriptionHistoryDataError]
)
def test_fixed_history_failure_is_safe_data_error(error_type: type[Exception]) -> None:
    history = SavedHistory()
    history.error = error_type("secret-internal-snapshot-details")
    with client(history, CompletedReader(history.versions)) as connection:
        response = connection.get(path(history))
    assert response.status_code == 500
    assert response.json() == {"detail": {"code": "jd_turn_data_error"}}
    assert response.headers["x-request-id"]
    assert "secret-internal" not in response.text


def test_technical_query_failure_retains_technical_error_code() -> None:
    history = SavedHistory()
    history.error = JobDescriptionQueryError("technical-query-details")
    with client(history, CompletedReader(history.versions)) as connection:
        response = connection.get(path(history))
    assert response.status_code == 500
    assert response.json() == {"detail": {"code": "jd_query_error"}}


@pytest.mark.parametrize("field", ["workspace_id", "job_description_id", "turn_id"])
def test_invalid_path_uuid_rejects_before_callback(field: str) -> None:
    history = SavedHistory()
    reader = CompletedReader(history.versions)
    endpoint = path(history).replace(
        str(getattr(history.versions, field)), "not-a-uuid"
    )
    with client(history, reader) as connection:
        response = connection.get(endpoint)
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_request"
    assert reader.calls == []
    assert history.reads == []


def test_openapi_declares_readonly_turn_operation_and_reuses_full_content_schema() -> (
    None
):
    history = SavedHistory()
    with client(history, CompletedReader(history.versions)) as connection:
        schema = connection.get("/openapi.json").json()
    endpoint = (
        "/workspaces/{workspace_id}/job-descriptions/{job_description_id}"
        "/turns/{turn_id}/changes"
    )
    operation = schema["paths"][endpoint]["get"]
    assert operation["operationId"] == "get_job_description_turn_changes"
    assert "requestBody" not in operation
    assert {parameter["in"] for parameter in operation["parameters"]} == {"path"}
    result = schema["components"]["schemas"]["JobDescriptionTurnChangesResponse"]
    assert (
        result["properties"]["before"]
        == result["properties"]["after"]
        == {"$ref": "#/components/schemas/JobDescriptionContentResponse"}
    )
    assert result["properties"]["difference"] == {
        "$ref": "#/components/schemas/JobDescriptionDifferenceResponse"
    }
