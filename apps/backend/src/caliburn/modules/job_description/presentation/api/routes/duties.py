"""職責內容與排序的 HTTP 入口。"""

from fastapi import APIRouter, Request, Response, status

from caliburn.modules.job_description.application import duties
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
    AddDutyRequest,
    JobDescriptionResponse,
    UpdateDutyRequest,
)
from caliburn.shared.presentation.api.values import HttpId


def build_duties_router(uow_factory: JobDescriptionUoWFactory) -> APIRouter:
    """只映射 HTTP 與用例；交易與版本前置由 Application 完成。"""
    router = APIRouter(
        prefix="/workspaces/{workspace_id}/job-descriptions",
        tags=["jd-duties"],
        route_class=JobDescriptionRoute,
        responses=ERROR_RESPONSES,
    )

    @router.post(
        "/{job_description_id}/duties",
        response_model=JobDescriptionResponse,
        operation_id="jd_add_duty",
        summary="新增職責",
        name="jd_add_duty",
        status_code=status.HTTP_201_CREATED,
        responses=CREATED_RESPONSES,
    )
    def add_duty(
        workspace_id: HttpId,
        job_description_id: HttpId,
        body: AddDutyRequest,
        request: Request,
        response: Response,
    ) -> JobDescriptionResponse:
        result = duties.add_duty(
            workspace_id=workspace_id,
            job_description_id=job_description_id,
            expected_version=body.expected_version,
            name=body.name,
            scope=body.scope,
            correlation_id=body.correlation_id,
            citations=tuple(change.to_application() for change in body.citations),
            uow_factory=uow_factory,
        )
        return created_response(request, response, result)

    @router.patch(
        "/{job_description_id}/duties/{duty_id}",
        response_model=JobDescriptionResponse,
        operation_id="jd_update_duty",
        summary="修改職責",
        name="jd_update_duty",
    )
    def update_duty(
        workspace_id: HttpId,
        request: Request,
        job_description_id: HttpId,
        duty_id: HttpId,
        body: UpdateDutyRequest,
    ) -> JobDescriptionResponse:
        result = duties.update_duty(
            workspace_id=workspace_id,
            input=duties.UpdateDutyInput.model_validate(
                {
                    "job_description_id": job_description_id,
                    "duty_id": duty_id,
                    **body.model_dump(exclude_unset=True),
                }
            ),
            uow_factory=uow_factory,
        )
        return write_response(request, result)

    @router.delete(
        "/{job_description_id}/duties/{duty_id}",
        response_model=JobDescriptionResponse,
        operation_id="jd_delete_duty",
        summary="刪除職責",
        name="jd_delete_duty",
    )
    def delete_duty(
        workspace_id: HttpId,
        request: Request,
        job_description_id: HttpId,
        duty_id: HttpId,
        expected_version: ExpectedVersionQuery,
        correlation_id: CorrelationIdInput | None = None,
    ) -> JobDescriptionResponse:
        result = duties.delete_duty(
            workspace_id=workspace_id,
            job_description_id=job_description_id,
            duty_id=duty_id,
            expected_version=expected_version,
            correlation_id=correlation_id,
            uow_factory=uow_factory,
        )
        return write_response(request, result)

    return router
