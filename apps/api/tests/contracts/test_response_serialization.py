"""Product serialization helpers preserve originals; HTTP mock is not provider acceptance."""

import json
from copy import deepcopy
from pathlib import Path

import httpx2
import pytest
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from openai import AsyncOpenAI
from openai.types.responses import Response, ResponseFunctionToolCall
from openai.types.responses.compacted_response import CompactedResponse
from pydantic import ValidationError

from caliburn.adapters.response_serialization import (
    compaction_input_items,
    function_result_item,
    require_result_order,
    response_input_items,
    restore_response,
    snapshot_compaction,
    snapshot_response,
)


@pytest.fixture
def response() -> Response:
    return Response.model_validate_json(
        (Path(__file__).parents[1] / "fixtures/native-response.json").read_text(encoding="utf-8")
    )


def test_snapshot_and_replay_are_distinct_without_losing_received_metadata(
    response: Response,
) -> None:
    original = snapshot_response(response)
    serializer = JsonPlusSerializer(pickle_fallback=False, allowed_msgpack_modules=None)
    restored = restore_response(serializer.loads_typed(serializer.dumps_typed(original)))
    assert snapshot_response(restored) == original
    replay = response_input_items(restored)
    expected = deepcopy(original["output"])
    for item in expected:
        item.pop("status", None)
    assert replay == expected
    assert replay[0]["provider_extension"] == {"must_survive": True}
    assert replay[1]["phase"] == "commentary"
    assert original["output"][0]["status"] == "completed"
    replay[0]["provider_extension"]["must_survive"] = False
    assert snapshot_response(response) == original


def test_native_alias_is_preserved_instead_of_python_attribute(response: Response) -> None:
    raw = snapshot_response(response)
    raw["output"][2]["async"] = False
    raw["provider_envelope_metadata"] = {"value": [1, None, "測試"]}
    restored = restore_response(raw)
    assert snapshot_response(restored) == raw
    replay = response_input_items(restored)
    assert replay[2]["async"] is False
    assert "async_" not in replay[2]


def test_compaction_adopts_the_whole_window_without_appending_original_input(
    response: Response,
) -> None:
    raw = {
        "id": "cmp_test",
        "object": "response.compaction",
        "created_at": 1,
        "usage": snapshot_response(response)["usage"],
        "output": [
            {"type": "compaction", "id": "ci_test", "encrypted_content": "opaque"},
            snapshot_response(response)["output"][1],
        ],
    }
    compact = CompactedResponse.model_validate(raw)
    saved = snapshot_compaction(compact)
    serializer = JsonPlusSerializer(pickle_fallback=False, allowed_msgpack_modules=None)
    restored = serializer.loads_typed(serializer.dumps_typed(saved))
    assert restored == raw
    assert compaction_input_items(restored) == raw["output"]


@pytest.mark.asyncio
async def test_compaction_preserves_retained_user_messages_from_real_sdk(
    response: Response,
) -> None:
    raw = {
        "id": "cmp_user",
        "object": "response.compaction",
        "created_at": 1,
        "usage": snapshot_response(response)["usage"],
        "output": [
            {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": "合成員工原話"}],
            },
            {"type": "compaction", "id": "ci_test", "encrypted_content": "opaque"},
        ],
    }
    async with AsyncOpenAI(
        api_key="synthetic-only",
        base_url="https://openai.invalid/v1/",
        max_retries=0,
        http_client=httpx2.AsyncClient(
            transport=httpx2.MockTransport(lambda _: httpx2.Response(200, json=raw))
        ),
    ) as client:
        compact = await client.responses.compact(model="gpt-6-luna", input="合成員工原話")
    saved = snapshot_compaction(compact)
    assert saved == raw
    restored = compaction_input_items(saved)
    assert restored == raw["output"]
    restored[0]["content"][0]["text"] = "不得改寫保存原件"
    assert saved == raw


def test_results_keep_call_identity_and_direct_caller(response: Response) -> None:
    call = ResponseFunctionToolCall.model_validate(snapshot_response(response)["output"][2])
    call.caller = None
    output = function_result_item(call, '{"status":"unchanged"}')
    assert output == {
        "type": "function_call_output",
        "call_id": "call_synthetic",
        "output": '{"status":"unchanged"}',
    }
    require_result_order([call], [])
    require_result_order([call], [output])
    direct = ResponseFunctionToolCall.model_validate(
        {**call.model_dump(), "caller": {"type": "direct"}}
    )
    assert function_result_item(direct, "done")["caller"] == {"type": "direct"}


@pytest.mark.parametrize(
    "result_ids", [["second"], ["first", "first"], ["first", "second", "third"]]
)
def test_saved_result_prefix_cannot_skip_repeat_or_exceed_calls(result_ids: list[str]) -> None:
    calls = [
        ResponseFunctionToolCall(
            type="function_call", call_id=name, name="read_test", arguments="{}"
        )
        for name in ["first", "second"]
    ]
    results = [
        function_result_item(call.model_copy(update={"call_id": name}), "result")
        for name, call in zip(result_ids, [calls[0]] * len(result_ids), strict=True)
    ]
    with pytest.raises(ValueError):
        require_result_order(calls, results)


@pytest.mark.asyncio
@pytest.mark.parametrize("missing_billing_detail", [False, True])
async def test_real_sdk_mock_transport_sends_preserved_items_and_exact_result(
    response: Response,
    missing_billing_detail: bool,
) -> None:
    captured = []
    raw = snapshot_response(response)
    if missing_billing_detail:
        del raw["usage"]["input_tokens_details"]["cache_write_tokens"]

    def reply(request: httpx2.Request) -> httpx2.Response:
        assert request.url.host == "openai.invalid"
        captured.append(json.loads(request.content))
        return httpx2.Response(200, json=raw)

    async with AsyncOpenAI(
        api_key="synthetic-only",
        base_url="https://openai.invalid/v1/",
        max_retries=0,
        http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(reply)),
    ) as client:
        first = await client.responses.create(
            model="gpt-6-luna", input="合成問題", store=False, reasoning={"context": "all_turns"}
        )
        restored = restore_response(snapshot_response(first))
        assert snapshot_response(restored) == raw
        history = [{"role": "user", "content": "合成問題"}, *response_input_items(restored)]
        call = ResponseFunctionToolCall.model_validate(raw["output"][2])
        history.append(function_result_item(call, "原工具結果"))
        await client.responses.create(
            model="gpt-6-luna", input=history, store=False, reasoning={"context": "all_turns"}
        )
    assert captured[1]["input"] == history
    assert captured[1]["input"][1]["encrypted_content"] == raw["output"][0]["encrypted_content"]
    assert captured[1]["input"][2]["phase"] == "commentary"
    assert len(captured) == 2


def test_missing_billing_detail_does_not_relax_output_validation(response: Response) -> None:
    raw = snapshot_response(response)
    del raw["usage"]["input_tokens_details"]["cache_write_tokens"]
    raw["output"][2]["call_id"] = []
    with pytest.raises(ValidationError) as failure:
        restore_response(raw)
    assert any(error["loc"][0] == "output" for error in failure.value.errors())
