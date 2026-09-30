"""Synthetic native HTTP responses for the real SDK, in the requested transport mode."""

import json
from typing import Any

import httpx2


def response_http_reply(request: httpx2.Request, raw: dict[str, Any]) -> httpx2.Response:
    if not json.loads(request.content).get("stream"):
        return httpx2.Response(200, json=raw)
    events: list[dict[str, Any]] = [
        {
            "type": "response.created",
            "sequence_number": 0,
            "response": {**raw, "status": "in_progress", "output": []},
        }
    ]
    for index, item in enumerate(raw["output"]):
        if item["type"] != "message":
            continue
        events.append(
            {
                "type": "response.output_item.added",
                "sequence_number": len(events),
                "output_index": index,
                "item": {**item, "status": "in_progress", "content": []},
            }
        )
        for part_index, part in enumerate(item["content"]):
            if part["type"] != "output_text":
                continue
            events.append(
                {
                    "type": "response.output_text.delta",
                    "sequence_number": len(events),
                    "item_id": item["id"],
                    "output_index": index,
                    "content_index": part_index,
                    "delta": part["text"],
                    "logprobs": [],
                }
            )
        events.append(
            {
                "type": "response.output_item.done",
                "sequence_number": len(events),
                "output_index": index,
                "item": item,
            }
        )
    events.append({"type": "response.completed", "sequence_number": len(events), "response": raw})
    body = "".join(f"data: {json.dumps(event, ensure_ascii=False)}\n\n" for event in events)
    return httpx2.Response(200, headers={"Content-Type": "text/event-stream"}, content=body)
