"""Fresh-process PG probe using native response helpers, not the full product runner."""

import asyncio
import json
import os
import sys
from pathlib import Path
from uuid import UUID, uuid4

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from openai.types.responses import Response, ResponseFunctionToolCall

from caliburn.adapters.database_settings import require_isolated_test_database
from caliburn.adapters.graph_checkpointer import create_graph_serializer
from caliburn.adapters.openai_responses import ResponseRequest
from caliburn.adapters.response_serialization import (
    response_input_items,
    snapshot_response,
)
from caliburn.agent_execution.response_runtime import ReceivedModelResponse
from caliburn.agent_execution.tool_steps import _completed_step_items
from tests.fixtures.native_response_runtime import read_response_state, run_response_step
from tests.fixtures.response_capacity import synthetic_response_runtime


async def account_response(received: ReceivedModelResponse) -> None:
    """Isolated saver probe, without execution cost persistence."""


async def run(mode: str, thread_id: str) -> None:
    require_isolated_test_database(os.environ["CALIBURN_TEST_DATABASE_URL"], environment=os.environ)
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

    async def request_model(
        request: ResponseRequest, request_id: UUID, input_tokens: int
    ) -> ReceivedModelResponse:
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

    async def account_saved(received):
        if mode == "write":
            raise ConnectionError("synthetic stop after durable raw response")

    runtime = synthetic_response_runtime(
        request_model=request_model,
        prepare_tool=prepare_tool,
        execute_tool=execute_tool,
        ensure_active=ensure_active,
        account_response=account_saved,
    )

    async with AsyncPostgresSaver.from_conn_string(
        os.environ["CALIBURN_TEST_DATABASE_URL"],
        serde=create_graph_serializer(),
    ) as saver:
        await saver.setup()
        config = {"configurable": {"thread_id": thread_id}}
        before = await read_response_state(saver, config)
        if mode == "write":
            assert "request_id" not in before.values
            try:
                await run_response_step(
                    saver,
                    thread_id=thread_id,
                    request=model_request,
                    runtime=runtime,
                    max_tool_calls=16,
                )
            except ConnectionError:
                pass
            else:
                raise AssertionError("The fixture must stop after its durable raw response")
            saved = await read_response_state(saver, config)
            assert saved.next == ("NativePolicy.after_model",)
            assert saved.values["response_snapshot"] == original_snapshot
            assert saved.values["request_snapshot"] == model_request.create_payload()
            assert saved.values["request_snapshot"]["stream"] is False
            assert "input_items" not in saved.values
            assert model_calls == 1 and observation_calls == 0
        elif mode == "resume":
            assert before.next == ("NativePolicy.after_model",)
            assert before.values["response_snapshot"] == original_snapshot
            assert before.values["request_snapshot"] == model_request.create_payload()
            assert before.values["request_snapshot"]["stream"] is False
            assert isinstance(before.values["request_id"], UUID)
            await run_response_step(
                saver, thread_id=thread_id, request=None, runtime=runtime, max_tool_calls=16
            )
            saved = await read_response_state(saver, config)
            assert saved.values["completed_steps"] == 1
            assert saved.values["request_id"] == before.values["request_id"]
            assert "input_items" not in saved.values
            assert _completed_step_items(
                saved.values["request_snapshot"],
                saved.values["response_snapshot"],
                saved.values["tool_results"],
            ) == [*original_items, observation]
            assert model_calls == 0 and observation_calls == 1
        else:
            raise ValueError("Unknown probe mode")
        assert (
            "request_id"
            not in (
                await read_response_state(
                    saver, {"configurable": {"thread_id": thread_id + "-other"}}
                )
            ).values
        )
        print(
            json.dumps(
                {"mode": mode, "model_calls": model_calls, "observation_calls": observation_calls}
            )
        )


if __name__ == "__main__":
    # Psycopg async requires Selector on Windows; explicit factory avoids deprecated policies.
    asyncio.run(run(sys.argv[1], sys.argv[2]), loop_factory=asyncio.SelectorEventLoop)
