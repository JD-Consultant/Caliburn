"""Protect count/create equivalence and native continuation at the new boundary."""

import json
from copy import deepcopy

import httpx2
import pytest
from caliburn.adapters.openai_responses import (
    ResponseRequest,
    count_response_input,
    create_response,
    create_responses_client,
)
from completion_contract import structured_request
from jsonschema import ValidationError, validate


def request() -> ResponseRequest:
    return ResponseRequest(
        model="gpt-6-luna",
        instructions="test",
        tools=[],
        input_items=[
            {"role": "user", "content": "synthetic input"},
            {
                "type": "reasoning",
                "id": "r1",
                "summary": [],
                "encrypted_content": "opaque",
            },
            {"type": "function_call_output", "call_id": "c1", "output": "saved"},
        ],
        reasoning_effort="high",
        max_output_tokens=16384,
    )


@pytest.mark.parametrize("role", ["single", "reader"])
def test_count_and_create_both_include_final_schema_without_rewriting_items(role):
    original = request()
    before = deepcopy(original.create_payload())
    wrapped = structured_request(original, role)
    count, create = wrapped.count_payload(), wrapped.create_payload()
    assert count["text"] == create["text"]
    assert create["text"]["format"]["type"] == "json_schema"
    assert create["text"]["format"]["strict"] is True
    assert create["input"] == before["input"]
    assert create["max_output_tokens"] == 16384
    assert original.create_payload() == before
    count["text"]["format"]["schema"].clear()
    assert wrapped.create_payload()["text"]["format"]["schema"]


def test_reader_schema_allows_existing_reference_variants_but_not_missing_task_work():
    schema = structured_request(request(), "reader").create_payload()["text"]["format"][
        "schema"
    ]
    value = {
        "task": {"title": "盤點", "work": "每月盤點"},
        "unknowns": [],
        "references": [
            {"kind": "work_understanding", "target_title": "盤點"},
            {"kind": "work_situation", "target_title": "盤點"},
            {"kind": "interview", "sequences": [2]},
        ],
    }
    validate(value, schema)
    del value["task"]["work"]
    with pytest.raises(ValidationError):
        validate(value, schema)


@pytest.mark.asyncio
async def test_real_sdk_forwards_the_same_schema_and_native_items_on_both_endpoints():
    sent = []

    def respond(http_request):
        sent.append(json.loads(http_request.content))
        if http_request.url.path.endswith("input_tokens"):
            return httpx2.Response(
                200, json={"object": "response.input_tokens", "input_tokens": 123}
            )
        return httpx2.Response(
            200,
            json={
                "id": "resp_test",
                "created_at": 1,
                "model": "gpt-6-luna",
                "object": "response",
                "status": "completed",
                "output": [],
                "parallel_tool_calls": True,
                "tool_choice": "auto",
                "tools": [],
            },
        )

    wrapped = structured_request(request(), "reader")
    async with create_responses_client(
        api_key="offline-only",
        timeout_seconds=1,
        http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(respond)),
    ) as client:
        await count_response_input(client, wrapped)
        await create_response(client, wrapped)
    assert len(sent) == 2
    assert sent[0]["text"] == sent[1]["text"]
    assert sent[1]["text"]["format"]["strict"] is True
    assert sent[0]["input"] == sent[1]["input"] == request().create_payload()["input"]
