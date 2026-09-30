"""Deterministic scripted provider for browser and HTTP journeys (test-only, never product code).

It answers the real Responses wire through an httpx MockTransport: input-token counts and
streamed or plain responses, so the product's own SDK path runs unchanged. The script is
chosen only from the employee's newest input, so a test states what should happen inside
the text it submits:

* ``職稱：X；單位：Y；主管：Z；目的：W`` (any subset) records those profile fields, sourced
  from the current input, then answers with one question.
* ``[[hold]]`` holds the Turn's last response: it streams a commentary line, then waits for
  a permit before finishing, so a test can act while the Turn is genuinely processing.
  With profile fields the tool step runs first, so a candidate edit exists during the hold.
* ``[[reject]]`` is refused like a known provider rejection.
* Text with none of these gets one clarifying question and no tool call.

This is a synthetic double for UI, transport and control journeys. It says nothing about
model quality, provider acceptance or real timing.
"""

import asyncio
import json
import re
from collections.abc import AsyncIterator
from typing import Any

import httpx2
from fastapi import APIRouter

PROFILE_LABELS = {
    "職稱": "job_title",
    "單位": "organization_unit",
    "主管": "reports_to",
    "目的": "purpose",
}
HOLD_MARKER = "[[hold]]"
REJECT_MARKER = "[[reject]]"
COMMENTARY_HOLD_TEXT = "我需要一點時間整理，請稍候。"
COMMENTARY_RECORD_TEXT = "我先把你剛說的基本資料記到 JD。"
QUESTION_TEXT = "了解。可以說說你最近一次實際做的工作，從收到需求開始是怎麼進行的？"


def profile_fields(text: str) -> dict[str, str]:
    """Read ``label：value`` directives; a value ends at a separator or line break."""
    found: dict[str, str] = {}
    for label, field in PROFILE_LABELS.items():
        match = re.search(rf"{label}[：:]\s*([^；;。\n]+)", text)
        if match:
            found[field] = match.group(1).strip()
    return found


class ScriptedModel:
    def __init__(self, *, chunk_delay_seconds: float = 0.05) -> None:
        self.chunk_delay_seconds = chunk_delay_seconds
        self.permits = asyncio.Semaphore(0)
        self.waiting = 0
        self._waiting_changed = asyncio.Condition()
        self.responses_sent = 0
        self.counts_sent = 0
        self._sequence = 0

    async def handle(self, request: httpx2.Request) -> httpx2.Response:
        payload = json.loads(request.content)
        if request.url.path.endswith("/input_tokens"):
            self.counts_sent += 1
            return httpx2.Response(
                200, json={"object": "response.input_tokens", "input_tokens": 500}
            )
        if not request.url.path.endswith("/responses"):
            return _error(404, "not_found", "This path is not scripted")
        text, tool_steps = _current_input(payload["input"])
        if REJECT_MARKER in text:
            return _error(400, "invalid_request", "Synthetic known rejection")
        self._sequence += 1
        self.responses_sent += 1
        raw = _raw_response(self._sequence, self._output(self._sequence, text, tool_steps))
        if not payload.get("stream"):
            return httpx2.Response(200, json=raw)
        hold = _holds(text, tool_steps)
        return httpx2.Response(
            200,
            headers={"Content-Type": "text/event-stream"},
            stream=_EventStream(self._events(raw, hold)),
        )

    def _output(self, number: int, text: str, tool_steps: int) -> list[dict[str, Any]]:
        reasoning = {
            "id": f"rs_{number}",
            "type": "reasoning",
            "summary": [],
            "status": "completed",
            "encrypted_content": "synthetic-opaque-not-real-reasoning",
        }
        fields = profile_fields(text)
        if _holds(text, tool_steps):
            return [
                reasoning,
                _message(number, "commentary", COMMENTARY_HOLD_TEXT),
                _message(number, "final_answer", _answer(fields)),
            ]
        if fields and tool_steps == 0:
            changes = [
                change
                for field, value in fields.items()
                for change in (
                    {"action": "set_field", "field": field, "value": value},
                    {"action": "add_source", "field": field, "source": {"kind": "current_input"}},
                )
            ]
            return [
                reasoning,
                _message(number, "commentary", COMMENTARY_RECORD_TEXT),
                {
                    "id": f"fc_{number}",
                    "type": "function_call",
                    "call_id": f"call_{number}",
                    "name": "revise_jd_profile",
                    "arguments": json.dumps({"changes": changes}, ensure_ascii=False),
                    "status": "completed",
                },
            ]
        return [reasoning, _message(number, "final_answer", _answer(fields))]

    async def _events(self, raw: dict[str, Any], hold: bool) -> AsyncIterator[bytes]:
        sequence = 0

        def frame(event: dict[str, Any]) -> bytes:
            nonlocal sequence
            event = {**event, "sequence_number": sequence}
            sequence += 1
            return f"data: {json.dumps(event, ensure_ascii=False)}\n\n".encode()

        yield frame(
            {"type": "response.created", "response": {**raw, "status": "in_progress", "output": []}}
        )
        waiting_for_permit = hold
        for index, item in enumerate(raw["output"]):
            if item["type"] != "message":
                continue
            if item["phase"] != "commentary" and waiting_for_permit:
                await self._wait_for_permit()
                waiting_for_permit = False
            yield frame(
                {
                    "type": "response.output_item.added",
                    "output_index": index,
                    "item": {**item, "status": "in_progress", "content": []},
                }
            )
            for part_index, part in enumerate(item["content"]):
                for chunk in _chunks(part["text"]):
                    yield frame(
                        {
                            "type": "response.output_text.delta",
                            "item_id": item["id"],
                            "output_index": index,
                            "content_index": part_index,
                            "delta": chunk,
                            "logprobs": [],
                        }
                    )
                    await asyncio.sleep(self.chunk_delay_seconds)
            yield frame({"type": "response.output_item.done", "output_index": index, "item": item})
        if waiting_for_permit:
            await self._wait_for_permit()
        yield frame({"type": "response.completed", "response": raw})

    async def until_waiting(self, count: int = 1) -> None:
        """Return once at least this many responses are held for a permit."""
        async with self._waiting_changed:
            await self._waiting_changed.wait_for(lambda: self.waiting >= count)

    async def _wait_for_permit(self) -> None:
        async with self._waiting_changed:
            self.waiting += 1
            self._waiting_changed.notify_all()
        try:
            await self.permits.acquire()
        finally:
            self.waiting -= 1

    def control_router(self) -> APIRouter:
        """Test-only control surface, mounted by the scripted backend and nowhere else."""
        router = APIRouter(prefix="/__script")

        @router.get("/state")
        async def state() -> dict[str, int]:
            return {
                "waiting": self.waiting,
                "responses": self.responses_sent,
                "counts": self.counts_sent,
            }

        @router.post("/release")
        async def release() -> dict[str, bool]:
            # A permit with nobody waiting would silently let the next hold through.
            if self.waiting == 0:
                return {"released": False}
            self.permits.release()
            return {"released": True}

        return router


