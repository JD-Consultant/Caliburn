"""Legal compact output must pass the research hook unchanged."""

import json
from pathlib import Path

import httpx2
import pytest
from caliburn.adapters.openai_responses import ResponseRequest
from main import StudyRecorder


@pytest.mark.asyncio
async def test_retained_user_message_in_compact_output_passes_hook_unchanged():
    recorder = StudyRecorder(Path("unused-no-file-written"))
    events = []
    recorder.event = events.append
    template = ResponseRequest(
        model="gpt-6-luna",
        instructions="fixed instructions",
        input_items=[],
        tools=[],
        reasoning_effort="high",
        max_output_tokens=16_384,
    )
    count_payload = template.count_payload()
    recorder.allowance.record_count(count_payload, 20_000)
    request_payload = {"model": "gpt-6-luna", "input": [], "service_tier": "default"}
    recorder.allowance.admit("/v1/responses/compact", request_payload)
    payload = {
        "id": "cmp_synthetic",
        "object": "response.compaction",
        "created_at": 1,
        "output": [
            {
                "role": "user",
                "type": "message",
                "content": [{"type": "input_text", "text": "retained original"}],
            },
            {"id": "cmp_item", "type": "compaction", "encrypted_content": "opaque"},
        ],
        "usage": {
            "input_tokens": 20_000,
            "output_tokens": 500,
            "total_tokens": 20_500,
            "input_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 0},
            "output_tokens_details": {"reasoning_tokens": 100},
        },
    }
    response = httpx2.Response(
        200,
        json=payload,
        request=httpx2.Request(
            "POST",
            "https://api.openai.com/v1/responses/compact",
            content=json.dumps(request_payload),
        ),
    )
    await recorder.response(response)
    assert response.json() == payload
    assert recorder.allowance.pending == {}
    assert 0 < recorder.allowance.occupied_usd < 1
    assert events[0]["payload"]["output"][0] == payload["output"][0]


@pytest.mark.asyncio
async def test_count_response_without_rate_headers_does_not_erase_generation_snapshot():
    recorder = StudyRecorder(Path("unused-no-file-written"))
    events = []
    recorder.event = events.append
    recorder.headers = {
        "x-ratelimit-limit-tokens": "200000",
        "x-ratelimit-remaining-tokens": "200000",
    }
    timestamp = recorder.received_at
    request = ResponseRequest(
        model="gpt-6-luna",
        instructions="fixed",
        input_items=[],
        tools=[],
        reasoning_effort="high",
        max_output_tokens=16_384,
    )
    response = httpx2.Response(
        200,
        json={"input_tokens": 50_000},
        request=httpx2.Request(
            "POST", "https://api.openai.com/v1/responses/input_tokens", json=request.count_payload()
        ),
    )
    await recorder.response(response)
    assert recorder.headers["x-ratelimit-limit-tokens"] == "200000"
    assert recorder.received_at == timestamp
    assert events[0]["rate_headers"] == {}
