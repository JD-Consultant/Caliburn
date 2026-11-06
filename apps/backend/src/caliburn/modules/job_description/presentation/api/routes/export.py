"""正式 JD PDF 下載；可停用列印資源，查讀與內容 API 仍獨立存在。"""

from fastapi import APIRouter, HTTPException, Response

from caliburn.modules.job_description.application.exporting import (
    HtmlPdfRenderer,
    PdfRenderError,
    export_job_description,
)
from caliburn.modules.job_description.application.queries import JobDescriptionQueries
from caliburn.modules.job_description.presentation.api.errors import (
    ERROR_RESPONSES,
    JobDescriptionRoute,
)
from caliburn.shared.presentation.api.values import HttpId


def build_export_router(
    *, queries: JobDescriptionQueries, renderer: HtmlPdfRenderer | None = None
) -> APIRouter:
    router = APIRouter(
        tags=["JD"], route_class=JobDescriptionRoute, responses=ERROR_RESPONSES
    )

    @router.get(
        "/workspaces/{workspace_id}/job-descriptions/{job_description_id}/export.pdf",
        response_class=Response,
        responses={
            200: {
                "content": {
                    "application/pdf": {
                        "schema": {"type": "string", "format": "binary"}
                    }
                }
            },
            503: {"description": "PDF 未設定、忙碌或無法列印"},
            504: {"description": "PDF 列印逾時"},
        },
        operation_id="export_job_description_pdf",
        summary="下載完整 JD PDF",
    )
    async def export_pdf(workspace_id: HttpId, job_description_id: HttpId) -> Response:
        if renderer is None:
            raise HTTPException(
                status_code=503, detail={"code": "pdf_export_unavailable"}
            )
        try:
            result = await export_job_description(
                workspace_id=workspace_id,
                job_description_id=job_description_id,
                queries=queries,
                renderer=renderer,
            )
        except PdfRenderError as error:
            raise HTTPException(
                status_code=504 if error.code == "pdf_render_timeout" else 503,
                detail={"code": error.code},
            ) from error
        return Response(
            result,
            media_type="application/pdf",
            headers={
                "Content-Disposition": 'attachment; filename="job-description.pdf"',
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
            },
        )

    return router
