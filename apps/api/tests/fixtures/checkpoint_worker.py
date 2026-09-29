"""Fresh-process PG probe using native response helpers, not the full product runner."""

import asyncio
import json
import os
import sys
from pathlib import Path
from uuid import UUID, uuid4

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from openai.types.responses import Response, ResponseFunctionToolCall

from caliburn.adapters.graph_checkpointer import create_graph_serializer
from caliburn.adapters.openai_responses import ResponseRequest
from caliburn.adapters.response_serialization import (
    response_input_items,
    snapshot_response,
)
from caliburn.agent_execution.tool_steps import (
    ReceivedModelResponse,
    ResponseStepRuntime,
    _build_response_step,
)


async def account_response(received: ReceivedModelResponse) -> None:
    """Isolated saver probe, without execution cost persistence."""


async def run(mode: str, thread_id: str) -> None:
    response = Response.model_validate_json(
        Path(__file__).with_name("native-response.json").read_text(encoding="utf-8")
    )
    original_snapshot = snapshot_response(response)
    original_items = response_input_items(response)
    model_calls = 0
    observation_calls = 0
    observation = {
        "type": "function_call_output",
        "call_id": "call_synthetic",
        "output": "synthetic result",
    }

    model_request = ResponseRequest(
        model="gpt-6-luna",
        instructions="synthetic",
        input_items=[],
        tools=[],
        reasoning_effort="low",
        max_output_tokens=512,
    )

    async def request_model(request: ResponseRequest, request_id: UUID) -> ReceivedModelResponse:
        nonlocal model_calls
        model_calls += 1
        return ReceivedModelResponse(response=response, attempt_id=uuid4())

    async def prepare_tool(call: ResponseFunctionToolCall, operation_id: UUID) -> object:
        nonlocal observation_calls
        observation_calls += 1
        assert call.call_id == "call_synthetic"
        return "synthetic result"

    async def execute_tool(prepared: object) -> str:
        raise AssertionError("The synthetic read does not have a write phase")

    async def ensure_active() -> None:
        """Isolated saver probe; no product scope in this fixture."""

    runtime = ResponseStepRuntime(
        request_model=request_model,
        prepare_tool=prepare_tool,
        execute_tool=execute_tool,
        ensure_active=ensure_active,
        account_response=account_response,
    )

    async with AsyncPostgresSaver.from_conn_string(
        os.environ["CALIBURN_TEST_DATABASE_URL"],
        serde=create_graph_serializer(),
    ) as saver:
        await saver.setup()
        graph = _build_response_step(saver, max_tool_calls=16)
        config = {"configurable": {"thread_id": thread_id}}
        before = await graph.aget_state(config)
        if mode == "write":
            assert not before.values
            request_id = uuid4()
            await graph.ainvoke(
                {
                    "request_snapshot": model_request.create_payload(),
                    "request_id": request_id,
                    "model_step_limit": None,
                    "tool_call_limit": 16,
                },
                config,
                context=runtime,
                durability="sync",
                interrupt_before=["prepare_tool"],
            )
            saved = await graph.aget_state(config)
            assert saved.next == ("prepare_tool",)
            assert saved.values["response_snapshot"] == original_snapshot
            assert saved.values["request_snapshot"] == model_request.create_payload()
            assert saved.values["request_snapshot"]["stream"] is False
            assert saved.values["request_id"] == request_id
            assert "input_items" not in saved.values
            assert model_calls == 1 and observation_calls == 0
        elif mode == "resume":
            assert before.next == ("prepare_tool",)
            assert before.values["response_snapshot"] == original_snapshot
            assert before.values["request_snapshot"] == model_request.create_payload()
            assert before.values["request_snapshot"]["stream"] is False
            assert isinstance(before.values["request_id"], UUID)
            await graph.ainvoke(None, config, context=runtime, durability="sync")
            saved = await graph.aget_state(config)
            assert not saved.next
            assert saved.values["request_id"] == before.values["request_id"]
            assert saved.values["input_items"] == [*original_items, observation]
            assert model_calls == 0 and observation_calls == 1
        else:
            raise ValueError("Unknown probe mode")
        assert not (
            await graph.aget_state({"configurable": {"thread_id": thread_id + "-other"}})
        ).values
        print(
            json.dumps(
                {"mode": mode, "model_calls": model_calls, "observation_calls": observation_calls}
            )
        )


if __name__ == "__main__":
    # Psycopg async requires Selector on Windows; explicit factory avoids deprecated policies.
    asyncio.run(run(sys.argv[1], sys.argv[2]), loop_factory=asyncio.SelectorEventLoop)
