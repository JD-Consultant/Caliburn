"""The scripted provider behaves like the real wire on the product's own SDK path."""

import asyncio
import json

import httpx2
import pytest
from openai import BadRequestError

from caliburn.adapters.openai_responses import (
    ResponseRequest,
    count_response_input,
    create_response,
    create_responses_client,
)
from caliburn.adapters.response_serialization import function_result_item
from caliburn.adapters.response_streaming import PublicCommentaryUpdate
from caliburn.agent_execution.response_steps import ResponseAction, inspect_response_step
from tests.fixtures.scripted_model import ScriptedModel, profile_fields


def client_for(model: ScriptedModel):
    return create_responses_client(
        api_key="synthetic-not-a-real-key",
        timeout_seconds=5,
        http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(model.handle)),
    )


def request_for(text: str, *later_items: dict, stream: bool = True) -> ResponseRequest:
    return ResponseRequest(
        model="gpt-6-luna",
        instructions="scripted",
        input_items=[
            {"role": "user", "content": "App 資料訊息"},
            {"role": "user", "content": text},
            *later_items,
        ],
        tools=[],
        reasoning_effort="low",
        max_output_tokens=512,
        stream=stream,
    )


def test_profile_fields_are_read_by_label_in_any_order_and_subset() -> None:
    assert profile_fields(
        "職稱：前端工程師；單位：產品團隊。主管：李主任\n目的：把設計稿做成頁面"
    ) == {
        "job_title": "前端工程師",
        "organization_unit": "產品團隊",
        "reports_to": "李主任",
        "purpose": "把設計稿做成頁面",
    }
    assert profile_fields("我的主管:王經理") == {"reports_to": "王經理"}
    assert profile_fields("今天做了一些事") == {}


async def test_profile_turn_records_each_field_from_current_input_then_answers_once() -> None:
    model = ScriptedModel()
    async with client_for(model) as client:
        first = await create_response(client, request_for("職稱：前端工程師；主管：李主任"))
        step = inspect_response_step(first)
        assert step.action == ResponseAction.EXECUTE_TOOLS
        assert [call.name for call in step.calls] == ["revise_jd_profile"]
        assert json.loads(step.calls[0].arguments)["changes"] == [
            {"action": "set_field", "field": "job_title", "value": "前端工程師"},
            {"action": "add_source", "field": "job_title", "source": {"kind": "current_input"}},
            {"action": "set_field", "field": "reports_to", "value": "李主任"},
            {"action": "add_source", "field": "reports_to", "source": {"kind": "current_input"}},
        ]
        result = function_result_item(step.calls[0], "已更新")
        second = await create_response(
            client,
            request_for("職稱：前端工程師；主管：李主任", *first_items(first), dict(result)),
        )
        final = inspect_response_step(second)
        assert final.action == ResponseAction.DELIVER_ANSWER
        assert "前端工程師" in second.output_text and "李主任" in second.output_text
    assert model.responses_sent == 2


def first_items(response) -> list[dict]:
    return [
        item.model_dump(mode="json", by_alias=True, exclude_unset=True, exclude={"status"})
        for item in response.output
    ]


async def test_text_without_directives_gets_one_question_and_no_tool() -> None:
    async with client_for(ScriptedModel()) as client:
        response = await create_response(client, request_for("今天主要在做網站頁面"))
    step = inspect_response_step(response)
    assert step.action == ResponseAction.DELIVER_ANSWER
    assert not step.calls
    assert response.output_text.strip().endswith("？")


async def test_hold_streams_commentary_then_waits_for_a_permit() -> None:
    model = ScriptedModel(chunk_delay_seconds=0)
    seen: list[PublicCommentaryUpdate] = []
    async with client_for(model) as client:
        turn = asyncio.create_task(
            create_response(client, request_for("請稍候 [[hold]]"), on_commentary=seen.append)
        )
        async with asyncio.timeout(5):
            await model.until_waiting()
        assert seen and seen[-1].text
        assert not turn.done()
        model.permits.release()
        response = await asyncio.wait_for(turn, 5)
    step = inspect_response_step(response)
    assert step.action == ResponseAction.DELIVER_ANSWER
    assert [message.phase for message in step.messages] == ["commentary", "final_answer"]
    assert model.waiting == 0


async def test_cancelled_hold_gives_up_its_place_without_consuming_a_permit() -> None:
    model = ScriptedModel(chunk_delay_seconds=0)
    async with client_for(model) as client:
        turn = asyncio.create_task(create_response(client, request_for("[[hold]]")))
        async with asyncio.timeout(5):
            await model.until_waiting()
        turn.cancel()
        with pytest.raises(asyncio.CancelledError):
            await turn
    assert model.waiting == 0


async def test_reject_marker_is_refused_like_a_known_provider_rejection() -> None:
    async with client_for(ScriptedModel()) as client:
        with pytest.raises(BadRequestError):
            await create_response(client, request_for("這句會被拒絕 [[reject]]"))


async def test_token_count_is_fixed_and_generation_is_available_without_streaming() -> None:
    model = ScriptedModel()
    async with client_for(model) as client:
        counted = await count_response_input(client, request_for("職稱：前端工程師"))
        response = await create_response(client, request_for("職稱：前端工程師", stream=False))
    assert counted.input_tokens == 500
    assert model.counts_sent == 1
    assert inspect_response_step(response).action == ResponseAction.EXECUTE_TOOLS


async def test_hold_with_profile_fields_runs_the_tool_step_then_holds_the_answer() -> None:
    model = ScriptedModel(chunk_delay_seconds=0)
    text = "職稱：前端工程師 [[hold]]"
    async with client_for(model) as client:
        first = await create_response(client, request_for(text))
        step = inspect_response_step(first)
        assert step.action == ResponseAction.EXECUTE_TOOLS
        assert model.waiting == 0
        later = [*first_items(first), dict(function_result_item(step.calls[0], "已更新"))]
        turn = asyncio.create_task(create_response(client, request_for(text, *later)))
        async with asyncio.timeout(5):
            await model.until_waiting()
        assert not turn.done()
        model.permits.release()
        second = await asyncio.wait_for(turn, 5)
    assert inspect_response_step(second).action == ResponseAction.DELIVER_ANSWER
    assert "前端工程師" in second.output_text
