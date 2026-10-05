"""One bounded role episode, with network admission owned by the caller."""

import json
from collections.abc import Awaitable, Callable

from caliburn.adapters.openai_responses import ResponseRequest
from caliburn.adapters.response_serialization import (
    function_result_item,
    response_input_items,
)
from caliburn.settings import ModelSettings
from openai.types.responses import Response
from protocol import validate_completion
from workspace import Workspace, tool_definitions


async def run_episode(
    workspace: Workspace,
    role: str,
    instructions: str,
    context: dict,
    settings: ModelSettings,
    send: Callable[[ResponseRequest], Awaitable[Response]],
    event: Callable[[dict], None],
) -> dict:
    items = [{"role": "user", "content": json.dumps(context, ensure_ascii=False)}]
    reads: set[tuple] = set()
    tool_calls = []
    for step in range(1, settings.max_model_steps + 1):
        request = ResponseRequest(
            model=settings.model,
            instructions=instructions,
            input_items=items,
            tools=tool_definitions(workspace.arm, role),
            reasoning_effort=settings.reasoning_effort,
            max_output_tokens=settings.max_output_tokens,
        )
        response = await send(request)
        if response.status != "completed":
            raise ValueError(f"incomplete_response:{response.status}")
        items.extend(response_input_items(response))
        calls = [item for item in response.output if item.type == "function_call"]
        if len(calls) > settings.max_tool_calls_per_step:
            raise ValueError("tool_calls_per_step_limit")
        for call in calls:
            try:
                arguments = json.loads(call.arguments)
                result = workspace.invoke(role, call.name, arguments)
            except json.JSONDecodeError:
                arguments = None
                result = Workspace._error("invalid_json")
            record = {
                "event": "tool",
                "step": step,
                "name": call.name,
                "arguments": arguments,
                "result": result,
            }
            event(record)
            tool_calls.append(record)
            if "error" not in result:
                if call.name == "read_interview":
                    reads.update(
                        ("interview", item["interview_sequence"])
                        for item in result["messages"]
                    )
                elif call.name in ("read_work_understanding", "read_work_situation"):
                    reads.add(
                        (call.name.removeprefix("read_"), arguments["target_title"])
                    )
            items.append(
                function_result_item(call, json.dumps(result, ensure_ascii=False))
            )
        if calls:
            continue
        final_messages = [
            item
            for item in response.output
            if item.type == "message"
            and getattr(item, "phase", None) in (None, "final_answer")
        ]
        if not final_messages:
            continue
        text = "".join(
            part.text
            for message in final_messages
            for part in message.content
            if part.type == "output_text"
        )
        value = json.loads(text)
        validate_completion(role, value, workspace, reads)
        return {
            "final": value,
            "steps": step,
            "tool_calls": tool_calls,
            "reads": sorted(reads, key=str),
        }
    raise ValueError("model_step_limit")
