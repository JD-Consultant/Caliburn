"""具名 SSE 事件拒絕錯配資料，模型通知只保留公開白名單。"""

from typing import Any

import pytest
from pydantic import TypeAdapter, ValidationError

from caliburn.modules.agent.application.events import TurnEvent, model_event


@pytest.mark.parametrize(
    "event,data",
    [
        ("status", {"status": "running"}),
        ("text_delta", {"model_step": 1, "call_id": "call-1"}),
        ("reasoning_summary_delta", {"model_step": 1, "delta": 42}),
        ("tool_call", {"model_step": 1, "delta": "text"}),
        ("resync_required", {"reason": "other"}),
        ("cancellation", {"turn_id": "invalid", "status": "completed"}),
    ],
)
def test_event_name_selects_its_required_payload(
    event: str, data: dict[str, Any]
) -> None:
    with pytest.raises(ValidationError):
        TypeAdapter(TurnEvent).validate_python({"event": event, "data": data})


@pytest.mark.parametrize(
    "sdk_type,public_event",
    [
        ("response.output_text.delta", "text_delta"),
        ("response.reasoning_summary_text.delta", "reasoning_summary_delta"),
    ],
)
def test_model_deltas_only_expose_the_public_projection(
    sdk_type: str, public_event: str
) -> None:
    projected = model_event(
        {
            "type": "custom",
            "data": {
                "execution": {"model_step": 2, "private": "hidden"},
                "event": {"type": sdk_type, "delta": "更新\n內容", "private": "hidden"},
            },
        }
    )
    assert projected is not None
    assert projected.model_dump(mode="json") == {
        "event": public_event,
        "data": {"model_step": 2, "delta": "更新\n內容"},
    }


def test_tool_notice_does_not_expose_sdk_metadata() -> None:
    projected = model_event(
        {
            "type": "custom",
            "data": {
                "execution": {"model_step": 1},
                "event": {
                    "type": "response.output_item.done",
                    "item": {
                        "type": "function_call",
                        "call_id": "call-1",
                        "name": "record_answer",
                        "arguments": '{"answer":"原文"}',
                        "id": "private-sdk-id",
                        "extra": "hidden",
                    },
                },
            },
        }
    )
    assert projected is not None
    assert projected.model_dump(mode="json") == {
        "event": "tool_call",
        "data": {
            "model_step": 1,
            "call_id": "call-1",
            "name": "record_answer",
            "arguments": '{"answer":"原文"}',
        },
    }


@pytest.mark.parametrize("step", [True, 0, -1, 9007199254740992, "1"])
def test_model_notice_ignores_invalid_step_numbers(step: Any) -> None:
    assert (
        model_event(
            {
                "type": "custom",
                "data": {
                    "execution": {"model_step": step},
                    "event": {"type": "response.output_text.delta", "delta": "text"},
                },
            }
        )
        is None
    )
