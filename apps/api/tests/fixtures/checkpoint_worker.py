"""Fresh-process PG probe using native response helpers, not the full product runner."""

import asyncio
import json
import os
import sys
from pathlib import Path
from uuid import UUID

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from openai.types.responses import Response, ResponseFunctionToolCall

from caliburn.adapters.graph_checkpointer import create_graph_serializer
from caliburn.adapters.response_serialization import (
    response_input_items,
    snapshot_response,
)
from caliburn.agent_execution.tool_steps import ResponseStepRuntime, _build_response_step


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

    async def request_model(items: list) -> Response:
        nonlocal model_calls
        model_calls += 1
        return response

    async def prepare_tool(call: ResponseFunctionToolCall, operation_id: UUID) -> object:
        nonlocal observation_calls
        observation_calls += 1
        assert call.call_id == "call_synthetic"
        return "synthetic result"

    async def execute_tool(prepared: object) -> str:
        raise AssertionError("The synthetic read does not have a write phase")

    async def ensure_active() -> None:
        """Isolated saver probe; no product scope in this fixture."""

    runtime = ResponseStepRuntime(request_model, prepare_tool, execute_tool, ensure_active)

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
            await graph.ainvoke(
                {"input_items": []},
                config,
                context=runtime,
                durability="sync",
                interrupt_before=["prepare_tool"],
            )
            saved = await graph.aget_state(config)
            assert saved.next == ("prepare_tool",)
            assert saved.values["response_snapshot"] == original_snapshot
            assert saved.values["input_items"] == []
            assert model_calls == 1 and observation_calls == 0
        elif mode == "resume":
            assert before.next == ("prepare_tool",)
            assert before.values["response_snapshot"] == original_snapshot
            await graph.ainvoke(None, config, context=runtime, durability="sync")
            saved = await graph.aget_state(config)
            assert not saved.next
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
