"""Explicit, synthetic-only provider preflight; never invoked by tests or application startup.

Limits and authorization: T06 evidence, protocol preflight manifest. Output is safe JSONL,
not a response store. Each output path may be used once; failures are not automatically retried.
"""

import argparse
import asyncio
import json
import re
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from openai import APIError, AsyncOpenAI
from openai.types.responses.function_tool_param import FunctionToolParam

from caliburn.adapters.openai_failures import classify_response_failure
from caliburn.adapters.openai_responses import (
    ResponseRequest,
    count_response_input,
    create_response,
    create_responses_client,
)
from caliburn.adapters.response_serialization import (
    NativeItems,
    function_result_item,
    response_input_items,
    restore_response,
    snapshot_response,
)
from caliburn.agent_execution.response_steps import ResponseAction, inspect_response_step

MODEL = "gpt-6-luna"
INPUT_LIMIT = 4096
OUTPUT_LIMIT = 512
REQUEST_TIMEOUT_SECONDS = 30
TOTAL_TIMEOUT_SECONDS = 120
INSTRUCTIONS = (
    "This is a synthetic API protocol check. Call read_synthetic_marker exactly once "
    "before answering. The function takes no arguments. After receiving its result, "
    "answer exactly protocol-ok. Do not call it again."
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


def read_api_key(path: Path) -> str:
    """Load only the explicitly authorized key; never evaluate or apply other env values."""
    values = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        name, separator, value = line.strip().partition("=")
        if separator and name.strip() == "OPENAI_API_KEY":
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            values.append(value)
    if len(values) != 1 or not re.fullmatch(r"[A-Za-z0-9_-]+", values[0]):
        raise ValueError("Exactly one plain OPENAI_API_KEY value is required")
    return values[0]


async def run_preflight(client: AsyncOpenAI, emit: Callable[[dict[str, Any]], None]) -> None:
    """Exactly count/create, then count/create, stopping at the first unexpected outcome."""
    window: NativeItems = [{"role": "user", "content": "Complete the synthetic protocol check."}]
    for step in (1, 2):
        request = ResponseRequest(
            model=MODEL,
            instructions=INSTRUCTIONS,
            input_items=window,
            tools=[TOOL],
            reasoning_effort="low",
            max_output_tokens=OUTPUT_LIMIT,
        )
        emit({"event": "request_started", "step": step, "kind": "token_count"})
        counted = await count_response_input(client, request)
        emit({"event": "input_count", "step": step, "tokens": counted.input_tokens})
        if not 0 < counted.input_tokens <= INPUT_LIMIT:
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
                "message_phases": [
                    item.phase for item in response.output if item.type == "message"
                ],
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
        routed = inspect_response_step(restored)
        if step == 1:
            if routed.action != ResponseAction.EXECUTE_TOOLS or len(routed.calls) != 1:
                raise ValueError("Expected one synthetic call")
            call = routed.calls[0]
            if call.name != TOOL["name"] or json.loads(call.arguments) != {}:
                raise ValueError("Unexpected function request")
            window.extend(response_input_items(restored))
            window.append(dict(function_result_item(call, "protocol-ok")))
        elif (
            routed.action != ResponseAction.DELIVER_ANSWER
            or restored.output_text.strip() != "protocol-ok"
        ):
            raise ValueError("Expected the synthetic final answer")
    emit({"event": "passed", "http_requests": 4, "model_requests": 2, "retries": 0})


async def execute(key_file: Path, output: Path) -> int:
    # Exclusive creation is intentional: a failed run is still a consumed test batch.
    with output.open("x", encoding="utf-8") as report:

        def emit(record: dict[str, Any]) -> None:
            record = {"time": datetime.now(UTC).isoformat(), **record}
            line = json.dumps(record, ensure_ascii=False)
            report.write(line + "\n")
            report.flush()
            print(line, flush=True)

        emit({"event": "started", "model": MODEL, "data": "synthetic-only"})
        try:
            api_key = read_api_key(key_file)
            async with create_responses_client(
                api_key=api_key, timeout_seconds=REQUEST_TIMEOUT_SECONDS
            ) as client:
                async with asyncio.timeout(TOTAL_TIMEOUT_SECONDS):
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


def _safe_identifier(value: object) -> str | None:
    if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_.\[\]-]{1,100}", value):
        return value
    return None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--key-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    raise SystemExit(asyncio.run(execute(arguments.key_file, arguments.output)))
