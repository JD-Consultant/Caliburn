"""Read-only human evidence routes; no model execution, publication or confirmation."""

from dataclasses import asdict
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response

from caliburn.contracts.generated.jd_source_changes_view import JdSourceChangesView
from caliburn.contracts.generated.jd_source_content_view import JdSourceContentView
from caliburn.contracts.generated.jd_sources_view import JdSourcesView
from caliburn.features.interviews.models import InterviewReadError
from caliburn.features.job_files.models import JobFileNotFoundError
from caliburn.features.work_memory.revisions import MemoryRevisionNotFoundError
from caliburn.transport.jd_source_markdown import (
    project_jd_source_changes,
    project_jd_target_changes,
)
from caliburn.workflows.jd_evidence import (
    JdEvidenceComparisonError,
    JdEvidenceNotFoundError,
    JdEvidenceStaleError,
    JdEvidenceWorkflow,
    MemoryEvidence,
)

router = APIRouter(prefix="/api/job-files/{job_file_id}/jd/sources", tags=["job-description"])


def get_evidence_workflow(request: Request, response: Response) -> JdEvidenceWorkflow:
    response.headers["Cache-Control"] = "no-store"
    workflow = request.app.state.jd_evidence_workflow
    if not isinstance(workflow, JdEvidenceWorkflow):
        raise HTTPException(status_code=503, detail={"code": "database_not_configured"})
    return workflow


EvidenceWorkflow = Annotated[JdEvidenceWorkflow, Depends(get_evidence_workflow)]
READ_ERRORS = (
    JobFileNotFoundError,
    JdEvidenceNotFoundError,
    JdEvidenceStaleError,
    JdEvidenceComparisonError,
    MemoryRevisionNotFoundError,
    InterviewReadError,
)


def _read_error(error: Exception) -> HTTPException:
    if isinstance(error, JobFileNotFoundError):
        return HTTPException(status_code=404, detail={"code": "job_file_not_found"})
    if isinstance(error, JdEvidenceNotFoundError):
        return HTTPException(status_code=404, detail={"code": "source_not_found"})
    if isinstance(error, JdEvidenceStaleError):
        return HTTPException(status_code=409, detail={"code": "jd_source_view_stale"})
    if isinstance(error, JdEvidenceComparisonError):
        return HTTPException(status_code=503, detail={"code": "jd_review_baseline_not_available"})
    return HTTPException(status_code=503, detail={"code": "source_not_available"})


@router.get("", response_model=JdSourcesView)
async def read_sources(job_file_id: UUID, workflow: EvidenceWorkflow) -> JdSourcesView:
    try:
        result = await workflow.read_overview(job_file_id)
    except READ_ERRORS as error:
        raise _read_error(error) from error
    return JdSourcesView.model_validate(asdict(result))


@router.get("/{citation_id}", response_model=JdSourceContentView)
async def read_source_content(
    job_file_id: UUID,
    citation_id: UUID,
    revision_id: UUID,
    workflow: EvidenceWorkflow,
    source_ref: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
) -> JdSourceContentView:
    try:
        result = await workflow.read_content(job_file_id, revision_id, citation_id, source_ref)
    except READ_ERRORS as error:
        raise _read_error(error) from error
    if isinstance(result, MemoryEvidence):
        content = {
            "kind": result.revision.layer.value,
            **asdict(result.revision.content),
            "references": [asdict(link) for link in result.references],
        }
    else:
        content = {
            "kind": "interview",
            "interview_sequence": result.interview_sequence,
            "speaker": result.speaker.value,
            "interview_text": result.interview_text,
        }
    return JdSourceContentView.model_validate(
        {"revision_id": revision_id, "citation_id": citation_id, "content": content}
    )


@router.get("/{citation_id}/changes", response_model=JdSourceChangesView)
async def read_source_changes(
    job_file_id: UUID,
    citation_id: UUID,
    revision_id: UUID,
    workflow: EvidenceWorkflow,
) -> JdSourceChangesView:
    try:
        result = await workflow.read_changes(job_file_id, revision_id, citation_id)
    except READ_ERRORS as error:
        raise _read_error(error) from error
    return JdSourceChangesView(
        revision_id=revision_id,
        citation_id=citation_id,
        jd_markdown=project_jd_target_changes(result),
        source_markdown=(
            project_jd_source_changes(
                result.source_changes, comparison_label="本次讀取時的最新已發布 Memory"
            )
            if result.source_changes is not None
            else None
        ),
    )
