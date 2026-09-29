"""Safe provider failure classification, not authorization to retry or a billing verdict."""

from dataclasses import dataclass
from enum import StrEnum

from openai import APIConnectionError, APIError, APIResponseValidationError, APIStatusError


class ResponseFailureKind(StrEnum):
    REMOTE_RESULT_UNKNOWN = "remote_result_unknown"
    TRANSIENT_SERVICE = "transient_service"
    ACCESS_BLOCKED = "access_blocked"
    CAPACITY_EXCEEDED = "capacity_exceeded"
    REQUEST_REJECTED = "request_rejected"
    RESPONSE_PROTOCOL = "response_protocol"


@dataclass(frozen=True, slots=True)
class ResponseFailure:
    kind: ResponseFailureKind
    status_code: int | None = None


def classify_response_failure(error: APIError) -> ResponseFailure:
    """Never copy exception text/body, which may contain input or credentials, into State/UI.

    Transient only describes the cause. A subsequent request still requires original-result
    reconciliation, Retry-After handling and fresh admission against the original work budget.
    None of these outcomes establishes that the failed request was free.
    """
    if isinstance(error, APIConnectionError):
        return ResponseFailure(ResponseFailureKind.REMOTE_RESULT_UNKNOWN)
    if isinstance(error, APIResponseValidationError):
        return ResponseFailure(ResponseFailureKind.RESPONSE_PROTOCOL, error.status_code)
    if not isinstance(error, APIStatusError):
        return ResponseFailure(ResponseFailureKind.RESPONSE_PROTOCOL)
    if (
        error.status_code in (401, 403)
        or error.code
        in {
            "credit_balance_exhausted",
            "organization_spend_limit_exceeded",
            "project_spend_limit_exceeded",
            "organization_usage_limit_exceeded",
            "insufficient_quota",
        }
        or error.type == "insufficient_quota"
    ):
        kind = ResponseFailureKind.ACCESS_BLOCKED
    elif error.code == "context_length_exceeded":
        kind = ResponseFailureKind.CAPACITY_EXCEEDED
    elif error.response.headers.get("x-should-retry") == "false":
        kind = ResponseFailureKind.REQUEST_REJECTED
    elif error.status_code in (408, 409, 429) or error.status_code >= 500:
        kind = ResponseFailureKind.TRANSIENT_SERVICE
    else:
        kind = ResponseFailureKind.REQUEST_REJECTED
    return ResponseFailure(kind, error.status_code)
