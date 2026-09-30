"""Preserve provider originals separately from the supported outgoing item projection.

Any is confined to the SDK/JSON serialization boundary. No business state is inferred.
"""

from collections.abc import Sequence
from copy import deepcopy
from typing import Any

from openai.types.responses import Response, ResponseFunctionToolCall
from openai.types.responses.compacted_response import CompactedResponse
from openai.types.responses.response_input_item_param import FunctionCallOutput
from openai.types.responses.response_usage import ResponseUsage

type NativeSnapshot = dict[str, Any]
type NativeItems = list[dict[str, Any]]


def snapshot_response(response: Response) -> dict[str, Any]:
    """Capture every received field, preserving aliases and unknown provider metadata."""
    return response.model_dump(mode="json", by_alias=True, exclude_unset=True)


def restore_response(snapshot: dict[str, Any]) -> Response:
    """Validate executable content; preserve partial billing data with native SDK semantics."""
    usage = snapshot.get("usage")
    if isinstance(usage, dict):
        # SDK replies may omit billing details. Keep them absent, not fabricated as zero;
        # the pricing owner separately decides whether they support a cost estimate.
        snapshot = {**snapshot, "usage": ResponseUsage.model_construct(**usage)}
    return Response.model_validate(snapshot)


def response_input_items(response: Response) -> list[dict[str, Any]]:
    """Project whole output items, excluding only top-level output status per official example.

    The original snapshot still retains status. Remote acceptance is a separate provider gate.
    """
    return [
        item.model_dump(mode="json", by_alias=True, exclude_unset=True, exclude={"status"})
        for item in response.output
    ]


def snapshot_compaction(response: CompactedResponse) -> dict[str, Any]:
    """Capture the entire compaction result before Runtime adopts its complete output window."""
    # SDK output unions are narrower than retained inputs (e.g. user messages). Preserve
    # the received fields; avoid emitting schema warnings containing private input text.
    return response.to_dict(mode="json", warnings=False)


def compaction_input_items(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    """Return every compacted output item, including retained items, in original order."""
    output = snapshot.get("output")
    if not isinstance(output, list) or any(not isinstance(item, dict) for item in output):
        raise ValueError("The saved compaction result must contain a complete output window")
    return deepcopy(output)


def function_result_item(call: ResponseFunctionToolCall, output: str) -> FunctionCallOutput:
    """Pair one real tool result with its original direct call, never a generated call ID."""
    result: FunctionCallOutput = {
        "type": "function_call_output",
        "call_id": call.call_id,
        "output": output,
    }
    if call.caller is not None:
        if call.caller.type != "direct":
            raise ValueError("Only direct calls are supported by this result adapter")
        result["caller"] = {"type": "direct"}
    return result


def require_result_order(
    calls: Sequence[ResponseFunctionToolCall], results: Sequence[FunctionCallOutput]
) -> None:
    """A saved prefix may be incomplete, but cannot skip, duplicate or reorder calls."""
    if len(results) > len(calls):
        raise ValueError("There are more tool results than original calls")
    for call, result in zip(calls, results, strict=False):
        if result["type"] != "function_call_output" or result["call_id"] != call.call_id:
            raise ValueError("Tool results must follow the original call order")
