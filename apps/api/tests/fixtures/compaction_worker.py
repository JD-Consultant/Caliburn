"""Restart between saved C and parent adoption, without sending compact twice."""

import asyncio
import json
import os
import sys
from copy import deepcopy
from pathlib import Path
from uuid import uuid4

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from openai.types.responses import Response
from openai.types.responses.compacted_response import CompactedResponse
from response_capacity import synthetic_capacity_limits

from caliburn.adapters.graph_checkpointer import create_graph_serializer
from caliburn.adapters.openai_responses import ResponseRequest
from caliburn.agent_execution.context_compaction import (
    CompactionRuntime,
    ReceivedCompaction,
    run_context_compaction,
)
from caliburn.agent_execution.tool_steps import (
    ReceivedModelResponse,
    ResponseStepRuntime,
    run_response_loop,
)


async def run(mode, thread_id):
    calls = {"model": 0, "compact": 0, "count": 0}
    window = [
        {"type": "compaction", "id": "cmp_test", "encrypted_content": "synthetic-opaque"},
        {"role": "user", "content": "retained synthetic message"},
    ]
    first = json.loads(Path(__file__).with_name("native-response.json").read_text("utf-8"))
    final = deepcopy(first)
    final["output"] = first["output"][:2]
    final["output"][1]["phase"] = "final_answer"

    async def model(request, request_id, input_tokens: int):
        calls["model"] += 1
        if mode == "write":
            assert calls["model"] == 1, "Must stop after durable C, before next generation"
            return ReceivedModelResponse(Response.model_validate(first), uuid4())
        assert request.create_payload()["input"] == window
        return ReceivedModelResponse(Response.model_validate(final), uuid4())

    async def count(request, request_id):
        calls["count"] += 1
        if mode == "resume":
            assert calls["count"] == 1
            assert request.count_payload()["input"] == window
            tokens = 100
        else:
            tokens = 100 if calls["count"] == 1 else 272000
        return {"input_tokens": tokens, "attempt_id": uuid4()}

    async def compact(request, request_id):
        calls["compact"] += 1
        assert mode == "write", "Saved C must prevent another paid compact"
        items = request.create_payload()["input"]
        assert items[-1] == {
            "type": "function_call_output",
            "call_id": "call_synthetic",
            "output": "observed",
        }, "Complete native Step, including tool observation, goes into compact"
        return ReceivedCompaction(
            CompactedResponse.construct(
                id="cmp_synthetic",
                object="response.compaction",
                created_at=1,
                output=window,
                usage={
                    "input_tokens": 272000,
                    "output_tokens": 100,
                    "input_tokens_details": {"cached_tokens": 0},
                    "total_tokens": 272100,
                },
            ),
            uuid4(),
        )

    async def account_compact(received):
        assert received.response.usage.output_tokens == 100

    async def guard():
        pass

    async def account_model(received):
        pass

    async def read_tool(call, operation_id):
        assert mode == "write", "Saved tool observation must not be read again"
        return "observed"

    async def execute_tool(prepared):
        raise AssertionError("Read-only fixture")

    async with AsyncPostgresSaver.from_conn_string(
        os.environ["CALIBURN_TEST_DATABASE_URL"],
        serde=create_graph_serializer(),
    ) as saver:
        await saver.setup()

        async def compact_window(request, input_count, request_id):
            items = await run_context_compaction(
                saver,
                thread_id=f"{thread_id}:compact:{request_id}",
                request=request,
                input_count=input_count,
                runtime=CompactionRuntime(
                    compact, account_compact, guard, synthetic_capacity_limits()
                ),
            )
            if mode == "write":
                raise ConnectionError("synthetic loss after C adoption before parent save")
            return items

        runtime = ResponseStepRuntime(
            model,
            read_tool,
            execute_tool,
            guard,
            account_model,
            count,
            synthetic_capacity_limits(),
            compact_window,
        )
        request = ResponseRequest(
            model="gpt-6-luna",
            instructions="fixed synthetic instructions",
            input_items=[{"role": "user", "content": "pinned map and input"}],
            tools=[],
            reasoning_effort="low",
            max_output_tokens=512,
        )
        options = dict(thread_id=thread_id, runtime=runtime, max_tool_calls=4, max_model_steps=3)
        if mode == "write":
            try:
                await run_response_loop(saver, request=request, **options)
            except ConnectionError:
                pass
            else:
                raise AssertionError("Expected original C to be saved before failure")
            assert calls == {"model": 1, "compact": 1, "count": 2}
        else:
            result = await run_response_loop(saver, request=None, **options)
            assert result["next_action"] == "deliver_answer"
            assert result["completed_steps"] == 2
            assert result["input_items"][:2] == window
            assert calls == {"model": 1, "compact": 0, "count": 1}
        print(
            json.dumps(
                {"mode": mode, "model_calls": calls["model"], "observation_calls": calls["compact"]}
            )
        )


if __name__ == "__main__":
    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        runner.run(run(sys.argv[1], sys.argv[2]))
