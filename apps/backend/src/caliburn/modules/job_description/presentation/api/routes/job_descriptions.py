"""JD 建立與基本資料的 HTTP 入口。"""

from typing import Annotated

from fastapi import APIRouter, Body, Request, Response, status

from caliburn.modules.job_description.application import job_descriptions
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
from caliburn.modules.job_description.presentation.api.schemas.content import (
    CreateJobDescriptionRequest,
    JobDescriptionResponse,
    UpdateJobDescriptionRequest,
)
from caliburn.shared.presentation.api.values import HttpId


def build_job_descriptions_router(uow_factory: JobDescriptionUoWFactory) -> APIRouter:
    """只映射 HTTP 與用例；交易與版本前置由 Application 完成。"""
    router = APIRouter(
        prefix="/workspaces/{workspace_id}",
        tags=["job-descriptions"],
        route_class=JobDescriptionRoute,
        responses=ERROR_RESPONSES,
    )

    @router.post(
        "/job-description",
        response_model=JobDescriptionResponse,
        operation_id="jd_create_job_description",
        summary="建立職務說明書",
        name="jd_create_job_description",
        status_code=status.HTTP_201_CREATED,
        responses=CREATED_RESPONSES,
    )
    def create_job_description(
        workspace_id: HttpId,
        body: CreateJobDescriptionRequest,
        request: Request,
        response: Response,
    ) -> JobDescriptionResponse:
        result = job_descriptions.create_job_description(
            workspace_id=workspace_id,
            correlation_id=body.correlation_id,
            uow_factory=uow_factory,
        )
        return created_response(request, response, result)

    @router.patch(
        "/job-descriptions/{job_description_id}",
        response_model=JobDescriptionResponse,
        operation_id="jd_update_job_description",
        summary="修改職務說明書基本資料",
        name="jd_update_job_description",
    )
    def update_job_description(
        workspace_id: HttpId,
        request: Request,
        job_description_id: HttpId,
        body: Annotated[
            UpdateJobDescriptionRequest,
            Body(
                description=(
                    "省略欄位會保留；清空用途可送 "
                    '{"expected_version": 2, "purpose": null}。'
                ),
                openapi_examples={
                    "update_title": {
                        "summary": "只改職稱，其餘欄位保留",
                        "value": {"expected_version": 1, "job_title": "設備工程師"},
                    },
                },
            ),
        ],
    ) -> JobDescriptionResponse:
        result = job_descriptions.update_job_description(
            workspace_id=workspace_id,
            input=job_descriptions.UpdateJobDescriptionInput.model_validate(
                {
                    "job_description_id": job_description_id,
                    **body.model_dump(exclude_unset=True),
                }
            ),
            uow_factory=uow_factory,
        )
        return write_response(request, result)

    return router
