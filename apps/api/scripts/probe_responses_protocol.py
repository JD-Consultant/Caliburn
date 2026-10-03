"""Explicit, synthetic-only provider preflight; never invoked by tests or application startup.

Limits and authorization: T06 evidence, protocol preflight manifests (stage `protocol` is
§6, stage `compaction` is §20). Output is safe JSONL, not a response store. Each output path
may be used once; failures are not automatically retried.
"""

import argparse
import asyncio
import json
import re
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from openai import APIError, AsyncOpenAI
from openai.types.responses import Response
from openai.types.responses.function_tool_param import FunctionToolParam

from caliburn.adapters.openai_credentials import read_openai_api_key
from caliburn.adapters.openai_failures import classify_response_failure
from caliburn.adapters.openai_responses import (
    ResponseRequest,
    compact_context,
    count_response_input,
    create_response,
    create_responses_client,
)
from caliburn.adapters.response_serialization import (
    NativeItems,
    compaction_input_items,
    function_result_item,
    response_input_items,
    restore_response,
    snapshot_compaction,
    snapshot_response,
)
from caliburn.agent_execution.response_steps import (
    ResponseAction,
    ResponseStep,
    inspect_response_step,
)

type Stage = Literal["protocol", "compaction", "summary"]
type Emit = Callable[[dict[str, Any]], None]

MODEL = "gpt-6-luna"
INPUT_LIMIT = 4096
COMPACTED_INPUT_LIMIT = 8192
OUTPUT_LIMIT = 512
# (per request, whole batch) seconds by stage; compact has no documented latency bound.
TIMEOUTS: dict[Stage, tuple[int, int]] = {
    "protocol": (30, 120),
    "compaction": (60, 240),
    "summary": (30, 60),
}
INSTRUCTIONS = (
    "This is a synthetic API protocol check. Call read_synthetic_marker exactly once "
    "before answering. The function takes no arguments. After receiving its result, "
    "answer exactly protocol-ok. Do not call it again."
)
COMPACTED_INSTRUCTIONS = (
    "This is a synthetic API protocol check. The earlier synthetic check is complete. "
    "Do not call any function. Answer exactly compact-ok."
)
TOOL: FunctionToolParam = {
    "type": "function",
    "name": "read_synthetic_marker",
    "description": "Read the synthetic marker for this API protocol check.",
    "parameters": {
        "type": "object",
        "properties": {},
        "required": [],
        "additionalProperties": False,
    },
    "strict": True,
}


async def count_and_create(
    client: AsyncOpenAI,
    emit: Emit,
    window: NativeItems,
    *,
    step: int,
    instructions: str,
    input_limit: int,
) -> tuple[Response, ResponseStep]:
    """One count then one generation for the exact window; stops on an unexpected shape."""
    request = ResponseRequest(
        model=MODEL,
        instructions=instructions,
        input_items=window,
        tools=[TOOL],
        reasoning_effort="low",
        max_output_tokens=OUTPUT_LIMIT,
    )
    emit({"event": "request_started", "step": step, "kind": "token_count"})
    counted = await count_response_input(client, request)
    emit({"event": "input_count", "step": step, "tokens": counted.input_tokens})
    if not 0 < counted.input_tokens <= input_limit:
        raise ValueError("Input count outside preflight limit")
    emit({"event": "request_started", "step": step, "kind": "model"})
    response = await create_response(client, request)
    # Exercise the actual serializer, with a JSON round trip, without logging opaque data.
    original = snapshot_response(response)
    restored = restore_response(json.loads(json.dumps(original)))
    emit(
        {
            "event": "response_received",
            "step": step,
            "response_id": response.id,
            "model": response.model,
            "status": response.status,
            "service_tier": response.service_tier,
            "output_types": [item.type for item in response.output],
            "message_phases": [item.phase for item in response.output if item.type == "message"],
            "encrypted_reasoning_present": any(
                item.type == "reasoning" and bool(item.encrypted_content)
                for item in response.output
            ),
            "usage": response.usage.model_dump() if response.usage else None,
            "original_round_trip_equal": snapshot_response(restored) == original,
        }
    )
    if snapshot_response(restored) != original:
        raise ValueError("Original response did not round trip")
    if response.usage is None or response.usage.output_tokens > OUTPUT_LIMIT:
        raise ValueError("Missing usage or output limit exceeded")
    return restored, inspect_response_step(restored)


