"""HTTP projection of the same result, without executing or retrying a write."""

from dataclasses import dataclass
from http import HTTPStatus
from typing import Literal
from uuid import UUID

from .result_transport import validate_result


@dataclass(frozen=True)
class HttpResult:
    status_code: int
    media_type: str
    body: dict
    headers: dict[str, str]


_WRITE_STATUS = {"invalid_input": 422, "target_missing": 404, "stale_view": 409,
                 "relationship_conflict": 409, "dependent_items": 409,
                 "operation_conflict": 409, "busy": 409, "archived": 409,
                 "save_failed": 500}


def project_result(result: dict, *, request_id: UUID, context: Literal["write", "lookup"] = "write") -> HttpResult:
    """Lookup means this request successfully obtained an observation.

    Failure to read a receipt at all is a host/port error, not a found receipt.
    It must not be used to rewrite the original write's status or replay it.
    """
    if not isinstance(request_id, UUID) or context not in {"write", "lookup"}:
        raise ValueError("invalid_http_context")
    value = validate_result(result)
    headers = {"Cache-Control": "no-store"}
    if context == "lookup" or value["error"] is None:
        return HttpResult(200, "application/json", value, headers)
    if value["next_action"] == "reconcile_operation":
        # An admitted write has an unresolved receipt. 202 is not a success
        # receipt, nor an instruction to submit a new write or to rebind it.
        return HttpResult(202, "application/json", value, headers)
    status = _WRITE_STATUS[value["status"]]
    problem = {"type": "about:blank", "title": HTTPStatus(status).phrase,
               "status": status, "detail": value["error"]["message"],
               "instance": f"urn:uuid:{request_id}", "jd_result": value}
    return HttpResult(status, "application/problem+json", problem, headers)
