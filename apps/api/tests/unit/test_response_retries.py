"""Server delays are lower bounds, not hints that local backoff may shorten."""

from datetime import UTC, datetime

import httpx2
import pytest
from openai import APIStatusError, APITimeoutError

from caliburn.agent_execution.response_retries import ResponseRetryPolicy
from caliburn.settings import ModelSettings


def failure(headers, *, status=429, code="rate_limit_exceeded"):
    return APIStatusError(
        "synthetic sensitive body",
        body={"code": code},
        response=httpx2.Response(
            status,
            headers=headers,
            request=httpx2.Request("POST", "https://api.openai.com/v1/responses"),
        ),
    )


@pytest.mark.parametrize(
    ("headers", "expected"),
    [
        ({"retry-after": "125"}, 125.0),
        ({"retry-after": "0"}, 0.0),
        ({"retry-after": "5.5"}, 5.5),
        ({"retry-after-ms": "1250", "retry-after": "5"}, 1.25),
        ({"retry-after": "Wed, 30 Sep 2026 00:02:00 GMT"}, 120.0),
        ({"retry-after": "Tue, 29 Sep 2026 00:00:00 GMT"}, 0.0),
        ({"retry-after": "not a date"}, 3.0),
        ({"retry-after": "-2"}, 3.0),
        ({"retry-after": "1e999"}, None),
        ({"retry-after": "nan"}, None),
    ],
)
def test_provider_delay_is_honored_or_stopped_never_shortened(headers, expected):
    assert (
        ResponseRetryPolicy().delay_seconds(
            failure(headers),
            attempt_number=2,
            now=datetime(2026, 9, 30, tzinfo=UTC),
            random_fraction=1,
        )
        == expected
    )


def test_transport_retry_uses_capped_jitter_without_claiming_original_result():
    error = APITimeoutError(request=httpx2.Request("POST", "https://api.openai.com/v1/responses"))
    assert (
        ResponseRetryPolicy().delay_seconds(
            error,
            attempt_number=10000,
            now=datetime.now(UTC),
            random_fraction=0.5,
        )
        == 26.25
    )


@pytest.mark.parametrize(
    ("status", "code", "headers"),
    [
        (429, "insufficient_quota", {"retry-after": "0", "x-should-retry": "true"}),
        (401, "invalid_api_key", {"retry-after": "0"}),
        (400, "context_length_exceeded", {"retry-after": "0"}),
        (400, "invalid_request", {"retry-after": "0"}),
        (503, "server_is_overloaded", {"x-should-retry": "false"}),
    ],
)
def test_permanent_or_explicitly_refused_request_cannot_be_made_retryable(status, code, headers):
    assert (
        ResponseRetryPolicy().delay_seconds(
            failure(headers, status=status, code=code),
            attempt_number=1,
            now=datetime.now(UTC),
            random_fraction=0,
        )
        is None
    )


def test_default_schedule_outlasts_a_one_minute_rate_limit_window():
    """A tokens-per-minute limit refills over about a minute, and rejected retries also count
    against it (OpenAI rate-limit guide), so patience matters more than a fast first retry."""
    error = APITimeoutError(request=httpx2.Request("POST", "https://api.openai.com/v1/responses"))
    attempts = ModelSettings(api_key="synthetic-not-sent").max_attempts_per_request
    shortest_waits = [
        ResponseRetryPolicy().delay_seconds(
            error, attempt_number=n, now=datetime.now(UTC), random_fraction=1
        )
        for n in range(1, attempts)
    ]
    assert sum(shortest_waits) >= 60