def extend_with_tool_result(window: NativeItems, restored: Response, routed: ResponseStep) -> None:
    """Append the original output items and the synthetic result for the one expected call."""
    if routed.action != ResponseAction.EXECUTE_TOOLS or len(routed.calls) != 1:
        raise ValueError("Expected one synthetic call")
    call = routed.calls[0]
    if call.name != TOOL["name"] or json.loads(call.arguments) != {}:
        raise ValueError("Unexpected function request")
    window.extend(response_input_items(restored))
    window.append(dict(function_result_item(call, "protocol-ok")))


async def run_preflight(client: AsyncOpenAI, emit: Emit) -> None:
    """Exactly count/create, then count/create, stopping at the first unexpected outcome."""
    window: NativeItems = [{"role": "user", "content": "Complete the synthetic protocol check."}]
    for step in (1, 2):
        restored, routed = await count_and_create(
            client, emit, window, step=step, instructions=INSTRUCTIONS, input_limit=INPUT_LIMIT
        )
        if step == 1:
            extend_with_tool_result(window, restored, routed)
        elif (
            routed.action != ResponseAction.DELIVER_ANSWER
            or restored.output_text.strip() != "protocol-ok"
        ):
            raise ValueError("Expected the synthetic final answer")
    emit({"event": "passed", "http_requests": 4, "model_requests": 2, "retries": 0})


async def run_compaction_preflight(client: AsyncOpenAI, emit: Emit) -> None:
    """One native tool step, compact its complete window, then continue from the returned C."""
    window: NativeItems = [{"role": "user", "content": "Complete the synthetic protocol check."}]
    restored, routed = await count_and_create(
        client, emit, window, step=1, instructions=INSTRUCTIONS, input_limit=INPUT_LIMIT
    )
    extend_with_tool_result(window, restored, routed)
    emit({"event": "request_started", "step": 1, "kind": "compaction"})
    compacted = await compact_context(client, model=MODEL, input_items=window)
    original = snapshot_compaction(compacted)
    # The same serializer path the product uses: JSON round trip, then the whole window.
    carried = compaction_input_items(json.loads(json.dumps(original)))
    emit(
        {
            "event": "compaction_received",
            "step": 1,
            "response_id": compacted.id,
            "input_item_types": [item.get("type", "message") for item in window],
            "output_item_types": [item.get("type", "message") for item in carried],
            "encrypted_content_present": any(
                bool(item.get("encrypted_content")) for item in carried
            ),
            "usage": original.get("usage"),
            "output_items_carried": len(carried),
        }
    )
    if not carried:
        raise ValueError("The compaction returned no window")
    next_window: NativeItems = [
        *carried,
        {"role": "user", "content": "Finish the synthetic protocol check."},
    ]
    restored, routed = await count_and_create(
        client,
        emit,
        next_window,
        step=2,
        instructions=COMPACTED_INSTRUCTIONS,
        input_limit=COMPACTED_INPUT_LIMIT,
    )
    if (
        routed.action != ResponseAction.DELIVER_ANSWER
        or restored.output_text.strip() != "compact-ok"
    ):
        raise ValueError("Expected the synthetic final answer from the compacted window")
    emit(
        {"event": "passed", "http_requests": 5, "model_requests": 2, "compactions": 1, "retries": 0}
    )


