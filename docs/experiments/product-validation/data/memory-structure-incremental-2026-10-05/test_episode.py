"""Test native continuation before implementing the loop, with a fake transport only."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from episode import run_episode
from openai.types.responses import Response
from workspace import Workspace


def response(output):
    return Response.model_validate(
        {
            "id": "resp_test",
            "created_at": 1,
            "model": "gpt-6-luna",
            "object": "response",
            "status": "completed",
            "output": output,
            "parallel_tool_calls": True,
            "tool_choice": "auto",
            "tools": [],
        }
    )


@pytest.mark.asyncio
async def test_native_items_and_sequential_calls_replayed_without_duplicate_context():
    material = json.loads(
        (Path(__file__).parent / "materials.json").read_text(encoding="utf-8")
    )
    workspace = Workspace("one_collection", material["messages"])
    workspace.read_through = 10
    create = {
        "title": "訂單",
        "description": "前端防重送",
        "body": "甲防重複送單",
        "interview_references": [2],
    }
    first = response(
        [
            {
                "type": "reasoning",
                "id": "reasoning_test",
                "summary": [],
                "encrypted_content": "opaque-test",
            },
            {
                "type": "message",
                "id": "msg_progress",
                "role": "assistant",
                "status": "completed",
                "phase": "commentary",
                "content": [
                    {"type": "output_text", "text": "先整理。", "annotations": []}
                ],
            },
            {
                "type": "function_call",
                "call_id": "call_1",
                "name": "create_work_understanding",
                "arguments": json.dumps(create),
            },
            {
                "type": "function_call",
                "call_id": "call_2",
                "name": "read_work_understanding",
                "arguments": json.dumps({"target_title": "訂單"}),
            },
        ]
    )
    final = response(
        [
            {
                "type": "message",
                "id": "msg_final",
                "role": "assistant",
                "status": "completed",
                "phase": "final_answer",
                "content": [
                    {
                        "type": "output_text",
                        "text": '{"status":"complete"}',
                        "annotations": [],
                    }
                ],
            }
        ]
    )
    requests = []

    async def send(request):
        requests.append(request.create_payload())
        return first if len(requests) == 1 else final

    events = []
    settings = SimpleNamespace(
        model="gpt-6-luna",
        reasoning_effort="high",
        max_output_tokens=16384,
        max_model_steps=64,
        max_tool_calls_per_step=32,
    )
    result = await run_episode(
        workspace,
        "single",
        "instructions",
        {"test": "context"},
        settings,
        send,
        events.append,
    )
    assert result["final"] == {"status": "complete"}
    continuation = requests[1]["input"]
    assert len([item for item in continuation if item.get("role") == "user"]) == 1
    assert continuation[1]["encrypted_content"] == "opaque-test"
    assert continuation[2]["phase"] == "commentary"
    assert [
        item["call_id"]
        for item in continuation
        if item.get("type") == "function_call_output"
    ] == ["call_1", "call_2"]
    assert json.loads(continuation[-1]["output"])["body"] == "甲防重複送單"
