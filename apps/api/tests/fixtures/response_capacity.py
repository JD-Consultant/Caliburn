"""Explicit synthetic counting for tests focused on other execution boundaries."""

import json
from pathlib import Path
from uuid import uuid4

import pytest
from openai.types.responses import Response

from caliburn.adapters.openai_responses import ResponseRequest
from caliburn.agent_execution.tool_steps import ReceivedModelResponse, ResponseStepRuntime


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


def request_fixture() -> ResponseRequest:
    return ResponseRequest(
        model="gpt-6-luna",
        instructions="synthetic fixed instructions",
        input_items=[{"role": "user", "content": "synthetic pinned map"}],
        tools=[],
        reasoning_effort="low",
        max_output_tokens=512,
    )


class CapacityProbe:
    def __init__(self, counts: list[int], *, final: bool = True) -> None:
        self.counts = counts
        self.count_requests = []
        self.model_requests = []
        self.model_input_tokens = []
        self.fail_model = False
        self.final = final

    async def count(self, request, request_id):
        self.count_requests.append((request_id, request.count_payload()))
        return {
            "input_tokens": self.counts[len(self.count_requests) - 1],
            "attempt_id": uuid4(),
        }

    async def model(self, request, request_id, input_tokens: int):
        if self.fail_model:
            raise ConnectionError("synthetic before generation admission")
        self.model_requests.append(request.create_payload())
        self.model_input_tokens.append(input_tokens)
        payload = json.loads(Path(__file__).with_name("native-response.json").read_text("utf-8"))
        payload["output"] = payload["output"][:2]
        payload["output"][1]["phase"] = (
            "final_answer" if self.final or len(self.model_requests) > 1 else "commentary"
        )
        return ReceivedModelResponse(Response.model_validate(payload), uuid4())

    async def guard(self):
        pass

    async def account(self, response):
        pass

    async def tool(self, *args):
        pytest.fail("This capacity fixture has no tools")

    def runtime(self, **limits):
        return ResponseStepRuntime(
            request_model=self.model,
            prepare_tool=self.tool,
            execute_tool=self.tool,
            ensure_active=self.guard,
            account_response=self.account,
            count_input=self.count,
            capacity_limits={
                "model": "gpt-6-luna",
                "max_input_tokens": 900_000,
                "context_window_tokens": 1_000_000,
                "max_output_tokens": 100_000,
                **limits,
            },
        )
