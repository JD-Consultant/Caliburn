"""Native response routing, not provider acceptance or durable execution."""

import json
from copy import deepcopy
from pathlib import Path

import pytest
from openai.types.responses import Response

from caliburn.agent_execution.response_steps import (
    IncompleteModelResponseError,
    ResponseAction,
    UnsupportedModelResponseError,
    inspect_response_step,
)


@pytest.fixture
def payload() -> dict:
    return json.loads(
        (Path(__file__).parents[1] / "fixtures/native-response.json").read_text(encoding="utf-8")
    )


def test_commentary_and_calls_do_not_complete_the_turn(payload: dict) -> None:
    step = inspect_response_step(Response.model_validate(payload))
    assert step.action == ResponseAction.EXECUTE_TOOLS
    assert [call.call_id for call in step.calls] == ["call_synthetic"]
    assert [message.phase for message in step.messages] == ["commentary"]


def test_multiple_calls_remain_ordered_even_when_final_text_coexists(payload: dict) -> None:
    payload["output"][1]["phase"] = "final_answer"
    second = deepcopy(payload["output"][2])
    second.update(id="fc_second", call_id="call_second", name="update_test_record")
    payload["output"].append(second)
    step = inspect_response_step(Response.model_validate(payload))
    assert step.action == ResponseAction.EXECUTE_TOOLS
    assert [call.call_id for call in step.calls] == ["call_synthetic", "call_second"]


@pytest.mark.parametrize("output_count", [0, 1, 2])
def test_no_final_or_pending_tools_requires_continuation(payload: dict, output_count: int) -> None:
    payload["output"] = payload["output"][:output_count]
    step = inspect_response_step(Response.model_validate(payload))
    assert step.action == ResponseAction.CONTINUE
    assert not step.calls


@pytest.mark.parametrize("refusal", [False, True])
def test_explicit_final_with_no_calls_can_be_delivered(payload: dict, refusal: bool) -> None:
    payload["output"] = payload["output"][:2]
    payload["output"][1]["phase"] = "final_answer"
    if refusal:
        payload["output"][1]["content"] = [{"type": "refusal", "refusal": "合成拒絕"}]
    step = inspect_response_step(Response.model_validate(payload))
    assert step.action == ResponseAction.DELIVER_ANSWER
    assert len(step.messages) == 1  # Never expose reasoning as a public message.


@pytest.mark.parametrize("text", ["", " \n\t"])
@pytest.mark.parametrize("kind", ["output_text", "refusal"])
def test_empty_final_content_cannot_be_delivered(payload: dict, text: str, kind: str) -> None:
    payload["output"] = payload["output"][:2]
    message = payload["output"][1]
    message["phase"] = "final_answer"
    message["content"] = (
        [{"type": kind, "text": text, "annotations": []}]
        if kind == "output_text"
        else [{"type": kind, "refusal": text}]
    )
    assert inspect_response_step(Response.model_validate(payload)).action == ResponseAction.CONTINUE


@pytest.mark.parametrize("status", ["in_progress", "incomplete", "failed", "cancelled", "queued"])
def test_noncompleted_response_cannot_dispatch_tools(payload: dict, status: str) -> None:
    payload["status"] = status
    with pytest.raises(IncompleteModelResponseError):
        inspect_response_step(Response.model_validate(payload))


@pytest.mark.parametrize("item_index", [0, 1, 2])
def test_incomplete_item_blocks_even_a_completed_response(payload: dict, item_index: int) -> None:
    payload["output"][item_index]["status"] = "incomplete"
    with pytest.raises(IncompleteModelResponseError):
        inspect_response_step(Response.model_validate(payload))


def test_duplicate_call_identity_is_not_silently_deduplicated(payload: dict) -> None:
    payload["output"].append(deepcopy(payload["output"][2]))
    with pytest.raises(UnsupportedModelResponseError):
        inspect_response_step(Response.model_validate(payload))


@pytest.mark.parametrize(
    "extension",
    [
        {"namespace": "unconfigured"},
        {"async": True},
        {"caller": {"type": "program", "caller_id": "program_1"}},
    ],
)
def test_unsupported_execution_mode_does_not_reach_local_tools(
    payload: dict, extension: dict
) -> None:
    payload["output"][2].update(extension)
    with pytest.raises(UnsupportedModelResponseError):
        inspect_response_step(Response.model_validate(payload))


def test_missing_phase_is_not_guessed_from_visible_text(payload: dict) -> None:
    del payload["output"][1]["phase"]
    with pytest.raises(UnsupportedModelResponseError):
        inspect_response_step(Response.model_validate(payload))


def test_unconfigured_builtin_tool_is_not_silently_ignored(payload: dict) -> None:
    payload["output"].append(
        {"type": "file_search_call", "id": "fs_1", "queries": ["synthetic"], "status": "completed"}
    )
    with pytest.raises(UnsupportedModelResponseError):
        inspect_response_step(Response.model_validate(payload))
