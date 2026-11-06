"""共通條件內容與分類的 HTTP 入口。"""

from fastapi import APIRouter, Request, Response, status

from caliburn.modules.job_description.application import conditions
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
    AddConditionRequest,
    JobDescriptionResponse,
    UpdateConditionRequest,
)
from caliburn.shared.presentation.api.values import HttpId


def build_conditions_router(uow_factory: JobDescriptionUoWFactory) -> APIRouter:
    """只映射 HTTP 與用例；交易與版本前置由 Application 完成。"""
    router = APIRouter(
        prefix="/workspaces/{workspace_id}/job-descriptions",
        tags=["jd-conditions"],
        route_class=JobDescriptionRoute,
        responses=ERROR_RESPONSES,
    )

    @router.post(
        "/{job_description_id}/conditions",
        response_model=JobDescriptionResponse,
        operation_id="jd_add_condition",
        summary="新增共通條件",
        name="jd_add_condition",
        status_code=status.HTTP_201_CREATED,
        responses=CREATED_RESPONSES,
    )
    def add_condition(
        workspace_id: HttpId,
        job_description_id: HttpId,
        body: AddConditionRequest,
        request: Request,
        response: Response,
    ) -> JobDescriptionResponse:
        result = conditions.add_condition(
            workspace_id=workspace_id,
            job_description_id=job_description_id,
            expected_version=body.expected_version,
            kind=body.kind,
            text=body.text,
            correlation_id=body.correlation_id,
            citations=tuple(change.to_application() for change in body.citations),
            uow_factory=uow_factory,
        )
        return created_response(request, response, result)

    @router.patch(
        "/{job_description_id}/conditions/{condition_id}",
        response_model=JobDescriptionResponse,
        operation_id="jd_update_condition",
        summary="修改共通條件",
        name="jd_update_condition",
    )
    def update_condition(
        workspace_id: HttpId,
        request: Request,
        job_description_id: HttpId,
        condition_id: HttpId,
        body: UpdateConditionRequest,
    ) -> JobDescriptionResponse:
        result = conditions.update_condition(
            workspace_id=workspace_id,
            input=conditions.UpdateConditionInput.model_validate(
                {
                    "job_description_id": job_description_id,
                    "condition_id": condition_id,
                    **body.model_dump(exclude_unset=True),
                }
            ),
            uow_factory=uow_factory,
        )
        return write_response(request, result)

    @router.delete(
        "/{job_description_id}/conditions/{condition_id}",
        response_model=JobDescriptionResponse,
        operation_id="jd_delete_condition",
        summary="刪除共通條件",
        name="jd_delete_condition",
    )
    def delete_condition(
        workspace_id: HttpId,
        request: Request,
        job_description_id: HttpId,
        condition_id: HttpId,
        expected_version: ExpectedVersionQuery,
        correlation_id: CorrelationIdInput | None = None,
    ) -> JobDescriptionResponse:
        result = conditions.delete_condition(
            workspace_id=workspace_id,
            job_description_id=job_description_id,
            condition_id=condition_id,
            expected_version=expected_version,
            correlation_id=correlation_id,
            uow_factory=uow_factory,
        )
        return write_response(request, result)

    return router
