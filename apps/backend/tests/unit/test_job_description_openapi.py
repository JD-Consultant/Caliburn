"""JD 的 HTTP 能力、文件與契約不得依賴資料庫連線。"""

from caliburn.host.app import build_app
from caliburn.modules.job_description.presentation.api.schemas.content import (
    CreateJobDescriptionRequest,
    UpdateJobDescriptionRequest,
)
from caliburn.modules.job_description.presentation.api.schemas.history import (
    RestoreJobDescriptionRequest,
)
from caliburn.modules.job_description.presentation.api.schemas.tasks import (
    AddTaskRequest,
)
from tests.reference_configuration import HOST_REFERENCE_CONFIGURATION


def test_jd_openapi_exposes_selected_capabilities() -> None:
    """內容編修與歷史公開，四個局部查詢仍留在 Application。"""
    app = build_app(
        reference_configuration=HOST_REFERENCE_CONFIGURATION,
        database_url="postgresql+psycopg://localhost:1/unreachable",
    )
    schema = app.openapi()
    operations = [
        operation
        for path, methods in schema["paths"].items()
        if path.startswith("/workspaces/{workspace_id}/job-description")
        for method, operation in methods.items()
        if method in {"get", "post", "put", "patch", "delete"}
    ]
    assert len(operations) == 32
    operation_ids = [operation["operationId"] for operation in operations]
    assert len(set(operation_ids)) == 32
    assert {
        "jd_get_citation",
        "jd_change_citations",
        "export_job_description_pdf",
        "get_job_description_turn_changes",
        "restore_job_description_turn",
        "jd_get_history_citation",
    } <= set(operation_ids)
    assert not any(
        part in path
        for path in schema["paths"]
        for part in (
            ":move",
            ":reclassify",
            "/outcomes",
            "/requirements",
            "/knowledge-references",
            "/skill-references",
        )
    )
    assert (
        "get"
        not in schema["paths"][
            "/workspaces/{workspace_id}/job-descriptions/{job_description_id}/tasks/{task_id}"
        ]
    )
    assert schema["info"]["title"] == "Caliburn"
    assert app.docs_url == "/docs"
    assert app.redoc_url == "/redoc"
    assert app.openapi_url == "/openapi.json"


def test_history_page_size_omission_has_no_invalid_integer_default() -> None:
    """可省略的 Query 不投影與十進位字串型別衝突的整數預設值。"""
    app = build_app(
        reference_configuration=HOST_REFERENCE_CONFIGURATION,
        database_url="postgresql+psycopg://localhost:1/unreachable",
    )
    history = app.openapi()["paths"][
        "/workspaces/{workspace_id}/job-descriptions/{job_description_id}/history"
    ]["get"]
    size = next(p["schema"] for p in history["parameters"] if p["name"] == "page_size")
    assert size["anyOf"][0]["type"] == "string"
    assert size.get("default") is None


def test_jd_writes_return_complete_content_with_one_version() -> None:
    """所有內容寫入與恢復共用完整回覆，不再暴露交易座標或寫入封套。"""
    schema = build_app(
        reference_configuration=HOST_REFERENCE_CONFIGURATION,
        database_url="postgresql+psycopg://localhost:1/unreachable",
    ).openapi()
    models = schema["components"]["schemas"]
    fields = models["JobDescriptionResponse"]["properties"]
    assert {"job_description_id", "workspace_id", "tasks", "version"} <= fields.keys()
    assert "position" not in fields
    assert "JobDescriptionWriteResponse" not in models
    assert "HistoryPositionResponse" not in models
    for path, operations in schema["paths"].items():
        if not path.startswith("/workspaces/{workspace_id}/job-description"):
            continue
        for method, operation in operations.items():
            if method not in {"post", "put", "patch", "delete"}:
                continue
            for code, response in operation["responses"].items():
                if code.startswith("2"):
                    assert response["content"]["application/json"]["schema"] == {
                        "$ref": "#/components/schemas/JobDescriptionResponse"
                    }
                    if code == "201":
                        assert "Location" in response["headers"]


def test_documented_request_examples_remain_valid_after_openapi_generation() -> None:
    """驗證導出的實際例子；OpenAPI 轉換可能省略 dict 內的 null。"""
    schema = build_app(
        reference_configuration=HOST_REFERENCE_CONFIGURATION,
        database_url="postgresql+psycopg://localhost:1/unreachable",
    ).openapi()
    for model in (
        CreateJobDescriptionRequest,
        AddTaskRequest,
        RestoreJobDescriptionRequest,
    ):
        for example in schema["components"]["schemas"][model.__name__]["examples"]:
            model.model_validate(example)
    patch = schema["paths"][
        "/workspaces/{workspace_id}/job-descriptions/{job_description_id}"
    ]["patch"]
    for example in patch["requestBody"]["content"]["application/json"][
        "examples"
    ].values():
        UpdateJobDescriptionRequest.model_validate(example["value"])
