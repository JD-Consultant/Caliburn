"""Input isolation and full-history reading for this bounded experiment."""

import json
import sys
from collections.abc import Awaitable, Callable
from pathlib import Path

from caliburn.adapters.openai_responses import ResponseRequest
from caliburn.adapters.response_serialization import response_input_items
from caliburn.settings import ModelSettings
from openai.types.responses import Response

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "memory-structure-incremental-2026-10-05"
sys.path.insert(0, str(SOURCE))
from protocol import reader_context, validate_completion
from workspace import Workspace


def reading_context(workspace: Workspace, question: str, *, arm: str) -> dict:
    if arm == "layered":
        return reader_context(workspace, question)
    if arm != "full_history":
        raise ValueError("unknown_reading_arm")
    messages = workspace.read_interview(
        {
            "kind": "range",
            "start_sequence": 1,
            "end_sequence": workspace.read_through,
        }
    )["messages"]
    return {"question": question, "historical_interview": messages}


async def run_history_episode(
    workspace: Workspace,
    instructions: str,
    context: dict,
    settings: ModelSettings,
    send: Callable[[ResponseRequest], Awaitable[Response]],
) -> dict:
    """Read the complete visible source without forcing a redundant tool call."""
    items = [{"role": "user", "content": json.dumps(context, ensure_ascii=False)}]
    reads = {
        ("interview", item["interview_sequence"])
        for item in context["historical_interview"]
    }
    for step in range(1, settings.max_model_steps + 1):
        response = await send(
            ResponseRequest(
                model=settings.model,
                instructions=instructions,
                input_items=items,
                tools=[],
                reasoning_effort=settings.reasoning_effort,
                max_output_tokens=settings.max_output_tokens,
            )
        )
        if response.status != "completed":
            raise ValueError(f"incomplete_response:{response.status}")
        items.extend(response_input_items(response))
        if any(item.type == "function_call" for item in response.output):
            raise ValueError("unexpected_history_tool_call")
        messages = [
            item
            for item in response.output
            if item.type == "message"
            and getattr(item, "phase", None) in (None, "final_answer")
        ]
        if not messages:
            continue
        value = json.loads(
            "".join(
                part.text
                for item in messages
                for part in item.content
                if part.type == "output_text"
            )
        )
        validate_completion("reader", value, workspace, reads)
        return {
            "final": value,
            "steps": step,
            "tool_calls": [],
            "reads": sorted(reads, key=str),
        }
    raise ValueError("model_step_limit")
