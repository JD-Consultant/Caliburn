"""Provider-directed delays and bounded jitter; durable admission remains the work owner."""

from dataclasses import dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime
from math import isfinite

from openai import APIError, APIStatusError

from caliburn.adapters.openai_failures import ResponseFailureKind, classify_response_failure


@dataclass(frozen=True, slots=True)
class ResponseRetryPolicy:
    initial_backoff_seconds: float = 2.0
    maximum_backoff_seconds: float = 30.0

    def __post_init__(self) -> None:
        if not (
            isfinite(self.initial_backoff_seconds)
            and isfinite(self.maximum_backoff_seconds)
            and 0 < self.initial_backoff_seconds <= self.maximum_backoff_seconds
        ):
            raise ValueError("Retry backoff must have finite positive ordered bounds")

    def delay_seconds(
        self, error: APIError, *, attempt_number: int, now: datetime, random_fraction: float
    ) -> float | None:
        """None forbids retry. A server delay is never shortened to the local backoff cap."""
        if attempt_number < 1 or not 0 <= random_fraction <= 1 or now.utcoffset() is None:
            raise ValueError("Use a positive attempt ordinal, aware clock and unit random value")
        if classify_response_failure(error).kind not in (
            ResponseFailureKind.REMOTE_RESULT_UNKNOWN,
            ResponseFailureKind.TRANSIENT_SERVICE,
        ):
            return None
        server_delay = _server_delay(error, now)
        if server_delay is not None:
            # An excessive numeric value is not permission to fall back to a shorter wait.
            return server_delay if isfinite(server_delay) else None
        backoff = min(
            self.maximum_backoff_seconds,
            self.initial_backoff_seconds * 2.0 ** min(attempt_number - 1, 1000),
        )
        return backoff * (1 - 0.25 * random_fraction)


def _server_delay(error: APIError, now: datetime) -> float | None:
    if not isinstance(error, APIStatusError):
        return None
    headers = error.response.headers
    for name, divisor in (("retry-after-ms", 1000), ("retry-after", 1)):
        raw = headers.get(name)
        if raw is None:
            continue
        try:
            delay = float(raw) / divisor
        except ValueError:
            continue
        if delay >= 0:
            return delay
        if not isfinite(delay):
            return float("inf")
    raw = headers.get("retry-after")
    if raw is None:
        return None
    try:
        date = parsedate_to_datetime(raw)
        if date.utcoffset() is None:
            return None
        return max(0.0, (date - now).total_seconds())
    except ValueError, TypeError, OverflowError:
        return None
