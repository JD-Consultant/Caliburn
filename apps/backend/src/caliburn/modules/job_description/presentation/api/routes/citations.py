"""JD 引用的人工查讀與逐筆增修；不啟動 Agent。"""

from fastapi import APIRouter, Request

from caliburn.modules.job_description.application.citation_sources import (
    CitationSourceQueries,
)
from caliburn.modules.job_description.application.citations import (
    ChangeCitationsInput,
    change_citations,
    get_citation,
    get_history_citation,
)
from caliburn.modules.job_description.application.history.operations import (
    HistoryQueries,
)
from caliburn.modules.job_description.application.queries import JobDescriptionQueries
from caliburn.modules.job_description.presentation.api.dependencies import (
    JobDescriptionUoWFactory,
)
from caliburn.modules.job_description.presentation.api.errors import (
    ERROR_RESPONSES,
    JobDescriptionRoute,
)
from caliburn.modules.job_description.presentation.api.responses import write_response
from caliburn.modules.job_description.presentation.api.schemas.citations import (
    ChangeCitationsRequest,
    CitationDetailsResponse,
)
from caliburn.modules.job_description.presentation.api.schemas.common import (
    ExpectedVersionQuery,
)
from caliburn.modules.job_description.presentation.api.schemas.content import (
    JobDescriptionResponse,
)
from caliburn.modules.memory.application.persistence import MemoryQueries
from caliburn.shared.presentation.api.values import HttpId


def build_citations_router(
    *,
    uow_factory: JobDescriptionUoWFactory,
    queries: JobDescriptionQueries,
    history_queries: HistoryQueries,
    sources: CitationSourceQueries,
    memory_queries: MemoryQueries,
) -> APIRouter:
    router = APIRouter(
        prefix="/workspaces/{workspace_id}/job-descriptions/{job_description_id}",
        tags=["jd-citations"],
        route_class=JobDescriptionRoute,
        responses=ERROR_RESPONSES,
    )

    @router.get(
        "/citations/{citation_id}",
        response_model=CitationDetailsResponse,
        operation_id="jd_get_citation",
        summary="查閱固定引用來源與核對狀態",
    )
    def read_citation(
        workspace_id: HttpId,
        job_description_id: HttpId,
        citation_id: HttpId,
        published_version: ExpectedVersionQuery | None = None,
    ) -> CitationDetailsResponse:
        result = get_citation(
            workspace_id=workspace_id,
            job_description_id=job_description_id,
            citation_id=citation_id,
            queries=queries,
            sources=sources,
            published_version=published_version,
            memory_queries=memory_queries,
        )
        return CitationDetailsResponse.from_result(result)

    @router.get(
        "/history/{version}/citations/{citation_id}",
        response_model=CitationDetailsResponse,
        operation_id="jd_get_history_citation",
        summary="查閱指定 JD 保存點的固定引用來源",
    )
    def read_history_citation(
        workspace_id: HttpId,
        job_description_id: HttpId,
        version: ExpectedVersionQuery,
        citation_id: HttpId,
        published_version: ExpectedVersionQuery | None = None,
    ) -> CitationDetailsResponse:
        result = get_history_citation(
            workspace_id=workspace_id,
            job_description_id=job_description_id,
            version=version,
            citation_id=citation_id,
            history_queries=history_queries,
            sources=sources,
            published_version=published_version,
            memory_queries=memory_queries,
        )
        return CitationDetailsResponse.from_result(result)

    @router.patch(
        "/citations",
        response_model=JobDescriptionResponse,
        operation_id="jd_change_citations",
        summary="原子新增、移除或確認同一目標的引用",
    )
    def write_citations(
        workspace_id: HttpId,
        job_description_id: HttpId,
        body: ChangeCitationsRequest,
        request: Request,
    ) -> JobDescriptionResponse:
        result = change_citations(
            workspace_id=workspace_id,
            input=ChangeCitationsInput(
                job_description_id=job_description_id,
                expected_version=body.expected_version,
                target_kind=body.target_kind,
                target_id=body.target_id,
                changes=tuple(change.to_application() for change in body.changes),
                correlation_id=body.correlation_id,
            ),
            uow_factory=uow_factory,
        )
        return write_response(request, result)

    return router
