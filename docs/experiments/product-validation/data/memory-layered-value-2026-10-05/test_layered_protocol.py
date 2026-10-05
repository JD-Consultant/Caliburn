"""Catch future-data leakage, false unread references and lost native items."""

import json
from types import SimpleNamespace

import pytest
from layered_protocol import Workspace, reading_context, run_history_episode
from openai.types.responses import Response


def workspace():
    value = Workspace(
        "two_layer",
        [
            {"interview_sequence": 1, "role": "assistant", "text": "誰核准？"},
            {"interview_sequence": 2, "role": "user", "text": "尚未確認。"},
            {"interview_sequence": 3, "role": "user", "text": "後來確認是主管。"},
        ],
    )
    value.read_through = 2
    return value


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


def final_item(sequence):
    value = {
        "task": {"title": "變更", "work": "核准人尚未確認。"},
        "unknowns": ["核准人"],
        "references": [{"kind": "interview", "sequences": [sequence]}],
    }
    return {
        "type": "message",
        "id": "msg_final",
        "role": "assistant",
        "status": "completed",
        "phase": "final_answer",
        "content": [
            {"type": "output_text", "text": json.dumps(value), "annotations": []}
        ],
    }


SETTINGS = SimpleNamespace(
    model="gpt-6-luna",
    reasoning_effort="high",
    max_output_tokens=16384,
    max_model_steps=4,
)


def test_history_context_contains_only_visible_original_messages():
    value = reading_context(workspace(), "整理變更", arm="full_history")
    assert set(value) == {"question", "historical_interview"}
    assert [m["interview_sequence"] for m in value["historical_interview"]] == [1, 2]
    assert value["historical_interview"][1]["text"] == "尚未確認。"
    assert "後來" not in json.dumps(value, ensure_ascii=False)


def test_layered_reader_receives_maps_without_original_history():
    value = reading_context(workspace(), "整理變更", arm="layered")
    assert set(value) == {"question", "work_understanding_map", "work_situation_map"}
    assert "尚未確認" not in json.dumps(value, ensure_ascii=False)


@pytest.mark.asyncio
async def test_preloaded_history_is_citable_and_native_commentary_is_replayed():
    ws = workspace()
    calls = []

    async def send(request):
        calls.append(request.create_payload())
        if len(calls) == 1:
            return response(
                [
                    {
                        "type": "reasoning",
                        "id": "rs_test",
                        "summary": [],
                        "encrypted_content": "opaque-test",
                    },
                    {
                        "type": "message",
                        "id": "msg_note",
                        "role": "assistant",
                        "status": "completed",
                        "phase": "commentary",
                        "content": [
                            {
                                "type": "output_text",
                                "text": "正在核對",
                                "annotations": [],
                            }
                        ],
                    },
                ]
            )
        return response([final_item(2)])

    context = reading_context(ws, "整理變更", arm="full_history")
    result = await run_history_episode(ws, "method", context, SETTINGS, send)
    assert result["final"]["references"] == [{"kind": "interview", "sequences": [2]}]
    assert result["tool_calls"] == []
    assert calls[0]["tools"] == []
    items = calls[1]["input"]
    assert len([item for item in items if item.get("role") == "user"]) == 1
    assert items[1]["encrypted_content"] == "opaque-test"
    assert items[2]["phase"] == "commentary"


@pytest.mark.asyncio
async def test_full_history_reader_rejects_reference_to_future_message():
    ws = workspace()

    async def send(request):
        return response([final_item(3)])

    with pytest.raises(ValueError, match="unread_reference"):
        await run_history_episode(
            ws,
            "method",
            reading_context(ws, "整理", arm="full_history"),
            SETTINGS,
            send,
        )
