"""A fresh-process LangGraph/PG capability probe; intentionally has no product side effects."""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any, TypedDict

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import END, START, StateGraph
from openai.types.responses import Response


class ProbeState(TypedDict):
    native_items: list[dict[str, Any]]


async def run(mode: str, thread_id: str) -> None:
    response = Response.model_validate_json(
        Path(__file__).with_name("native-response.json").read_text(encoding="utf-8")
    )
    original_items = [item.model_dump(mode="json") for item in response.output]
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
        return {"native_items": original_items}

    def observe(state: ProbeState) -> ProbeState:
        nonlocal observation_calls
        observation_calls += 1
        assert state["native_items"] == original_items
        return {"native_items": [*state["native_items"], observation]}

    async with AsyncPostgresSaver.from_conn_string(
        os.environ["CALIBURN_TEST_DATABASE_URL"]
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
            await graph.ainvoke({"native_items": []}, config, durability="sync")
            saved = await graph.aget_state(config)
            assert saved.next == ("observe",)
            assert saved.values["native_items"] == original_items
            assert model_calls == 1 and observation_calls == 0
        elif mode == "resume":
            assert before.next == ("observe",)
            assert before.values["native_items"] == original_items
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
