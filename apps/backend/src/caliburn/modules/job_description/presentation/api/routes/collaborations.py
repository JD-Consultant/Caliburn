"""協作對象與內容的 HTTP 入口。"""

from fastapi import APIRouter, Request, Response, status

from caliburn.modules.job_description.application import collaborations
from caliburn.modules.job_description.presentation.api.dependencies import (
    JobDescriptionUoWFactory,
)
from caliburn.modules.job_description.presentation.api.errors import (
    ERROR_RESPONSES,
    JobDescriptionRoute,
)
from caliburn.modules.job_description.presentation.api.responses import (
    CREATED_RESPONSES,
    created_response,
    write_response,
)
from caliburn.modules.job_description.presentation.api.schemas.common import (
    CorrelationIdInput,
    ExpectedVersionQuery,
)
from caliburn.modules.job_description.presentation.api.schemas.content import (
    AddCollaborationRequest,
    JobDescriptionResponse,
    UpdateCollaborationRequest,
)
from caliburn.shared.presentation.api.values import HttpId


def build_collaborations_router(uow_factory: JobDescriptionUoWFactory) -> APIRouter:
    """只映射 HTTP 與用例；交易與版本前置由 Application 完成。"""
    router = APIRouter(
        prefix="/workspaces/{workspace_id}/job-descriptions",
        tags=["jd-collaborations"],
        route_class=JobDescriptionRoute,
        responses=ERROR_RESPONSES,
    )

    @router.post(
        "/{job_description_id}/collaborations",
        response_model=JobDescriptionResponse,
        operation_id="jd_add_collaboration",
        summary="新增協作對象",
        name="jd_add_collaboration",
        status_code=status.HTTP_201_CREATED,
        responses=CREATED_RESPONSES,
    )
    def add_collaboration(
        workspace_id: HttpId,
        job_description_id: HttpId,
        body: AddCollaborationRequest,
        request: Request,
        response: Response,
    ) -> JobDescriptionResponse:
        result = collaborations.add_collaboration(
            workspace_id=workspace_id,
            job_description_id=job_description_id,
            expected_version=body.expected_version,
            collaborator_name=body.collaborator_name,
            scope=body.scope,
            correlation_id=body.correlation_id,
            citations=tuple(change.to_application() for change in body.citations),
            uow_factory=uow_factory,
        )
        return created_response(request, response, result)

    @router.patch(
        "/{job_description_id}/collaborations/{collaboration_id}",
        response_model=JobDescriptionResponse,
        operation_id="jd_update_collaboration",
        summary="修改協作內容",
        name="jd_update_collaboration",
    )
    def update_collaboration(
        workspace_id: HttpId,
        request: Request,
        job_description_id: HttpId,
        collaboration_id: HttpId,
        body: UpdateCollaborationRequest,
    ) -> JobDescriptionResponse:
        result = collaborations.update_collaboration(
            workspace_id=workspace_id,
            input=collaborations.UpdateCollaborationInput.model_validate(
                {
                    "job_description_id": job_description_id,
                    "collaboration_id": collaboration_id,
                    **body.model_dump(exclude_unset=True),
                }
            ),
            uow_factory=uow_factory,
        )
        return write_response(request, result)

    @router.delete(
        "/{job_description_id}/collaborations/{collaboration_id}",
        response_model=JobDescriptionResponse,
        operation_id="jd_delete_collaboration",
        summary="刪除協作對象",
        name="jd_delete_collaboration",
    )
    def delete_collaboration(
        workspace_id: HttpId,
        request: Request,
        job_description_id: HttpId,
        collaboration_id: HttpId,
        expected_version: ExpectedVersionQuery,
        correlation_id: CorrelationIdInput | None = None,
    ) -> JobDescriptionResponse:
        result = collaborations.delete_collaboration(
            workspace_id=workspace_id,
            job_description_id=job_description_id,
            collaboration_id=collaboration_id,
            expected_version=expected_version,
            correlation_id=correlation_id,
            uow_factory=uow_factory,
        )
        return write_response(request, result)

    return router
