"""Explicit synthetic counting for tests focused on other execution boundaries."""

from uuid import uuid4

from caliburn.agent_execution.tool_steps import ResponseStepRuntime


def synthetic_capacity_limits():
    # These values describe a test double, not verified provider limits.
    return {
        "model": "gpt-6-luna",
        "max_input_tokens": 900_000,
        "context_window_tokens": 1_000_000,
        "max_output_tokens": 100_000,
    }


async def count_synthetic_input(request, request_id):
    return {"input_tokens": 100, "attempt_id": uuid4()}


def synthetic_response_runtime(*args, **kwargs):
    return ResponseStepRuntime(
        *args,
        count_input=count_synthetic_input,
        capacity_limits=synthetic_capacity_limits(),
        **kwargs,
    )
