"""RFC 9457 responses scoped to the greenfield job-analysis API."""

from collections.abc import Sequence

from fastapi.responses import JSONResponse
from job_analysis_contract import ProblemDetail, ProblemFieldError
from pydantic import ValidationError

from app.job_analysis.application import (
    ConcurrentAuthorityChange,
    DocumentNotFound,
    DutyNotChanged,
    DutyNotFound,
    IdempotencyConflict,
    InvalidDutyOrder,
    InvalidJdTaskOrder,
    InvalidOpksOrder,
    InvalidProposalDecision,
    JdHeaderNotChanged,
    JdTaskNotFound,
    OpksItemNotFound,
    OpksProposalNotDecidable,
    OpksProposalNotFound,
    ProposalNotDecidable,
    ProposalNotFound,
)
from app.job_analysis.application.errors import JobAnalysisApplicationError


DOCUMENT_NOT_FOUND = (
    "https://caliburn.dev/problems/job-analysis/document-not-found"
)
TASK_NOT_FOUND = "https://caliburn.dev/problems/job-analysis/task-not-found"
DUTY_NOT_FOUND = "https://caliburn.dev/problems/job-analysis/duty-not-found"
OPKS_ITEM_NOT_FOUND = (
    "https://caliburn.dev/problems/job-analysis/opks-item-not-found"
)
IDEMPOTENCY_CONFLICT = (
    "https://caliburn.dev/problems/job-analysis/idempotency-conflict"
)
AUTHORITY_CONFLICT = (
    "https://caliburn.dev/problems/job-analysis/authority-conflict"
)
INVALID_TASK_ORDER = (
    "https://caliburn.dev/problems/job-analysis/invalid-task-order"
)
INVALID_DUTY_ORDER = (
    "https://caliburn.dev/problems/job-analysis/invalid-duty-order"
)
INVALID_OPKS_ORDER = (
    "https://caliburn.dev/problems/job-analysis/invalid-opks-order"
)
INVALID_REQUEST = "https://caliburn.dev/problems/job-analysis/invalid-request"
PROPOSAL_NOT_FOUND = (
    "https://caliburn.dev/problems/job-analysis/proposal-not-found"
)
CONSULTANT_UNAVAILABLE = (
    "https://caliburn.dev/problems/job-analysis/consultant-unavailable"
)


def problem_response(
    *,
    type_uri: str,
    title: str,
    status: int,
    detail: str | None = None,
    errors: Sequence[ProblemFieldError] | None = None,
) -> JSONResponse:
    problem = ProblemDetail.model_validate(
        {
            "type": type_uri,
            "title": title,
            "status": status,
            "detail": detail,
            "errors": list(errors) if errors is not None else None,
        }
    )
    return JSONResponse(
        status_code=status,
        content=problem.model_dump(mode="json", exclude_none=True),
        media_type="application/problem+json",
    )


def application_error_response(
    error: JobAnalysisApplicationError,
) -> JSONResponse:
    if isinstance(error, DocumentNotFound):
        return problem_response(
            type_uri=DOCUMENT_NOT_FOUND,
            title="Document not found",
            status=404,
        )
    if isinstance(error, JdTaskNotFound):
        return problem_response(
            type_uri=TASK_NOT_FOUND,
            title="Task not found",
            status=404,
        )
    if isinstance(error, DutyNotFound):
        return problem_response(
            type_uri=DUTY_NOT_FOUND,
            title="Duty not found",
            status=404,
        )
    if isinstance(error, OpksItemNotFound):
        return problem_response(
            type_uri=OPKS_ITEM_NOT_FOUND,
            title="OPKS item not found",
            status=404,
        )
    if isinstance(error, (ProposalNotFound, OpksProposalNotFound)):
        return problem_response(
            type_uri=PROPOSAL_NOT_FOUND,
            title="Proposal not found",
            status=404,
        )
    if isinstance(error, IdempotencyConflict):
        return problem_response(
            type_uri=IDEMPOTENCY_CONFLICT,
            title="Idempotency conflict",
            status=409,
        )
    if isinstance(error, ConcurrentAuthorityChange):
        return problem_response(
            type_uri=AUTHORITY_CONFLICT,
            title="Authority conflict",
            status=409,
        )
    if isinstance(error, (ProposalNotDecidable, OpksProposalNotDecidable)):
        return problem_response(
            type_uri=AUTHORITY_CONFLICT,
            title="Proposal is no longer decidable",
            status=409,
        )
    if isinstance(error, InvalidJdTaskOrder):
        return problem_response(
            type_uri=INVALID_TASK_ORDER,
            title="Invalid Task order",
            status=422,
        )
    if isinstance(error, InvalidDutyOrder):
        return problem_response(
            type_uri=INVALID_DUTY_ORDER,
            title="Invalid Duty order",
            status=422,
        )
    if isinstance(error, InvalidOpksOrder):
        return problem_response(
            type_uri=INVALID_OPKS_ORDER,
            title="Invalid OPKS order",
            status=422,
        )
    if isinstance(error, InvalidProposalDecision):
        return problem_response(
            type_uri=INVALID_REQUEST,
            title="Invalid proposal decision",
            status=422,
        )
    if isinstance(error, JdHeaderNotChanged):
        return problem_response(
            type_uri=INVALID_REQUEST,
            title="Invalid request",
            status=422,
            detail="JD header edit must change at least one field.",
        )
    if isinstance(error, DutyNotChanged):
        return problem_response(
            type_uri=INVALID_REQUEST,
            title="Invalid request",
            status=422,
            detail="Duty edit must change the statement.",
        )
    raise TypeError(f"unmapped job-analysis error: {type(error).__name__}")


def consultant_unavailable_response() -> JSONResponse:
    return problem_response(
        type_uri=CONSULTANT_UNAVAILABLE,
        title="Consultant temporarily unavailable",
        status=503,
    )


def domain_validation_error_response(error: ValidationError) -> JSONResponse:
    return problem_response(
        type_uri=INVALID_REQUEST,
        title="Invalid request",
        status=422,
        errors=[
            ProblemFieldError(
                field=".".join(str(part) for part in item["loc"]),
                message=item["msg"],
            )
            for item in error.errors()
        ],
    )
