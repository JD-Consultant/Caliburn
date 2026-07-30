"""Local Web document library and Current JD transport routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, Response
from job_analysis_contract import (
    DocumentMetadataView,
    DocumentMetadataWrite,
    DocumentSummary,
    DocumentView,
    ProblemFieldError,
)

from app.api.deps import get_job_analysis_uow_factory
from app.api.job_analysis_mapper import (
    to_document_metadata_view,
    to_document_summary,
    to_document_view,
)
from app.api.job_analysis_problems import (
    DOCUMENT_NOT_FOUND,
    INVALID_REQUEST,
    problem_response,
)
from app.job_analysis.application import (
    JobAnalysisUnitOfWorkFactory,
    list_documents,
    load_document,
    put_document_metadata,
)


router = APIRouter(prefix="/job-analysis/documents", tags=["job-analysis"])


@router.get("", response_model=list[DocumentSummary])
async def get_documents(
    uow_factory: JobAnalysisUnitOfWorkFactory = Depends(
        get_job_analysis_uow_factory
    ),
):
    summaries = await list_documents(uow_factory)
    return [to_document_summary(summary) for summary in summaries]


@router.put("/{document_id}", response_model=DocumentMetadataView)
async def put_document(
    document_id: UUID,
    body: DocumentMetadataWrite,
    response: Response,
    uow_factory: JobAnalysisUnitOfWorkFactory = Depends(
        get_job_analysis_uow_factory
    ),
):
    title = body.title.strip()
    if not title:
        return problem_response(
            type_uri=INVALID_REQUEST,
            title="Invalid request",
            status=422,
            detail="Document title cannot be blank.",
            errors=[
                ProblemFieldError(
                    field="title",
                    message="Document title cannot be blank.",
                )
            ],
        )
    result = await put_document_metadata(
        uow_factory,
        document_id=document_id,
        title=title,
    )
    response.status_code = 201 if result.created else 200
    return to_document_metadata_view(result.document)


@router.get("/{document_id}", response_model=DocumentView)
async def get_document(
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
    return to_document_view(loaded)
