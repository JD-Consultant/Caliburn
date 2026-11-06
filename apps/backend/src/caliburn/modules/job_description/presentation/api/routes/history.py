"""JD 保存點查閱、比較與恢復；不判斷上層編修資格。"""

from typing import Annotated

from fastapi import APIRouter, Query, Request

from caliburn.modules.job_description.application.history import operations
from caliburn.modules.job_description.presentation.api.dependencies import (
    JobDescriptionUoWFactory,
)
from caliburn.modules.job_description.presentation.api.errors import (
    ERROR_RESPONSES,
    JobDescriptionRoute,
)
from caliburn.modules.job_description.presentation.api.responses import write_response
from caliburn.modules.job_description.presentation.api.schemas.common import (
    CorrelationIdInput,
    ExpectedVersionQuery,
    HistoryPageSizeQuery,
)
from caliburn.modules.job_description.presentation.api.schemas.content import (
    JobDescriptionResponse,
)
from caliburn.modules.job_description.presentation.api.schemas.history import (
    HistoryPageResponse,
    HistoryResponse,
    JobDescriptionDifferenceResponse,
    RestoreJobDescriptionRequest,
)
from caliburn.shared.presentation.api.values import HttpId


def build_history_router(
    *, queries: operations.HistoryQueries, uow_factory: JobDescriptionUoWFactory
) -> APIRouter:
    router = APIRouter(
        prefix="/workspaces/{workspace_id}/job-descriptions",
        tags=["JD 歷史"],
        route_class=JobDescriptionRoute,
        responses=ERROR_RESPONSES,
    )

    @router.get(
        "/{job_description_id}/history",
        operation_id="list_job_description_history",
        response_model=HistoryPageResponse,
        summary="列出 JD 保存紀錄",
    )
    def list_history(
        workspace_id: HttpId,
        job_description_id: HttpId,
        page_size: Annotated[
            HistoryPageSizeQuery | None,
            Query(description="省略或 0 為 20 筆，最多 100 筆"),
        ] = None,
        page_token: Annotated[str | None, Query()] = None,
        correlation_id: Annotated[CorrelationIdInput | None, Query()] = None,
        reverts_correlation_id: Annotated[CorrelationIdInput | None, Query()] = None,
    ) -> HistoryPageResponse:
        return HistoryPageResponse.model_validate(
            operations.list_history(
                workspace_id=workspace_id,
                job_description_id=job_description_id,
                queries=queries,
                page_size=page_size if page_size is not None else 20,
                page_token=page_token,
                correlation_id=correlation_id,
                reverts_correlation_id=reverts_correlation_id,
            )
        )

    @router.get(
        "/{job_description_id}/history:compare",
        operation_id="compare_job_description_history",
        response_model=JobDescriptionDifferenceResponse,
        summary="比較兩個 JD 保存點",
    )
    def compare_history(
        workspace_id: HttpId,
        job_description_id: HttpId,
        before_version: Annotated[ExpectedVersionQuery, Query()],
        after_version: Annotated[ExpectedVersionQuery, Query()],
    ) -> JobDescriptionDifferenceResponse:
        return JobDescriptionDifferenceResponse.model_validate(
            operations.compare_history(
                workspace_id=workspace_id,
                job_description_id=job_description_id,
                before_version=before_version,
                after_version=after_version,
                queries=queries,
            )
        )

    @router.get(
        "/{job_description_id}/history/{version}",
        operation_id="get_job_description_history",
        response_model=HistoryResponse,
        summary="讀取保存點的完整 JD",
    )
    def get_history(
        workspace_id: HttpId,
        job_description_id: HttpId,
        version: ExpectedVersionQuery,
    ) -> HistoryResponse:
        return HistoryResponse.model_validate(
            operations.get_history(
                workspace_id=workspace_id,
                job_description_id=job_description_id,
                version=version,
                queries=queries,
            )
        )

    @router.post(
        "/{job_description_id}:restore",
        operation_id="restore_job_description",
        response_model=JobDescriptionResponse,
        summary="將指定 JD 保存點恢復為新版本",
    )
    def restore(
        workspace_id: HttpId,
        request: Request,
        job_description_id: HttpId,
        body: RestoreJobDescriptionRequest,
    ) -> JobDescriptionResponse:
        return write_response(
            request,
            operations.restore(
                workspace_id=workspace_id,
                input=body.to_application(job_description_id=job_description_id),
                uow_factory=uow_factory,
            ),
        )

    return router
