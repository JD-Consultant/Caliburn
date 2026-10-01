"""Safe provider failure classification, not authorization to retry or a billing verdict."""

from dataclasses import dataclass
from enum import StrEnum

from openai import APIConnectionError, APIError, APIResponseValidationError, APIStatusError

_BLOCKED_CODES = frozenset(
    {
        "credit_balance_exhausted",
        "organization_spend_limit_exceeded",
        "project_spend_limit_exceeded",
        "organization_usage_limit_exceeded",
        "insufficient_quota",
    }
)
# An error event inside an open HTTP 200 stream has no status, so only its code can say that
# it is a provider hiccup or a rate limit. Anything not named here stays a terminal failure.
_RATE_LIMIT_CODES = frozenset({"rate_limit_exceeded", "slow_down"})
_TRANSIENT_STREAM_CODES = frozenset({"server_error", "server_is_overloaded", "service_unavailable"})
_DIAGNOSTIC_CODES = (
    _BLOCKED_CODES
    | _RATE_LIMIT_CODES
    | _TRANSIENT_STREAM_CODES
    | {
        "context_length_exceeded",
        "invalid_api_key",
    }
)


class ResponseFailureKind(StrEnum):
    REMOTE_RESULT_UNKNOWN = "remote_result_unknown"
    TRANSIENT_SERVICE = "transient_service"
    # The provider asking us to slow down is waiting, not a fault of the work; see the retry policy.
    RATE_LIMITED = "rate_limited"
    ACCESS_BLOCKED = "access_blocked"
    CAPACITY_EXCEEDED = "capacity_exceeded"
    REQUEST_REJECTED = "request_rejected"
    RESPONSE_PROTOCOL = "response_protocol"


@dataclass(frozen=True, slots=True)
class ResponseFailure:
    kind: ResponseFailureKind
    status_code: int | None = None
    provider_code: str | None = None


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
    status = error.status_code if isinstance(error, APIStatusError) else None
    if status in (401, 403) or error.code in _BLOCKED_CODES or error.type == "insufficient_quota":
        kind = ResponseFailureKind.ACCESS_BLOCKED
    elif error.code == "context_length_exceeded":
        kind = ResponseFailureKind.CAPACITY_EXCEEDED
    elif not isinstance(error, APIStatusError):
        if error.code in _RATE_LIMIT_CODES:
            kind = ResponseFailureKind.RATE_LIMITED
        elif error.code in _TRANSIENT_STREAM_CODES:
            kind = ResponseFailureKind.TRANSIENT_SERVICE
        else:
            kind = ResponseFailureKind.RESPONSE_PROTOCOL
    elif error.response.headers.get("x-should-retry") == "false":
        kind = ResponseFailureKind.REQUEST_REJECTED
    elif error.status_code == 429:
        kind = ResponseFailureKind.RATE_LIMITED
    elif error.status_code in (408, 409) or error.status_code >= 500:
        kind = ResponseFailureKind.TRANSIENT_SERVICE
    else:
        kind = ResponseFailureKind.REQUEST_REJECTED
    # Codes are external strings too. Retain only known constants, never an echoed payload.
    provider_code = error.code if error.code in _DIAGNOSTIC_CODES else None
    return ResponseFailure(kind, status, provider_code)
