"""完整 JD 讀取；HTTP 不提供另一套領域載入方式。"""

from fastapi import APIRouter

from caliburn.modules.job_description.application import queries as application
from caliburn.modules.job_description.application.errors import (
    JobDescriptionNotFoundError,
)
from caliburn.modules.job_description.presentation.api.errors import (
    ERROR_RESPONSES,
    JobDescriptionRoute,
)
from caliburn.modules.job_description.presentation.api.schemas.content import (
    JobDescriptionResponse,
)
from caliburn.shared.presentation.api.values import HttpId


def build_queries_router(queries: application.JobDescriptionQueries) -> APIRouter:
    router = APIRouter(
        tags=["JD"], route_class=JobDescriptionRoute, responses=ERROR_RESPONSES
    )

    @router.get(
        "/workspaces/{workspace_id}/job-descriptions/{job_description_id}",
        operation_id="get_job_description",
        response_model=JobDescriptionResponse,
        summary="讀取完整 JD",
    )
    def get_job_description(
        workspace_id: HttpId, job_description_id: HttpId
    ) -> JobDescriptionResponse:
        return JobDescriptionResponse.model_validate(
            application.get_job_description(
                workspace_id=workspace_id,
                job_description_id=job_description_id,
                queries=queries,
            )
        )

    @router.get(
        "/workspaces/{workspace_id}/job-description",
        operation_id="get_workspace_job_description",
        response_model=JobDescriptionResponse,
        summary="讀取 Workspace 的 JD",
    )
    def get_workspace_job_description(workspace_id: HttpId) -> JobDescriptionResponse:
        result = application.find_job_description_by_workspace(
            workspace_id=workspace_id, queries=queries
        )
        if result is None:
            raise JobDescriptionNotFoundError("Workspace 尚無 JD")
        return JobDescriptionResponse.model_validate(result)

    return router
