"""Synthetic OpenAI Responses replies for the consultant, validated by the SDK.

Test support only. Every body here is checked against the installed official
`Response` schema, so a fixture cannot drift into a shape the provider would
never send. Nothing in this module reaches a network: callers hand the body to
an in-process transport.

The consultant is a bounded tool-calling agent, so a reply is either a final
message or exactly one function call -- this product never allows parallel
tool calls.
"""

import json

from openai.types.responses import Response

MODEL = "gpt-5.6-luna"


def body(output: list[dict], *, status: str = "completed", incomplete: dict | None = None,
         identity: str = "synthetic") -> dict:
    # The adapter takes the reply's id from the response, so each reply needs
    # its own: two turns sharing one id would look like one saved response.
    return Response.model_validate({
        "id": f"resp_{identity}", "object": "response", "created_at": 1788624000,
        "model": MODEL, "status": status, "output": output,
        "incomplete_details": incomplete, "parallel_tool_calls": False,
        "tool_choice": "auto", "tools": [], "store": False,
        "reasoning": {"effort": "high", "context": "all_turns"},
        "usage": {"input_tokens": 100,
                  "input_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 0},
                  "output_tokens": 20, "output_tokens_details": {"reasoning_tokens": 10},
                  "total_tokens": 120},
    }).model_dump(mode="json", exclude_none=True)


def reply(identity: str, name: str | None = None, arguments: dict | None = None,
          *, text: str = "合成回覆") -> dict:
    """One consultant reply: a final message, or one tool call."""
    if name is None:
        return body([{"type": "message", "id": f"msg_{identity}", "role": "assistant",
                      "status": "completed", "phase": "final_answer",
                      "content": [{"type": "output_text", "text": text, "annotations": []}]}],
                    identity=identity)
    return body([{"type": "function_call", "id": f"fc_{identity}", "call_id": f"call_{identity}",
                  "name": name, "arguments": json.dumps(arguments or {}, ensure_ascii=False),
                  "status": "completed"}], identity=identity)


def truncated(identity: str) -> dict:
    """A reply cut off at the output ceiling: never a short success."""
    return body([{"type": "message", "id": f"msg_{identity}", "role": "assistant",
                  "status": "incomplete", "phase": "final_answer",
                  "content": [{"type": "output_text", "text": "合成回覆被截", "annotations": []}]}],
                status="incomplete", incomplete={"reason": "max_output_tokens"}, identity=identity)


def refused(identity: str) -> dict:
    return body([{"type": "message", "id": f"msg_{identity}", "role": "assistant",
                  "status": "completed", "phase": "final_answer",
                  "content": [{"type": "refusal", "refusal": "無法協助。"}]}], identity=identity)


def system_blocks(payload: dict) -> list[dict]:
    """The App-supplied system blocks inside one Responses request.

    The Responses API has no separate `system` field: the system message is the
    first `input` item with role `system` or `developer`. Reading it from the
    request is how a test checks what the App really told the model, without
    trusting the App's own view of it.
    """
    for item in payload.get("input", []):
        if isinstance(item, dict) and item.get("role") in {"system", "developer"}:
            content = item.get("content")
            if isinstance(content, str):
                return [{"type": "text", "text": content}]
            return [{"type": "text", "text": block.get("text", "")}
                    for block in content or [] if isinstance(block, dict)]
    return []
