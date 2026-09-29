"""Fresh-process PG probe using native response helpers, not the full product runner."""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any, TypedDict

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.graph import END, START, StateGraph
from openai.types.responses import Response

from caliburn.adapters.response_serialization import (
    function_result_item,
    response_input_items,
    restore_response,
    snapshot_response,
)
from caliburn.agent_execution.response_steps import ResponseAction, inspect_response_step


class ProbeState(TypedDict):
    response_snapshot: dict[str, Any]
    native_items: list[dict[str, Any]]


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

    def model_step(state: ProbeState) -> ProbeState:
        nonlocal model_calls
        model_calls += 1
        return {"response_snapshot": original_snapshot, "native_items": []}

    def observe(state: ProbeState) -> ProbeState:
        nonlocal observation_calls
        observation_calls += 1
        restored = restore_response(state["response_snapshot"])
        step = inspect_response_step(restored)
        assert step.action == ResponseAction.EXECUTE_TOOLS
        assert len(step.calls) == 1
        result = function_result_item(step.calls[0], "synthetic result")
        assert result == observation
        return {
            "response_snapshot": state["response_snapshot"],
            "native_items": [*response_input_items(restored), result],
        }

    async with AsyncPostgresSaver.from_conn_string(
        os.environ["CALIBURN_TEST_DATABASE_URL"],
        serde=JsonPlusSerializer(pickle_fallback=False, allowed_msgpack_modules=None),
    ) as saver:
        await saver.setup()
        builder = StateGraph(ProbeState)
        builder.add_node("model_step", model_step)
        builder.add_node("observe", observe)
        builder.add_edge(START, "model_step")
        builder.add_edge("model_step", "observe")
        builder.add_edge("observe", END)
        graph = builder.compile(checkpointer=saver, interrupt_before=["observe"])
        config = {"configurable": {"thread_id": thread_id}}
        before = await graph.aget_state(config)
        if mode == "write":
            assert not before.values
            await graph.ainvoke(
                {"response_snapshot": {}, "native_items": []}, config, durability="sync"
            )
            saved = await graph.aget_state(config)
            assert saved.next == ("observe",)
            assert saved.values["response_snapshot"] == original_snapshot
            assert saved.values["native_items"] == []
            assert model_calls == 1 and observation_calls == 0
        elif mode == "resume":
            assert before.next == ("observe",)
            assert before.values["response_snapshot"] == original_snapshot
            await graph.ainvoke(None, config, durability="sync")
            saved = await graph.aget_state(config)
            assert not saved.next
            assert saved.values["native_items"] == [*original_items, observation]
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
