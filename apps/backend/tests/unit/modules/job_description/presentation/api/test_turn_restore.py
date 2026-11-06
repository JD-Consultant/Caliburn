"""正式完成輪 JD 撤銷路由：可信版本、無業務 body、提交事實不丟失。"""

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from caliburn.modules.job_description.application.errors import (
    JobDescriptionConcurrencyError,
    JobDescriptionPersistenceError,
)
from caliburn.modules.job_description.application.history import turn_changes
from caliburn.modules.job_description.application.job_description_results import (
    JobDescriptionResult,
)
from caliburn.modules.job_description.presentation.api import responses
from caliburn.modules.job_description.presentation.api.routes import turn_history
from caliburn.modules.job_description.presentation.api.schemas.content import (
    JobDescriptionResponse,
)
from tests.unit.modules.job_description.application.test_turn_history import (
    CompletedReader,
    SavedHistory,
)
from tests.unit.modules.job_description.application.test_turn_restore import (
    CoreRestoreRecorder,
    no_direct_uow,
)


def client(history: SavedHistory, reader: CompletedReader) -> TestClient:
    app = FastAPI()
    app.include_router(
        turn_history.build_turn_history_router(
            queries=history, completed_turn_reader=reader, uow_factory=no_direct_uow
        )
    )
    return TestClient(app)


def path(history: SavedHistory) -> str:
    versions = history.versions
    return (
        f"/workspaces/{versions.workspace_id}/job-descriptions/"
        f"{versions.job_description_id}/turns/{versions.turn_id}:restore"
    )


def test_restore_endpoint_uses_trusted_completion_and_returns_full_jd(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    history = SavedHistory()
    core = CoreRestoreRecorder(history)
    monkeypatch.setattr(turn_changes, "restore_turn_changes", core)
    with client(history, CompletedReader(history.versions)) as connection:
        response = connection.post(path(history))
    assert response.status_code == 200, response.text
    assert response.json() == core.result.model_dump(mode="json")
    assert len(core.calls) == 1
    _, received, _ = core.calls[0]
    assert received.base_version == history.versions.before_version
    assert received.completed_version == history.versions.after_version
    assert received.correlation_id == str(history.versions.turn_id)


def test_uncompleted_turn_is_404_and_does_not_call_restore(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    history = SavedHistory()
    core = CoreRestoreRecorder(history)
    monkeypatch.setattr(turn_changes, "restore_turn_changes", core)
    with client(history, CompletedReader(None)) as connection:
        response = connection.post(path(history))
    assert response.status_code == 404
    assert response.json() == {
        "detail": {"code": "jd_turn_not_found", "commit_status": "not_committed"}
    }
    assert core.calls == []


@pytest.mark.parametrize(
    ("error", "status", "detail"),
    [
        (
            JobDescriptionConcurrencyError("later-write", reason="version"),
            409,
            {
                "code": "jd_concurrency_conflict",
                "commit_status": "not_committed",
                "reason": "version",
            },
        ),
        (
            JobDescriptionPersistenceError(commit_status="unknown"),
            500,
            {"code": "jd_persistence_error", "commit_status": "unknown"},
        ),
        (
            JobDescriptionPersistenceError(commit_status="committed"),
            500,
            {"code": "jd_persistence_error", "commit_status": "committed"},
        ),
    ],
)
def test_core_failure_preserves_status_and_commit_facts(
    monkeypatch: pytest.MonkeyPatch,
    error: Exception,
    status: int,
    detail: dict[str, str],
) -> None:
    history = SavedHistory()
    core = CoreRestoreRecorder(history)
    core.error = error
    monkeypatch.setattr(turn_changes, "restore_turn_changes", core)
    with client(history, CompletedReader(history.versions)) as connection:
        response = connection.post(path(history))
    assert response.status_code == status
    assert response.json() == {"detail": detail}


def test_response_failure_after_write_retains_committed_fact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    history = SavedHistory()
    core = CoreRestoreRecorder(history)
    monkeypatch.setattr(turn_changes, "restore_turn_changes", core)

    def fail_after_write_response(
        request: Request, result: JobDescriptionResult
    ) -> JobDescriptionResponse:
        responses.write_response(request, result)
        raise RuntimeError("合成回覆故障")

    monkeypatch.setattr(turn_history, "write_response", fail_after_write_response)
    with client(history, CompletedReader(history.versions)) as connection:
        response = connection.post(path(history))
    assert response.status_code == 500
    assert response.json() == {
        "detail": {"code": "internal_error", "commit_status": "committed"}
    }


def test_restore_openapi_has_no_business_body_or_client_versions() -> None:
    history = SavedHistory()
    with client(history, CompletedReader(history.versions)) as connection:
        schema = connection.get("/openapi.json").json()
    endpoint = (
        "/workspaces/{workspace_id}/job-descriptions/{job_description_id}"
        "/turns/{turn_id}:restore"
    )
    operation = schema["paths"][endpoint]["post"]
    assert operation["operationId"] == "restore_job_description_turn"
    assert "requestBody" not in operation
    assert {parameter["in"] for parameter in operation["parameters"]} == {"path"}
    assert operation["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/JobDescriptionResponse"
    }
