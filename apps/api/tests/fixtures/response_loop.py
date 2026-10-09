"""Synthetic native responses and loop probes shared by isolated execution tests."""

import json
from pathlib import Path
from uuid import UUID, uuid4

from openai.types.responses import Response, ResponseFunctionToolCall

from caliburn.adapters.openai_responses import ResponseRequest
from caliburn.agent_execution.tool_steps import ReceivedModelResponse, ResponseStepRuntime
from tests.fixtures.response_capacity import synthetic_response_runtime


def response_at(index: int, *, final: bool = False, tools: int = 0) -> Response:
    payload = json.loads(
        (Path(__file__).with_name("native-response.json")).read_text(encoding="utf-8")
    )
    payload["id"] = f"response_{index}"
    call = payload["output"].pop()
    payload["output"][0]["id"] = f"reasoning_{index}"
    payload["output"][0]["encrypted_content"] = f"synthetic-opaque-{index}"
    payload["output"][1]["id"] = f"message_{index}"
    payload["output"][1]["phase"] = "final_answer" if final else "commentary"
    for ordinal in range(tools):
        payload["output"].append(
            {**call, "id": f"function_{index}_{ordinal}", "call_id": f"call_{index}_{ordinal}"}
        )
    return Response.model_validate(payload)


def initial_request() -> ResponseRequest:
    return ResponseRequest(
        model="gpt-6-luna",
        instructions="synthetic fixed instructions",
        input_items=[
            {"role": "user", "content": "synthetic pinned Memory map"},
            {"role": "user", "content": "synthetic current employee input"},
        ],
        tools=[],
        reasoning_effort="low",
        max_output_tokens=512,
    )


class LoopProbe:
    def __init__(self, responses: list[Response]) -> None:
        self.responses = responses
        self.requests: list[dict] = []
        self.request_ids: list[UUID] = []
        self.effects: list[str] = []
        self.accounted: list[str] = []
        self.active = True

    async def request(
        self, request: ResponseRequest, request_id: UUID, input_tokens: int
    ) -> ReceivedModelResponse:
        self.requests.append(request.create_payload())
        self.request_ids.append(request_id)
        return ReceivedModelResponse(self.responses[len(self.requests) - 1], uuid4())

    async def prepare(self, call: ResponseFunctionToolCall, operation_id: UUID) -> object:
        return {"call_id": call.call_id, "operation_id": operation_id}

    async def execute(self, prepared: object) -> str:
        assert isinstance(prepared, dict)
        self.effects.append(prepared["call_id"])
        return "observation:" + prepared["call_id"]

    async def guard(self) -> None:
        if not self.active:
            raise PermissionError("synthetic cancelled execution")

    async def account(self, received: ReceivedModelResponse) -> None:
        self.accounted.append(received.response.id)

    def runtime(self) -> ResponseStepRuntime:
        return synthetic_response_runtime(
            request_model=self.request,
            prepare_tool=self.prepare,
            execute_tool=self.execute,
            ensure_active=self.guard,
            account_response=self.account,
        )
