"""Offline SDK/serializer capability checks, not remote API acceptance or product recovery."""

import json
from pathlib import Path

import httpx2
import pytest
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from openai import AsyncOpenAI
from openai.types.responses import Response
from openai.types.responses.compacted_response import CompactedResponse

RESPONSE_FIXTURE = Path(__file__).parents[1] / "fixtures/native-response.json"


@pytest.mark.asyncio
async def test_sdk_replays_all_native_items_without_remote_storage() -> None:
    payload = json.loads(RESPONSE_FIXTURE.read_text(encoding="utf-8"))
    captured = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        assert request.url.host == "openai.invalid"
        captured.append(json.loads(request.content))
        return httpx2.Response(200, json=payload)

    async with AsyncOpenAI(
        api_key="synthetic-test-key",
        base_url="https://openai.invalid/v1/",
        max_retries=0,
        http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(respond)),
    ) as client:
        history = [{"role": "user", "content": "合成測試：請讀資料。"}]
        result = await client.responses.create(
            model="gpt-6-luna",
            input=history,
            store=False,
            reasoning={"context": "all_turns"},
        )
        # Preserve the SDK's complete native items, not output_text or an App summary.
        replay_items = [item.model_dump(mode="json") for item in result.output]
        serializer = JsonPlusSerializer(pickle_fallback=False)
        restored = serializer.loads_typed(serializer.dumps_typed(replay_items))
        assert restored == replay_items
        assert restored[0]["encrypted_content"] == payload["output"][0]["encrypted_content"]
        assert restored[0]["provider_extension"] == {"must_survive": True}
        assert restored[1]["phase"] == "commentary"
        assert restored[2]["call_id"] == "call_synthetic"
        tool_result = {
            "type": "function_call_output",
            "call_id": "call_synthetic",
            "output": "合成資料",
        }
        history.extend(restored)
        history.append(tool_result)
        history.append({"role": "user", "content": "合成下一輪：請繼續。"})
        await client.responses.create(
            model="gpt-6-luna",
            input=history,
            store=False,
            reasoning={"context": "all_turns"},
        )

    assert len(captured) == 2
    assert captured[1]["input"] == history
    assert captured[1]["reasoning"] == {"context": "all_turns"}
    assert all(request["store"] is False for request in captured)
    assert all("previous_response_id" not in request for request in captured)


def test_compaction_window_round_trip_preserves_retained_items() -> None:
    raw = json.loads(RESPONSE_FIXTURE.read_text(encoding="utf-8"))
    window = CompactedResponse.model_validate(
        {
            "id": "cmp_synthetic",
            "created_at": raw["created_at"],
            "object": "response.compaction",
            "usage": raw["usage"],
            "output": [
                {
                    "type": "compaction",
                    "id": "ci_synthetic",
                    "encrypted_content": "synthetic-compact",
                },
                raw["output"][1],
            ],
        }
    )
    items = [item.model_dump(mode="json") for item in window.output]
    serializer = JsonPlusSerializer(pickle_fallback=False)
    restored = serializer.loads_typed(serializer.dumps_typed(items))
    assert restored == items
    assert len(restored) == 2
    assert restored[1]["phase"] == "commentary"


def test_synthetic_response_obeys_sdk_output_schema() -> None:
    response = Response.model_validate_json(RESPONSE_FIXTURE.read_text(encoding="utf-8"))
    assert [item.type for item in response.output] == ["reasoning", "message", "function_call"]
