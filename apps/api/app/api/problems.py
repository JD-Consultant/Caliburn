"""RFC 9457 responses for the durable consultant API."""

from collections.abc import Sequence

from fastapi.responses import JSONResponse
from job_analysis_contract import ProblemDetail, ProblemFieldError

from app.adapters.langgraph.postgres import (
    ActiveConsultantRun,
    ConsultantPersistenceError,
    DocumentNotFound,
    IdempotencyConflict,
    PendingSourceRequiresReconciliation,
    QuoteAnchorMismatch,
    SourceConflict,
    StaleRevision,
    UnknownEvidenceSource,
)
from app.consultant.views import CurrentDocumentUnavailable


DOCUMENT_NOT_FOUND = "https://caliburn.dev/problems/job-analysis/document-not-found"
IDEMPOTENCY_CONFLICT = "https://caliburn.dev/problems/job-analysis/idempotency-conflict"
AUTHORITY_CONFLICT = "https://caliburn.dev/problems/job-analysis/authority-conflict"
INVALID_REQUEST = "https://caliburn.dev/problems/job-analysis/invalid-request"
CONSULTANT_UNAVAILABLE = "https://caliburn.dev/problems/job-analysis/consultant-unavailable"
CONSULTANT_RUN_ACTIVE = "https://caliburn.dev/problems/job-analysis/consultant-run-active"
CONSULTANT_COMMAND_CONFLICT = "https://caliburn.dev/problems/job-analysis/consultant-command-conflict"
EXPORT_CONFIRMATION_REQUIRED = "https://caliburn.dev/problems/job-analysis/export-confirmation-required"


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


def consultant_unavailable_response() -> JSONResponse:
    return problem_response(
        type_uri=CONSULTANT_UNAVAILABLE,
        title="Consultant temporarily unavailable",
        status=503,
    )


def consultant_runtime_error_response(error: Exception) -> JSONResponse:
    """Map runtime failures without exposing evidence or provider payloads."""

    if isinstance(error, DocumentNotFound):
        return problem_response(
            type_uri=DOCUMENT_NOT_FOUND,
            title="Document not found",
            status=404,
        )
    if isinstance(error, ActiveConsultantRun):
        return problem_response(
            type_uri=CONSULTANT_RUN_ACTIVE,
            title="Another consultant run must be recovered first",
            status=409,
        )
    if isinstance(error, (IdempotencyConflict, SourceConflict)):
        return problem_response(
            type_uri=IDEMPOTENCY_CONFLICT,
            title="Idempotency conflict",
            status=409,
        )
    if isinstance(error, StaleRevision):
        return problem_response(
            type_uri=AUTHORITY_CONFLICT,
            title="Document revision changed",
            status=409,
        )
    if isinstance(error, CurrentDocumentUnavailable):
        return problem_response(
            type_uri=AUTHORITY_CONFLICT,
            title="Current document requires workspace reconciliation",
            status=409,
        )
    if isinstance(error, PendingSourceRequiresReconciliation):
        return problem_response(
            type_uri=CONSULTANT_RUN_ACTIVE,
            title="A saved employee input must be recovered first",
            status=409,
        )
    if isinstance(error, (QuoteAnchorMismatch, UnknownEvidenceSource, ValueError)):
        return problem_response(
            type_uri=INVALID_REQUEST,
            title="Invalid request",
            status=422,
        )
    if isinstance(error, KeyError):
        return problem_response(
            type_uri=CONSULTANT_COMMAND_CONFLICT,
            title="The requested decision is no longer available",
            status=409,
        )
    if isinstance(error, ConsultantPersistenceError):
        return problem_response(
            type_uri=CONSULTANT_COMMAND_CONFLICT,
            title="Consultant command conflict",
            status=409,
        )
    raise TypeError(f"unmapped consultant runtime error: {type(error).__name__}")
