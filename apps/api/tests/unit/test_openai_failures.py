"""Transient classification never overrides a known billing/capacity block."""

import httpx2
import pytest
from openai import (
    APIConnectionError,
    APIError,
    APIResponseValidationError,
    APIStatusError,
    APITimeoutError,
)

from caliburn.adapters.openai_failures import ResponseFailureKind, classify_response_failure


@pytest.mark.parametrize(
    ("status", "code", "error_type", "retry_header", "expected"),
    [
        (429, "credit_balance_exhausted", None, "true", ResponseFailureKind.ACCESS_BLOCKED),
        (429, "project_spend_limit_exceeded", None, None, ResponseFailureKind.ACCESS_BLOCKED),
        (429, "new_quota_code", "insufficient_quota", None, ResponseFailureKind.ACCESS_BLOCKED),
        (401, None, None, "true", ResponseFailureKind.ACCESS_BLOCKED),
        (403, None, None, None, ResponseFailureKind.ACCESS_BLOCKED),
        (400, "context_length_exceeded", None, "true", ResponseFailureKind.CAPACITY_EXCEEDED),
        # A rate limit is the provider asking us to wait, not a service fault.
        (429, "slow_down", "rate_limit_error", None, ResponseFailureKind.RATE_LIMITED),
        (429, "rate_limit_exceeded", "tokens", None, ResponseFailureKind.RATE_LIMITED),
        (429, None, None, None, ResponseFailureKind.RATE_LIMITED),
        (429, "rate_limit_exceeded", "tokens", "false", ResponseFailureKind.REQUEST_REJECTED),
        (503, "server_is_overloaded", None, None, ResponseFailureKind.TRANSIENT_SERVICE),
        (503, None, None, "false", ResponseFailureKind.REQUEST_REJECTED),
        (400, None, None, "true", ResponseFailureKind.REQUEST_REJECTED),
    ],
)
def test_known_block_wins_over_generic_retry_signal(
    status, code, error_type, retry_header, expected
) -> None:
    response = httpx2.Response(
        status,
        headers={"x-should-retry": retry_header} if retry_header is not None else {},
        request=httpx2.Request("POST", "https://api.openai.com/v1/responses"),
    )
    error = APIStatusError(
        "SENSITIVE MUST NOT BE PROJECTED",
        response=response,
        body={"code": code, "type": error_type, "message": "SENSITIVE MUST NOT BE PROJECTED"},
    )
    failure = classify_response_failure(error)
    assert failure.kind == expected
    assert failure.status_code == status
    assert "SENSITIVE" not in repr(failure)


def test_lost_transport_is_unknown_not_a_known_unexecuted_or_free_request() -> None:
    request = httpx2.Request("POST", "https://api.openai.com/v1/responses")
    for error in (APIConnectionError(request=request), APITimeoutError(request=request)):
        failure = classify_response_failure(error)
        assert failure.kind == ResponseFailureKind.REMOTE_RESULT_UNKNOWN
        assert failure.status_code is None
    invalid = APIResponseValidationError(httpx2.Response(200, request=request), {"raw": "private"})
    assert classify_response_failure(invalid).kind == ResponseFailureKind.RESPONSE_PROTOCOL


@pytest.mark.parametrize(
    ("code", "error_type", "expected"),
    [
        # Observed live: a tokens-per-minute limit arrives as an event inside an open stream.
        ("rate_limit_exceeded", "tokens", ResponseFailureKind.RATE_LIMITED),
        ("rate_limit_exceeded", "requests", ResponseFailureKind.RATE_LIMITED),
        ("slow_down", "rate_limit_error", ResponseFailureKind.RATE_LIMITED),
        ("server_error", "server_error", ResponseFailureKind.TRANSIENT_SERVICE),
        ("server_is_overloaded", None, ResponseFailureKind.TRANSIENT_SERVICE),
        # A known block or capacity signal still wins, exactly as for an HTTP status error.
        ("insufficient_quota", "insufficient_quota", ResponseFailureKind.ACCESS_BLOCKED),
        ("credit_balance_exhausted", None, ResponseFailureKind.ACCESS_BLOCKED),
        ("new_quota_code", "insufficient_quota", ResponseFailureKind.ACCESS_BLOCKED),
        ("context_length_exceeded", None, ResponseFailureKind.CAPACITY_EXCEEDED),
        # Unknown or missing detail stays a terminal protocol failure: never guess retryable.
        ("invalid_prompt", "invalid_request_error", ResponseFailureKind.RESPONSE_PROTOCOL),
        (None, None, ResponseFailureKind.RESPONSE_PROTOCOL),
    ],
)
def test_error_event_inside_a_stream_is_classified_by_its_code(code, error_type, expected) -> None:
    request = httpx2.Request("POST", "https://api.openai.com/v1/responses")
    error = APIError(
        "SENSITIVE MUST NOT BE PROJECTED",
        request,
        body={"code": code, "type": error_type, "message": "SENSITIVE MUST NOT BE PROJECTED"},
    )
    failure = classify_response_failure(error)
    assert failure.kind == expected
    assert failure.status_code is None
    assert "SENSITIVE" not in repr(failure)


@pytest.mark.parametrize("body", [None, "not a mapping", ["rate_limit_exceeded"]])
def test_stream_error_without_a_readable_code_is_never_retryable(body) -> None:
    request = httpx2.Request("POST", "https://api.openai.com/v1/responses")
    failure = classify_response_failure(APIError("SENSITIVE", request, body=body))
    assert failure.kind == ResponseFailureKind.RESPONSE_PROTOCOL


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("rate_limit_exceeded", "rate_limit_exceeded"),
        ("server_is_overloaded", "server_is_overloaded"),
        ("credit_balance_exhausted", "credit_balance_exhausted"),
        ("context_length_exceeded", "context_length_exceeded"),
        ("private employee text echoed as code", None),
        (None, None),
    ],
)
def test_diagnostic_code_preserves_known_cause_without_echoing_provider_data(
    code, expected
) -> None:
    error = APIError(
        "private input and credential",
        httpx2.Request("POST", "https://api.openai.com/v1/responses"),
        body={"code": code, "message": "private input and credential"},
    )
    failure = classify_response_failure(error)
    assert failure.provider_code == expected
    assert "private" not in repr(failure)
