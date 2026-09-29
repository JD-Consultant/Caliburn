"""Validate saved request counts; never guess, truncate or select another model."""

from typing import TypedDict
from uuid import UUID

from caliburn.adapters.openai_responses import ResponseRequest


class ModelCapacityLimits(TypedDict):
    model: str
    max_input_tokens: int
    context_window_tokens: int
    max_output_tokens: int


class ReceivedInputCount(TypedDict):
    input_tokens: int
    attempt_id: UUID


class RequestCapacityError(ValueError):
    """Do not issue generation with this saved request and capacity policy."""


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
    payload = request.create_payload()
    output_tokens = payload["max_output_tokens"]
    if (
        tokens > limits["max_input_tokens"]
        or tokens + output_tokens > limits["context_window_tokens"]
    ):
        raise RequestCapacityError("The counted request exceeds the configured model capacity")
    # Caliburn policy, not a provider context-window guarantee. First-request preparation
    # and actual compact/adoption belong to their own workflow, not to this count gate.
    if completed_steps > 0 and tokens >= 272_000:
        raise CompactionRequiredError("The next request requires explicit boundary compaction")
