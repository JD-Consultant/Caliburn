"""Two-process probe: recover the second saved R without repeating the first Step."""

import asyncio
import json
import os
import sys
from pathlib import Path
from uuid import UUID, uuid4

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from openai.types.responses import Response, ResponseFunctionToolCall
from response_capacity import synthetic_response_runtime

from caliburn.adapters.graph_checkpointer import create_graph_serializer
from caliburn.adapters.openai_responses import ResponseRequest
from caliburn.adapters.response_serialization import response_input_items
from caliburn.agent_execution.tool_steps import (
    ReceivedModelResponse,
    _build_response_step,
    run_response_loop,
)


async def run(mode: str, thread_id: str) -> None:
    first = Response.model_validate_json(
        Path(__file__).with_name("native-response.json").read_text(encoding="utf-8")
    )
    payload = first.model_dump(mode="json")
    payload["id"] = "response_final"
    payload["output"] = payload["output"][:2]
    payload["output"][0]["id"] = "reasoning_final"
    payload["output"][1]["id"] = "message_final"
    payload["output"][1]["phase"] = "final_answer"
    final = Response.model_validate(payload)
    initial = ResponseRequest(
        model="gpt-6-luna",
        instructions="synthetic fixed instructions",
        input_items=[{"role": "user", "content": "synthetic pinned map and input"}],
        tools=[],
        reasoning_effort="low",
        max_output_tokens=512,
    )
    first_window = [
        *initial.create_payload()["input"],
        *response_input_items(first),
        {"type": "function_call_output", "call_id": "call_synthetic", "output": "synthetic result"},
    ]
    model_calls = 0
    observation_calls = 0

    async def request_model(request: ResponseRequest, request_id: UUID) -> ReceivedModelResponse:
        nonlocal model_calls
        model_calls += 1
        assert mode == "write", "Restoring saved R must not reissue either model request"
        if model_calls == 1:
            assert request.create_payload() == initial.create_payload()
            return ReceivedModelResponse(first, uuid4())
        assert model_calls == 2
        assert request.create_payload() == {**initial.create_payload(), "input": first_window}
        return ReceivedModelResponse(final, uuid4())

    async def prepare_tool(call: ResponseFunctionToolCall, operation_id: UUID) -> object:
        nonlocal observation_calls
        observation_calls += 1
        assert mode == "write", "Completed first-Step observations must not be repeated"
        assert call.call_id == "call_synthetic"
        return "synthetic result"

    async def execute_tool(prepared: object) -> str:
        raise AssertionError("This probe uses read-only observations")

    async def ensure_active() -> None:
        """Serializer/process probe, without a product writer or provider cost."""

    async def account_response(received: ReceivedModelResponse) -> None:
        if mode == "write" and received.response.id == final.id:
            raise ConnectionError("synthetic interruption after saving second response")

    runtime = synthetic_response_runtime(
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
        options = {
            "thread_id": thread_id,
            "runtime": runtime,
            "max_tool_calls": 4,
            "max_model_steps": 2,
        }
        graph = _build_response_step(saver, max_tool_calls=4, max_model_steps=2)
        config = {"configurable": {"thread_id": thread_id}}
        if mode == "write":
            try:
                await run_response_loop(saver, request=initial, **options)
            except ConnectionError:
                pass
            else:
                raise AssertionError("The probe must stop at its injected interruption")
            saved = await graph.aget_state(config)
            assert saved.next == ("account_response",)
            assert saved.values["completed_steps"] == 1
            assert saved.values["response_snapshot"]["id"] == final.id
            assert model_calls == 2 and observation_calls == 1
        elif mode == "resume":
            before = await graph.aget_state(config)
            assert before.values["request_snapshot"]["input"] == first_window
            result = await run_response_loop(saver, request=None, **options)
            assert result["request_id"] == before.values["request_id"]
            assert result["input_items"] == [*first_window, *response_input_items(final)]
            assert result["completed_steps"] == 2
            assert result["next_action"] == "deliver_answer"
            assert await run_response_loop(saver, request=None, **options) == result
            assert model_calls == 0 and observation_calls == 0
        else:
            raise ValueError("Unknown probe mode")
    print(
        json.dumps(
            {"mode": mode, "model_calls": model_calls, "observation_calls": observation_calls}
        )
    )


if __name__ == "__main__":
    asyncio.run(run(sys.argv[1], sys.argv[2]), loop_factory=asyncio.SelectorEventLoop)
