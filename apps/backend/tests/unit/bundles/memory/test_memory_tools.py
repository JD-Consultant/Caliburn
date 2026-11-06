"""Memory 工具與模型完成協定。"""

import json
from typing import cast
from uuid import uuid4

import pytest
from langchain_core.utils.function_calling import convert_to_openai_function
from langgraph.checkpoint.base import CheckpointMetadata
from langgraph.types import StateSnapshot
from openai.types.responses import Response

from caliburn.bundles.memory import create_bundle
from caliburn.bundles.memory.completion import (
    InvalidMemoryCompletion,
    completed_memory_request,
    final_text,
    require_complete,
)
from caliburn.bundles.memory.tool_contracts import UpdateSituation
from caliburn.modules.agent.state import CancelStatus
from tests.unit.modules.agent.offline_openai import message, response_payload


def test_each_role_only_declares_its_tools() -> None:
    a, b1, b2 = (
        tuple(tool for plugin in create_bundle(config).plugins for tool in plugin.tools)
        for config in ({}, {"role": "situation"}, {"role": "understanding"})
    )
    situations = {"read_work_situation_map", "read_work_situation"}
    understandings = {"read_work_understanding_map", "read_work_understanding"}
    assert {tool.name for tool in a} == situations | understandings | {
        "request_memory_consolidation",
        "read_interview",
    }
    assert {tool.name for tool in b1} == situations | {
        "create_work_situation",
        "update_work_situation",
        "delete_work_situation",
        "read_interview",
    }
    assert {tool.name for tool in b2} == situations | understandings | {
        "create_work_understanding",
        "update_work_understanding",
        "delete_work_understanding",
        "read_interview",
    }
    for tool in (*a, *b1, *b2):
        wire = convert_to_openai_function(tool, strict=True)
        assert wire["parameters"]["additionalProperties"] is False
        assert "runtime" not in json.dumps(wire["parameters"])


def test_situation_update_disallows_understanding_references_and_ids() -> None:
    arguments = {
        "target_title": " A ",
        "changes": [
            {"field": "title", "value": " a "},
            {
                "field": "interview_references",
                "add": ["message_101"],
                "remove": ["message_32"],
            },
        ],
    }
    assert UpdateSituation.model_validate(arguments).target_title == " A "
    with pytest.raises(ValueError):
        UpdateSituation.model_validate(
            {
                "target_title": "A",
                "changes": [{"field": "interview_references", "add": [1]}],
            }
        )
    with pytest.raises(ValueError):
        UpdateSituation.model_validate({**arguments, "workspace_id": "other"})
    with pytest.raises(ValueError):
        UpdateSituation.model_validate(
            {
                "target_title": "A",
                "changes": [
                    {"field": "work_situation_references", "add": ["a"]},
                ],
            }
        )
    with pytest.raises(ValueError):
        UpdateSituation.model_validate(
            {
                "target_title": "A",
                "changes": [
                    {"field": "body", "diff": "@@\n-x\n+y"},
                    {"field": "body", "diff": "@@\n-y\n+z"},
                ],
            }
        )


@pytest.mark.parametrize(
    "text",
    [
        '{"status":"complete","status":"complete"}',
        '{"status":"complete","extra":1}',
        "完成",
        '"""{"status":"complete"}"""',
        '["complete"]',
        '{"status":"failed"}',
    ],
)
def test_ambiguous_or_partial_completion_is_rejected(text: str) -> None:
    with pytest.raises(InvalidMemoryCompletion):
        require_complete(text)


def test_exact_completion_allows_json_whitespace() -> None:
    require_complete(' { "status" : "complete" }\n')


@pytest.mark.parametrize(
    "output",
    [
        [
            {
                **message(),
                "content": [{"type": "refusal", "refusal": '{"status":"complete"}'}],
            }
        ],
        [message(text='{"status":"complete"}'), message(text='{"status":"complete"}')],
        [
            {
                **message(),
                "content": [
                    {
                        "type": "output_text",
                        "text": '{"status":"complete"}',
                        "annotations": [],
                    },
                    {"type": "refusal", "refusal": "拒絕"},
                ],
            }
        ],
    ],
    ids=["refusal", "multiple_finals", "mixed_content"],
)
def test_analyst_completion_requires_one_pure_text_final(
    output: list[dict[str, object]],
) -> None:
    response = Response.model_validate({**response_payload(output), "usage": None})
    assert final_text(response) is None


@pytest.mark.parametrize("cancel_status", [None, "pending", "completed"])
def test_only_uncancelled_terminal_turn_admits_saved_intent(
    cancel_status: CancelStatus | None,
) -> None:
    turn_id = uuid4()
    payload = {**response_payload(), "usage": None}
    snapshot = StateSnapshot(
        values={
            "turn_id": turn_id,
            "turn_completed": True,
            "model_response": Response.model_validate(payload),
            "memory_consolidation_requested": True,
            "cancel_status": cancel_status,
        },
        next=(),
        config={},
        metadata=cast(
            CheckpointMetadata,
            {"source": "update" if cancel_status else "loop", "turn_id": str(turn_id)},
        ),
        created_at=None,
        parent_config=None,
        tasks=(),
        interrupts=(),
    )
    assert completed_memory_request(snapshot) == (
        turn_id if cancel_status is None else None
    )
