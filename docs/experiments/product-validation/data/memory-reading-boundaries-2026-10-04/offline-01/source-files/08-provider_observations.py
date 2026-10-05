"""Experiment-only, allowlisted rate headers; never persist arbitrary HTTP headers."""

import re

HEADER_NAMES = (
    "retry-after",
    "x-ratelimit-limit-requests",
    "x-ratelimit-limit-tokens",
    "x-ratelimit-remaining-requests",
    "x-ratelimit-remaining-tokens",
    "x-ratelimit-reset-requests",
    "x-ratelimit-reset-tokens",
    "x-ratelimit-limit-project-tokens",
    "x-ratelimit-remaining-project-tokens",
    "x-ratelimit-reset-project-tokens",
)


def rate_headers(headers) -> dict[str, str]:
    return {
        key: value
        for key in HEADER_NAMES
        if (value := headers.get(key)) is not None
        and re.fullmatch(r"[0-9.mshd]+", value)
        and len(value) < 80
    }


def reset_seconds(value: str) -> float:
    parts = re.findall(r"(\d+(?:\.\d+)?)(ms|s|m|h|d)", value)
    if not parts or "".join(number + unit for number, unit in parts) != value:
        return 0.0
    units = {"ms": 0.001, "s": 1, "m": 60, "h": 3600, "d": 86400}
    return sum(float(number) * units[unit] for number, unit in parts)


def admission_delay(headers: dict, elapsed: float, input_tokens: int) -> float:
    waits = [max(0, 5 - elapsed)]
    limit = headers.get("x-ratelimit-limit-tokens")
    if limit is not None and limit.isdigit() and int(limit) > 0:
        # Remaining/reset is a snapshot, not a reservation for our next input.
        # Pace conservatively at 5/6 of the observed TPM even when a cached
        # request returned a nearly full remaining-token counter.
        waits.append(max(0, (input_tokens + 4096) * 72 / int(limit) - elapsed))
    for resource, required in (
        ("requests", 1),
        ("tokens", input_tokens + 4096),
        ("project-tokens", input_tokens + 4096),
    ):
        remaining = headers.get(f"x-ratelimit-remaining-{resource}")
        if remaining is not None and remaining.isdigit() and int(remaining) < required:
            reset = reset_seconds(headers.get(f"x-ratelimit-reset-{resource}", ""))
            waits.append(max(0, reset - elapsed) + 1)
    if "x-ratelimit-remaining-tokens" not in headers:
        waits.append(max(0, (60 if input_tokens > 40_000 else 10) - elapsed))
    return max(waits)
