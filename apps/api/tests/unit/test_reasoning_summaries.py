"""Public summaries must not become raw reasoning, duplicate context, or formal messages."""

from dataclasses import asdict

import pytest
from langgraph.checkpoint.base import empty_checkpoint
from langgraph.checkpoint.memory import InMemorySaver

from caliburn.adapters import openai_responses as adapter
from caliburn.adapters.response_serialization import response_input_items, snapshot_response
from caliburn.agent_execution import public_messages
from tests.unit.test_response_streaming import (
    WireStream,
    client_for,
    request,
    terminal,
    wire_events,
)


def summary_response():
    raw = terminal()
    raw["output"][0]["summary"] = [
        {"type": "summary_text", "text": "先核對工作範圍。"},
        {"type": "summary_text", "text": "再確認責任分界。"},
    ]
    raw["output"][0]["content"] = [{"type": "reasoning_text", "text": "PRIVATE_REASONING"}]
    return raw


def summary_events(raw):
    events = wire_events(raw)
    item = raw["output"][0]
    identity = {"item_id": item["id"], "output_index": 0, "summary_index": 0}
    events[1:1] = [
        {
            "type": "response.output_item.added",
            "output_index": 0,
            "item": {**item, "summary": [], "status": "in_progress"},
        },
        {
            "type": "response.reasoning_summary_part.added",
            **identity,
            "part": {"type": "summary_text", "text": ""},
        },
        {"type": "response.reasoning_summary_text.delta", **identity, "delta": "先核對"},
        {"type": "response.reasoning_summary_text.delta", **identity, "delta": "工作範圍。"},
        {
            "type": "response.reasoning_summary_text.delta",
            **identity,
            "output_index": 99,
            "delta": "WRONG_ITEM",
        },
        {"type": "response.reasoning_summary_text.done", **identity, "text": "先核對工作範圍。"},
        {"type": "response.output_item.done", "output_index": 0, "item": item},
    ]
    return events


def test_summary_is_explicit_and_saved_requests_keep_their_original_policy():
    old = request().create_payload()
    new = adapter.ResponseRequest(
        model="gpt-6-luna",
        instructions="synthetic",
        input_items=[],
        tools=[],
        reasoning_effort="medium",
        reasoning_summary="auto",
        max_output_tokens=1024,
    )
    assert new.count_payload()["reasoning"] == {
        "context": "all_turns",
        "effort": "medium",
        "summary": "auto",
    }
    assert (
        adapter.ResponseRequest.from_snapshot(new.create_payload()).create_payload()
        == new.create_payload()
    )
    assert adapter.ResponseRequest.from_snapshot(old).create_payload() == old
    assert "summary" not in old["reasoning"]


async def test_summary_stream_accumulates_parts_without_leaking_or_changing_native_result():
    raw = summary_response()
    summaries, commentary = [], []
    async with client_for(WireStream(summary_events(raw)), []) as client:
        result = await adapter.create_response(
            client,
            request(stream=True),
            on_commentary=commentary.append,
            on_reasoning_summary=summaries.append,
        )
    assert [(s.item_id, s.output_index, s.summary_index, s.text) for s in summaries] == [
        (raw["output"][0]["id"], 0, 0, "先核對"),
        (raw["output"][0]["id"], 0, 0, "先核對工作範圍。"),
        (raw["output"][0]["id"], 0, 1, "再確認責任分界。"),
    ]
    assert commentary[-1].text == "正在核對"
    assert "PRIVATE" not in str([asdict(s) for s in summaries])
    assert snapshot_response(result) == raw
    assert response_input_items(result)[0]["summary"] == raw["output"][0]["summary"]
    assert len(response_input_items(result)) == len(raw["output"])


async def test_summary_observer_failure_does_not_discard_response_or_leak_logs(caplog):
    calls = []

    def broken(update):
        calls.append(update)
        raise RuntimeError("PRIVATE_FAILURE")

    raw = summary_response()
    async with client_for(WireStream(summary_events(raw)), []) as client:
        result = await adapter.create_response(
            client,
            request(stream=True),
            on_reasoning_summary=broken,
        )
    assert snapshot_response(result) == raw
    assert len(calls) == 1
    assert "PRIVATE_FAILURE" not in caplog.text


@pytest.mark.parametrize("envelope", ["item", "part"])
async def test_non_summary_parts_are_not_public_even_if_sdk_constructs_them(envelope):
    raw = summary_response()
    events = summary_events(raw)
    private = {"type": "reasoning_text", "text": "PRIVATE_MALFORMED_PART"}
    event = (
        {
            "type": "response.output_item.done",
            "output_index": 0,
            "item": {**raw["output"][0], "summary": [private]},
        }
        if envelope == "item"
        else {
            "type": "response.reasoning_summary_part.done",
            "item_id": raw["output"][0]["id"],
            "output_index": 0,
            "summary_index": 0,
            "part": private,
        }
    )
    events.insert(-1, event)
    summaries = []
    async with client_for(WireStream(events), []) as client:
        await adapter.create_response(
            client, request(stream=True), on_reasoning_summary=summaries.append
        )
    assert all("PRIVATE" not in s.text for s in summaries)


async def test_saved_summary_history_survives_compaction_without_duplicate_or_private_fields():
    saver = InMemorySaver()
    config = {"configurable": {"thread_id": "summary-turn", "checkpoint_ns": ""}}
    raw = summary_response()
    for index in range(2):
        checkpoint = empty_checkpoint()
        checkpoint["channel_values"] = {
            "response_snapshot": raw if index == 0 else {},
            "input_items": [{"type": "compaction", "encrypted_content": "opaque"}],
        }
        checkpoint["channel_versions"] = {"response_snapshot": index + 1, "input_items": index + 1}
        config = await saver.aput(
            config,
            checkpoint,
            {"source": "loop", "step": index, "parents": {}},
            checkpoint["channel_versions"],
        )
    await saver.aput_writes(config, [("response_snapshot", raw)], "saved-model")
    result = await public_messages.read_public_reasoning_summaries(saver, thread_id="summary-turn")
    assert [asdict(s) for s in result] == [
        {
            "response_id": "resp_synthetic",
            "item_id": raw["output"][0]["id"],
            "output_index": 0,
            "summary_index": i,
            "text": text,
        }
        for i, text in enumerate(["先核對工作範圍。", "再確認責任分界。"])
    ]
    assert await public_messages.read_public_reasoning_summaries(saver, thread_id="other") == ()


@pytest.mark.parametrize("status", ["failed", "incomplete"])
def test_unfinished_responses_do_not_become_durable_summary_history(status):
    from caliburn.adapters.response_serialization import restore_response

    raw = summary_response()
    raw["status"] = status
    assert public_messages.project_reasoning_summaries(restore_response(raw)) == ()
