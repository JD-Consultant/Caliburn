"""OpenRouter Chat Completions fixtures; never sent outside MockTransport."""

import json


MODEL = "openai/gpt-5.6-luna"


def reply(identity, tool=None, arguments=None, *, text="合成顧問回覆"):
    message = {"role": "assistant", "content": text if tool is None else ""}
    if tool is not None:
        message["tool_calls"] = [{
            "id": f"call_{identity}",
            "type": "function",
            "function": {"name": tool, "arguments": json.dumps(
                arguments or {}, ensure_ascii=False, separators=(",", ":"))},
        }]
    return {
        "id": identity,
        "object": "chat.completion",
        "created": 1,
        "model": MODEL,
        "system_fingerprint": None,
        "provider": "OpenAI",
        "choices": [{"index": 0, "message": message,
                     "finish_reason": "tool_calls" if tool is not None else "stop"}],
        "usage": {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30},
        "openrouter_metadata": {
            "attempt": 1,
            "endpoints": {"available": [{
                "provider": "OpenAI", "model": MODEL, "selected": True,
            }], "total": 1},
            "is_byok": False,
            "region": None,
            "requested": MODEL,
            "strategy": "provider-only",
            "summary": "synthetic OpenAI route",
        },
    }


def truncated(identity):
    value = reply(identity, text="未完成")
    value["choices"][0]["finish_reason"] = "length"
    return value


def refused(identity):
    value = reply(identity, text="")
    value["choices"][0]["message"]["refusal"] = "synthetic refusal"
    return value


def system_blocks(payload):
    system = next((message for message in payload["messages"] if message["role"] == "system"), None)
    if system is None:
        return []
    return system["content"] if isinstance(system["content"], list) else [
        {"type": "text", "text": system["content"]}]
