"""公版 XLSX download route."""

from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, Response

from app.adapters.xlsx import XLSX_MEDIA_TYPE, render_xlsx
from app.api.deps import get_job_analysis_uow_factory
from app.api.problems import DOCUMENT_NOT_FOUND, problem_response
from app.core.persistence import JobAnalysisUnitOfWorkFactory
from app.documents import load_document
from app.export import assemble_export_document


router = APIRouter(prefix="/job-analysis/documents", tags=["job-analysis"])


def _export_filename(title: str) -> str:
    safe_title = "".join(
        "_"
        if character in '<>:/\\|?*\"\r\n'
        else character
        for character in title.strip()
    ).rstrip(" .") or "職務說明書"
    return f"{safe_title}.xlsx"


@router.get("/{document_id}/export")
async def export_document_route(
    document_id: UUID,
    uow_factory: JobAnalysisUnitOfWorkFactory = Depends(
        get_job_analysis_uow_factory
    ),
):
    loaded = await load_document(uow_factory, document_id)
    if loaded is None:
        return problem_response(
            type_uri=DOCUMENT_NOT_FOUND,
            title="Document not found",
            status=404,
        )

    export_document = assemble_export_document(
        loaded.state,
        title=loaded.document.title,
    )
    filename = _export_filename(loaded.document.title)
    return Response(
        content=render_xlsx(export_document),
        media_type=XLSX_MEDIA_TYPE,
        headers={
            "Content-Disposition": (
                'attachment; filename="job-description.xlsx"; '
                f"filename*=UTF-8''{quote(filename, safe='')}"
            )
        },
    )
