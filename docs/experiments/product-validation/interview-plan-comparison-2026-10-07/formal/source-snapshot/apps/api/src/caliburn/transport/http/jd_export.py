"""Download the fixed formal JD, even when a Turn has an uncommitted preview."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from caliburn.adapters.pdf_renderer import PdfRenderError
from caliburn.features.job_files.models import JobFileNotFoundError
from caliburn.workflows.jd_export import JdExportWorkflow

router = APIRouter(prefix="/api/job-files/{job_file_id}/jd", tags=["job-description"])


def get_jd_export_workflow(request: Request) -> JdExportWorkflow:
    workflow = getattr(request.app.state, "jd_export_workflow", None)
    if not isinstance(workflow, JdExportWorkflow):
        raise HTTPException(status_code=503, detail={"code": "pdf_export_unavailable"})
    return workflow


@router.get(
    "/export.pdf", response_class=Response, responses={200: {"content": {"application/pdf": {}}}}
)
async def export_jd_pdf(
    job_file_id: UUID,
    workflow: Annotated[JdExportWorkflow, Depends(get_jd_export_workflow)],
) -> Response:
    try:
        content = await workflow.export_current(job_file_id)
    except JobFileNotFoundError as error:
        raise HTTPException(status_code=404, detail={"code": "job_file_not_found"}) from error
    except PdfRenderError as error:
        code = str(error)
        if code not in {"pdf_renderer_busy", "pdf_render_timeout", "pdf_font_unavailable"}:
            code = "pdf_render_failed"
        raise HTTPException(
            status_code=504 if code == "pdf_render_timeout" else 503, detail={"code": code}
        ) from error
    return Response(
        content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": 'attachment; filename="job-description.pdf"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
