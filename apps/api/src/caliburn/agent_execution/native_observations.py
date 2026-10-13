"""Pure observations from saved native JSON; never replay or business eligibility."""

import json
import re
from collections.abc import Iterable
from copy import deepcopy
from typing import Any
from uuid import UUID, uuid5

SENSITIVE_FIELDS = {"encrypted_content", "api_key", "openai_api_key", "authorization", "password"}


def redact(value: Any) -> Any:
    """Mask known sensitive fields, including JSON tool strings; not a PII anonymizer."""
    if isinstance(value, dict):
        return {
            key: "[redacted]" if key.lower() in SENSITIVE_FIELDS else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, str):
        if value.lstrip().startswith(("{", "[")):
            try:
                decoded = json.loads(value)
            except json.JSONDecodeError:
                pass
            else:
                cleaned = redact(decoded)
                if cleaned != decoded:
                    return json.dumps(cleaned, ensure_ascii=False)
        return re.sub(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{16,}", "[redacted]", value)
    return value


def collect_steps(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """依原請求身分合併觀察；只有已保存請求時也保留，不推定已外送。"""
    records = list(records)
    steps: dict[tuple[str, str], dict[str, Any]] = {}
    for record in records:
        if (
            record.get("checkpoint_ns")
            or record["thread_id"].endswith(":initial_context")
            or record["thread_id"].endswith(":context")
            or ":prepared_history" in record["thread_id"]
            or ":compact:" in record["thread_id"]
        ):
            continue
        values = record["values"]
        response = values.get("response_snapshot")
        request = values.get("request_snapshot")
        request_id = values.get("request_id")
        if not request and not response:
            continue
        if response and (not isinstance(response, dict) or not isinstance(response.get("id"), str)):
            raise ValueError("Invalid saved response snapshot")
        if request_id is None:
            raise ValueError("Saved model request identity is unavailable")
        key = (record["thread_id"], str(request_id))
        if key not in steps:
            steps[key] = {
                **{key: value for key, value in record.items() if key != "values"},
                "request_id": request_id,
                "request": deepcopy(request),
                "input_count": None,
                "response": None,
                "response_state": "request_only",
                "tool_results": {},
                "metadata": {"operation_seed": None, "tool_operation_ids": {}},
            }
        step = steps[key]
        if step["request"] != request:
            raise ValueError("Conflicting original requests for one identity")
        if not response:
            continue
        if step["response"] is None:
            step.update(
                response=deepcopy(response),
                response_state="recorded",
                response_checkpoint_id=record["checkpoint_id"],
                response_checkpoint_time=record["checkpoint_time"],
                response_source=record["source"],
            )
        elif step["response"] != response:
            raise ValueError("Conflicting saved responses for one request")
        calls = {
            item["call_id"] for item in response["output"] if item.get("type") == "function_call"
        }
        raw_seed = values.get("operation_seed")
        seed = UUID(str(raw_seed)) if raw_seed is not None else None
        metadata = step["metadata"]
        if seed is not None:
            if metadata["operation_seed"] not in {None, str(seed)}:
                raise ValueError("Conflicting operation seeds for one response")
            metadata["operation_seed"] = str(seed)
        # Only observations carrying this response qualify; a request-only observation
        # may still carry the preceding Step's seed and must never supply this identity.
        response_seed = metadata["operation_seed"]
        metadata["tool_operation_ids"] = {
            call_id: str(uuid5(UUID(response_seed), call_id)) if response_seed else None
            for call_id in calls
        }
        for result in values.get("tool_results", []):
            call_id = result["call_id"]
            if call_id not in calls:
                continue
            if (
                call_id in step["tool_results"]
                and step["tool_results"][call_id] != result["output"]
            ):
                raise ValueError("Conflicting saved tool results")
            step["tool_results"][call_id] = deepcopy(result["output"])
        messages = values.get("messages", [])
        current = [
            i
            for i, message in enumerate(messages)
            if message.get("type") == "ai" and message.get("id") == response["id"]
        ]
        if current:
            messages = messages[current[-1] + 1 :]
        for message in messages:
            if message.get("type") == "tool" and message.get("tool_call_id") in calls:
                _add_tool_result(step, message["tool_call_id"], message["content"])
    # Count／工具子圖可能已保存、父節點尚未返回；只補既有 Step，不另造 Step。
    for record in records:
        values = record["values"]
        count_step = steps.get((record["thread_id"], str(values.get("request_id"))))
        count = values.get("input_count")
        if count_step is not None and count is not None:
            if count_step["request"] != values.get("request_snapshot"):
                raise ValueError("A saved input count does not match its original request")
            if count_step["input_count"] is not None and count_step["input_count"] != count:
                raise ValueError("Conflicting saved input counts for one request")
            count_step["input_count"] = deepcopy(count)
        if not record.get("checkpoint_ns"):
            continue
        call = values.get("call")
        if not isinstance(call, dict) or "output" not in values:
            continue
        tool_step = steps.get((record["thread_id"], str(values.get("request_id"))))
        if tool_step is None or tool_step["response"] is None:
            continue
        original = next(
            (
                item
                for item in tool_step["response"]["output"]
                if item.get("type") == "function_call" and item["call_id"] == call.get("call_id")
            ),
            None,
        )
        if original is None or original != call:
            raise ValueError("A tool subgraph does not match its original native call")
        operation = values.get("operation_id")
        expected = tool_step["metadata"]["tool_operation_ids"].get(call["call_id"])
        if operation is not None and expected is not None and str(operation) != expected:
            raise ValueError("A tool subgraph does not match its original operation")
        _add_tool_result(tool_step, call["call_id"], values["output"])
    return [redact(step) for step in steps.values()]


def _add_tool_result(step: dict[str, Any], call_id: str, output: Any) -> None:
    if call_id in step["tool_results"] and step["tool_results"][call_id] != output:
        raise ValueError("Conflicting saved tool results")
    step["tool_results"][call_id] = deepcopy(output)


def collect_tool_calls(steps: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Retain call order and distinguish missing output from a recorded empty string."""
    calls = []
    for step in steps:
        response = step["response"]
        if response is None:
            continue
        for index, call in enumerate(response["output"]):
            if call.get("type") != "function_call":
                continue
            call_id = call["call_id"]
            results = step["tool_results"]
            calls.append(
                {
                    "thread_id": step["thread_id"],
                    "request_id": step["request_id"],
                    "response_id": response["id"],
                    "output_index": index,
                    "call_id": call_id,
                    "name": call["name"],
                    "arguments": call["arguments"],
                    "operation_id": step["metadata"]["tool_operation_ids"].get(call_id),
                    "result_state": "recorded" if call_id in results else "not_recorded",
                    "output": results.get(call_id),
                    "receipt_state": "not_recorded",
                }
            )
    return calls
