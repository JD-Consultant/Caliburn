"""內容路由覆蓋及 transport mapping；不代表真 PostgreSQL 證據。"""

from uuid import uuid7

from fastapi import FastAPI
from fastapi.testclient import TestClient

from caliburn.modules.job_description.application.persistence import (
    JobDescriptionUnitOfWork,
)
from caliburn.modules.job_description.domain.models.job_description import (
    JobDescription,
)
from caliburn.modules.job_description.presentation.api.routes.collaborations import (
    build_collaborations_router,
)
from caliburn.modules.job_description.presentation.api.routes.conditions import (
    build_conditions_router,
)
from caliburn.modules.job_description.presentation.api.routes.definitions import (
    build_definitions_router,
)
from caliburn.modules.job_description.presentation.api.routes.duties import (
    build_duties_router,
)
from caliburn.modules.job_description.presentation.api.routes.job_descriptions import (
    build_job_descriptions_router,
)
from caliburn.modules.job_description.presentation.api.routes.tasks import (
    build_tasks_router,
)
from caliburn.shared.presentation.api.app import build_http_app

from ...application.recording_uow import RecordingUnitOfWork


def unused_factory() -> JobDescriptionUnitOfWork:
    raise AssertionError("OpenAPI 不應取得交易")


def test_content_routes_expose_20_resource_writes() -> None:
    """完整公開已授權能力，每個操作有唯一具名 operation_id。"""
    app = FastAPI()
    for builder in (
        build_job_descriptions_router,
        build_duties_router,
        build_definitions_router,
        build_tasks_router,
        build_collaborations_router,
        build_conditions_router,
    ):
        app.include_router(builder(unused_factory))
    paths = app.openapi()["paths"]
    operations = [
        operation
        for path in paths.values()
        for method, operation in path.items()
        if method in {"post", "patch", "put", "delete"}
    ]

    assert len(operations) == 20
    assert len({operation["operationId"] for operation in operations}) == 20
    assert all(operation["tags"] for operation in operations)
    for operation in operations:
        response = operation["responses"]
        success = response.get("201", response.get("200"))
        assert success["content"]["application/json"]["schema"] == {
            "$ref": "#/components/schemas/JobDescriptionResponse"
        }


def test_created_location_preserves_mount_prefix_and_omits_query() -> None:
    """Location 沿具名路由反解，部署掛載前綴不會遺失或帶入請求 query。"""
    root = JobDescription(id=uuid7(), workspace_id=uuid7())
    unit = RecordingUnitOfWork(root)
    app = FastAPI()
    mounted = build_http_app(build_duties_router(lambda: unit))

    @mounted.get(
        "/workspaces/{workspace_id}/job-descriptions/{job_description_id}",
        name="get_job_description",
    )
    def read_description(workspace_id: str, job_description_id: str) -> None:
        """提供 Location 的正式查詢路徑；本測例只驗反解。"""

    app.mount("/api", mounted)

    with TestClient(app) as client:
        response = client.post(
            f"/api/workspaces/{root.workspace_id}/job-descriptions/{root.id}/duties?unused=value",
            json={"expected_version": 4, "name": "職責"},
        )

    assert response.status_code == 201
    payload = response.json()
    assert payload["duties"][0]["name"] == "職責"
    assert response.headers["Location"] == (
        f"http://testserver/api/workspaces/{root.workspace_id}/job-descriptions/{root.id}"
    )
    assert payload["version"] == 5
    assert unit.committed and unit.closed
