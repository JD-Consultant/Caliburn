"""HTTP read failures; never creates or changes a mutation observation."""

from http import HTTPStatus
from uuid import UUID
from .generated.query_http import QueryProblem
from .http_results import HttpResult
from .read_transport import read_failure


def query_problem(code: str, *, request_id: UUID) -> HttpResult:
    if not isinstance(request_id, UUID):
        raise ValueError("invalid_http_context")
    failure = read_failure(code if isinstance(code, str) else "read_failed")
    status = {
        "invalid_input": 422,
        "invalid_ref": 422,
        "stale_view": 409,
        "target_missing": 404,
        "read_failed": 500,
    }[failure["code"]]
    problem = QueryProblem(
        type="about:blank",
        title=HTTPStatus(status).phrase,
        status=status,
        detail=failure["message"],
        instance=f"urn:uuid:{request_id}",
        jd_read_error=failure,
    ).model_dump(mode="json")
    return HttpResult(
        status,
        "application/problem+json",
        problem,
        {"Cache-Control": "no-store", "X-Request-ID": str(request_id)},
    )
