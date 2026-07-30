"""RFC 9457 responses scoped to the greenfield job-analysis API."""

from collections.abc import Sequence

from fastapi.responses import JSONResponse
from job_analysis_contract import ProblemDetail, ProblemFieldError


DOCUMENT_NOT_FOUND = (
    "https://caliburn.dev/problems/job-analysis/document-not-found"
)
TASK_NOT_FOUND = "https://caliburn.dev/problems/job-analysis/task-not-found"
IDEMPOTENCY_CONFLICT = (
    "https://caliburn.dev/problems/job-analysis/idempotency-conflict"
)
AUTHORITY_CONFLICT = (
    "https://caliburn.dev/problems/job-analysis/authority-conflict"
)
INVALID_TASK_ORDER = (
    "https://caliburn.dev/problems/job-analysis/invalid-task-order"
)
INVALID_REQUEST = "https://caliburn.dev/problems/job-analysis/invalid-request"


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