async def execute(key_file: Path, output: Path, stage: Stage) -> int:
    # Exclusive creation is intentional: a failed run is still a consumed test batch.
    with output.open("x", encoding="utf-8") as report:

        def emit(record: dict[str, Any]) -> None:
            record = {"time": datetime.now(UTC).isoformat(), **record}
            line = json.dumps(record, ensure_ascii=False)
            report.write(line + "\n")
            report.flush()
            print(line, flush=True)

        emit({"event": "started", "stage": stage, "model": MODEL, "data": "synthetic-only"})
        request_seconds, total_seconds = TIMEOUTS[stage]
        try:
            api_key = read_openai_api_key(key_file)
            async with create_responses_client(
                api_key=api_key, timeout_seconds=request_seconds
            ) as client:
                async with asyncio.timeout(total_seconds):
                    if stage == "summary":
                        await run_summary_preflight(client, emit)
                    elif stage == "compaction":
                        await run_compaction_preflight(client, emit)
                    else:
                        await run_preflight(client, emit)
        except APIError as error:
            failure = classify_response_failure(error)
            emit(
                {
                    "event": "failed",
                    "kind": failure.kind,
                    "status_code": failure.status_code,
                    "error_class": type(error).__name__,
                    # Safe protocol diagnostics only, never message/body/headers/credentials.
                    "code": _safe_identifier(error.code),
                    "param": _safe_identifier(error.param),
                }
            )
            return 1
        except Exception as error:
            emit({"event": "failed", "error_class": type(error).__name__})
            return 1
    return 0


async def run_summary_preflight(client: AsyncOpenAI, emit: Emit) -> None:
    """One synthetic count/create pair; no raw summary text or encrypted state in evidence."""
    from caliburn.adapters.reasoning_summaries import project_reasoning_summaries

    request = ResponseRequest(
        model=MODEL,
        instructions="Solve the synthetic scheduling problem and give a concise answer.",
        input_items=[
            {
                "role": "user",
                "content": (
                    "Schedule A, B, C, D on one machine. Durations are 2, 3, 1, 2 hours. "
                    "B follows A; D follows C. Deadlines: A=5, B=6, C=3, D=8. "
                    "Start at zero, no overlap. Find a feasible order and verify each deadline."
                ),
            }
        ],
        tools=[],
        reasoning_effort="high",
        reasoning_summary="auto",
        max_output_tokens=1536,
        stream=True,
    )
    counted = await count_response_input(client, request)
    emit({"event": "input_count", "tokens": counted.input_tokens})
    if not 0 < counted.input_tokens <= 2048:
        raise ValueError("Summary probe input exceeded its limit")
    updates = []
    response = await create_response(client, request, on_reasoning_summary=updates.append)
    original = snapshot_response(response)
    restored = restore_response(json.loads(json.dumps(original)))
    summaries = project_reasoning_summaries(restored)
    carried = response_input_items(restored)
    round_trip_equal = snapshot_response(restored) == original
    summary_carried_intact = all(
        item.get("summary") == original["output"][index].get("summary")
        for index, item in enumerate(carried)
        if item.get("type") == "reasoning"
    )
    emit(
        {
            "event": "summary_received",
            "model": response.model,
            "status": response.status,
            "response_id": response.id,
            "stream_update_count": len(updates),
            "summary_part_count": len(summaries),
            "summary_chars": sum(len(s.text) for s in summaries),
            "original_round_trip_equal": round_trip_equal,
            "summary_carried_intact": summary_carried_intact,
            "usage": response.usage.model_dump() if response.usage else None,
        }
    )
    if response.status != "completed" or response.usage is None:
        raise ValueError("Summary probe did not complete")
    if not round_trip_equal or not summary_carried_intact:
        raise ValueError("Summary continuation did not round trip")
    if not summaries or not updates:
        emit(
            {
                "event": "not_observed",
                "summary_observed": bool(summaries),
                "stream_observed": bool(updates),
                "http_requests": 2,
                "retries": 0,
            }
        )
        return
    emit(
        {
            "event": "passed",
            "http_requests": 2,
            "model_requests": 1,
            "retries": 0,
            "summary_observed": bool(summaries),
            "stream_observed": bool(updates),
        }
    )


def _safe_identifier(value: object) -> str | None:
    if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_.\[\]-]{1,100}", value):
        return value
    return None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--key-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--stage", choices=["protocol", "compaction", "summary"], default="protocol"
    )
    arguments = parser.parse_args()
    raise SystemExit(asyncio.run(execute(arguments.key_file, arguments.output, arguments.stage)))
