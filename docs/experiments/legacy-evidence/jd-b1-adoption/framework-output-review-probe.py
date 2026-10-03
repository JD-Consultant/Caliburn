"""Pinned framework behavior, synthetic SDK SSE, zero network/provider.

Run from experiments/jd-relational-app with PYTHONPATH=src;tests;
../../packages/consultant-memory/src and pytest pointed at this file.
This probes framework behavior, not a production B1 provider adapter.
"""
import json

import pytest
from langsmith import tracing_context

from caliburn_memory.extraction import ExtractionOutput
from jd_relational.consultant_model import create_consultant_model
from test_consultant_model import SyncBody, events, mock_sync, no_external_clients


@pytest.mark.parametrize("reason", ["end_turn", "max_tokens", "refusal"])
def test_structured_parser_and_provider_completion_are_different(monkeypatch, reason):
    candidate = {"rollout_summary": "合成工作詳記", "raw_memory": "合成工作資訊", "rollout_slug": "合成"}
    output = json.dumps(candidate, ensure_ascii=False)
    if reason == "max_tokens":
        output = output[:-1]  # Missing closing brace, recoverable by native parser.
    elif reason == "refusal":
        output = "Synthetic refusal."
    frames = []
    for chunk in events():
        frame = json.loads(chunk.decode().split("data: ", 1)[1])
        if frame["type"] == "content_block_delta":
            frame["delta"]["text"] = output
        if frame["type"] == "message_delta":
            frame["delta"]["stop_reason"] = reason
        frames.append(f"event: {frame['type']}\ndata: {json.dumps(frame)}\n\n".encode())
    client, requests = mock_sync(monkeypatch, SyncBody(frames))
    try:
        model = create_consultant_model(model_name="synthetic", api_key="synthetic-not-a-key",
                                       timeout=5, max_tokens=8192)
        # These extra kwargs are deliberately passed to demonstrate that this
        # pinned Anthropic method ignores them; they are NOT adoption guidance.
        structured = model.with_structured_output(ExtractionOutput.model_json_schema(),
            method="json_schema", include_raw=True, strict=True, max_output_tokens=123)
        with tracing_context(enabled=False):
            result = structured.invoke("Synthetic offline extraction")
        assert len(requests) == 1
        assert requests[0]["max_tokens"] == 8192
        assert "max_output_tokens" not in requests[0]
        assert requests[0]["output_config"]["format"]["type"] == "json_schema"
        assert result["raw"].response_metadata["stop_reason"] == reason
        if reason == "refusal":
            assert result["parsed"] is None and result["parsing_error"] is not None
        else:
            assert result["parsed"] == candidate and result["parsing_error"] is None
    finally:
        client.close()
