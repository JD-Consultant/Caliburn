"""Validate saved request counts; never guess, truncate or select another model."""

from dataclasses import dataclass
from typing import TypedDict
from uuid import UUID

from caliburn.adapters.openai_models import ModelCapacityLimits as ModelCapacityLimits
from caliburn.adapters.openai_responses import ResponseRequest

# Each attempt costs one more exact count, so the owner of an oversized first request
# gets a small fixed number of reductions before the work is reported as capacity-blocked.
MAX_FIRST_REQUEST_FITS = 3
# Shared complete-Step/handoff policy; not a provider capacity or rate-limit guarantee.
MID_WORK_COMPACTION_THRESHOLD_TOKENS = 160_000


class ReceivedInputCount(TypedDict):
    input_tokens: int
    attempt_id: UUID


class RequestCapacityError(ValueError):
    """Do not issue generation with this saved request and capacity policy."""


class RequestOverCapacityError(RequestCapacityError):
    """The exact saved count exceeds the hard input limit; only the data's owner may shrink it."""

    def __init__(self, *, input_tokens: int, allowed_input_tokens: int) -> None:
        self.input_tokens = input_tokens
        self.allowed_input_tokens = allowed_input_tokens
        super().__init__("The counted request exceeds the configured model capacity")


@dataclass(frozen=True, slots=True)
class RequestOverflow:
    """A counted, unsent first request above its hard input limit; attempt starts at 1."""

    input_tokens: int
    allowed_input_tokens: int
    attempt: int


class CompactionRequiredError(ValueError):
    """A complete-Step boundary needs explicit compaction before the next request."""


def validate_capacity_limits(limits: ModelCapacityLimits) -> None:
    if set(limits) != {"model", "max_input_tokens", "context_window_tokens", "max_output_tokens"}:
        raise ValueError("Configure explicit model capacity limits")
    if not isinstance(limits["model"], str) or not limits["model"].strip():
        raise ValueError("Configure a model for the capacity limits")
    for value in (
        limits["max_input_tokens"],
        limits["context_window_tokens"],
        limits["max_output_tokens"],
    ):
        if type(value) is not int or value < 1:
            raise ValueError("Configure positive integer capacity limits")


def allowed_input_tokens(request: ResponseRequest, limits: ModelCapacityLimits) -> int:
    """Highest counted input that still leaves the requested output inside the window."""
    output_tokens: int = request.create_payload()["max_output_tokens"]
    return min(limits["max_input_tokens"], limits["context_window_tokens"] - output_tokens)


def require_request_limits(request: ResponseRequest, limits: ModelCapacityLimits) -> None:
    """Reject known configuration errors before making even the remote count request."""
    validate_capacity_limits(limits)
    payload = request.create_payload()
    if payload["model"] != limits["model"]:
        raise RequestCapacityError("The request model has no matching capacity policy")
    if payload["max_output_tokens"] > min(
        limits["max_output_tokens"], limits["context_window_tokens"]
    ):
        raise RequestCapacityError("The requested output exceeds the configured capacity")


def require_request_capacity(
    request: ResponseRequest,
    count: ReceivedInputCount,
    limits: ModelCapacityLimits,
    *,
    completed_steps: int,
) -> None:
    require_request_limits(request, limits)
    tokens = count["input_tokens"]
    if type(tokens) is not int or tokens < 0 or not isinstance(count["attempt_id"], UUID):
        raise RequestCapacityError("The saved input count is invalid; capacity is unknown")
    allowed = allowed_input_tokens(request, limits)
    if tokens > allowed:
        raise RequestOverCapacityError(input_tokens=tokens, allowed_input_tokens=allowed)
    # Caliburn policy, not a provider context-window guarantee. First-request preparation
    # and actual compact/adoption belong to their own workflow, not to this count gate.
    if completed_steps > 0 and tokens >= MID_WORK_COMPACTION_THRESHOLD_TOKENS:
        raise CompactionRequiredError("The next request requires explicit boundary compaction")