class _EventStream(httpx2.AsyncByteStream):
    def __init__(self, chunks: AsyncIterator[bytes]) -> None:
        self._chunks = chunks

    async def __aiter__(self) -> AsyncIterator[bytes]:
        async for chunk in self._chunks:
            yield chunk


def _holds(text: str, tool_steps: int) -> bool:
    """Hold the Turn's last response: after the profile tool step when there is one."""
    return HOLD_MARKER in text and tool_steps == (1 if profile_fields(text) else 0)


def _answer(fields: dict[str, str]) -> str:
    if not fields:
        return QUESTION_TEXT
    return f"已記下：{'、'.join(fields.values())}。{QUESTION_TEXT}"


def _current_input(input_items: list[dict[str, Any]]) -> tuple[str, int]:
    """The newest plain user text is the employee's input; tool outputs after it are Steps."""
    for index in range(len(input_items) - 1, -1, -1):
        item = input_items[index]
        if item.get("role") == "user" and isinstance(item.get("content"), str):
            later = input_items[index + 1 :]
            return item["content"], sum(
                1 for entry in later if entry.get("type") == "function_call_output"
            )
    raise ValueError("The scripted provider needs a user message")


def _message(number: int, phase: str, text: str) -> dict[str, Any]:
    return {
        "id": f"msg_{number}_{phase}",
        "type": "message",
        "role": "assistant",
        "status": "completed",
        "phase": phase,
        "content": [{"type": "output_text", "text": text, "annotations": []}],
    }


def _chunks(text: str, size: int = 6) -> list[str]:
    return [text[start : start + size] for start in range(0, len(text), size)] or [""]


def _raw_response(number: int, output: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "id": f"resp_scripted_{number}",
        "object": "response",
        "created_at": 1790630400 + number,
        "status": "completed",
        "model": "gpt-6-luna",
        "store": False,
        "parallel_tool_calls": False,
        "tool_choice": "auto",
        "tools": [],
        "reasoning": {"context": "all_turns", "effort": "medium"},
        "service_tier": "default",
        "output": output,
        "usage": {
            "input_tokens": 400,
            "input_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 0},
            "output_tokens": 40,
            "output_tokens_details": {"reasoning_tokens": 8},
            "total_tokens": 440,
        },
    }


def _error(status: int, code: str, message: str) -> httpx2.Response:
    return httpx2.Response(
        status,
        json={
            "error": {
                "message": message,
                "type": "invalid_request_error",
                "param": None,
                "code": code,
            }
        },
    )
