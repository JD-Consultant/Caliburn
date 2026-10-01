"""Reproduce Anthropic 1.5.0's EOF snapshot behavior without a provider call.

Run from experiments/jd-relational-app using its frozen development environment:
  uv run --offline --frozen python ../../docs/specs/evidence/jd-relational-context/anthropic_stream_closure_probe.py

This is a characterization probe, not an application completion validator.
All credentials, requests and SSE events are synthetic. MockTransport handles
every request locally; no product configuration or interview data is read.
"""

import json
from importlib.metadata import version

import anthropic
import httpx2


def probe(terminal: bool) -> dict[str, object]:
    events = [
        {
            "type": "message_start",
            "message": {
                "id": "msg_synthetic",
                "type": "message",
                "role": "assistant",
                "content": [],
                "model": "synthetic",
                "stop_reason": None,
                "stop_sequence": None,
                "usage": {"input_tokens": 1, "output_tokens": 1},
            },
        },
        {
            "type": "message_delta",
            "delta": {"stop_reason": "end_turn", "stop_sequence": None},
            "usage": {"output_tokens": 1},
        },
    ]
    if terminal:
        events.append({"type": "message_stop"})
    body = "".join(
        "event: " + event["type"] + "\ndata: " + json.dumps(event) + "\n\n"
        for event in events
    ).encode()
    request_count = 0

    def receive(request: httpx2.Request) -> httpx2.Response:
        nonlocal request_count
        request_count += 1
        assert request.method == "POST"
        assert request.url.host == "example.invalid"
        assert request.url.path == "/v1/messages"
        assert json.loads(request.content)["model"] == "synthetic"
        return httpx2.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content=body,
            request=request,
        )

    with anthropic.Anthropic(
        api_key="synthetic-not-a-key",
        base_url="https://example.invalid",
        max_retries=0,
        http_client=httpx2.Client(
            transport=httpx2.MockTransport(receive), trust_env=False
        ),
    ) as client:
        with client.messages.stream(
            model="synthetic",
            max_tokens=1,
            messages=[{"role": "user", "content": "synthetic"}],
        ) as stream:
            result = stream.get_final_message()
            assert result.id == "msg_synthetic"
            assert result.content == []
            assert result.stop_reason == "end_turn"
    assert request_count == 1
    return {
        "sent_message_stop": terminal,
        "sdk_returned_snapshot": True,
        "stop_reason": result.stop_reason,
    }


def main() -> None:
    assert version("anthropic") == "1.5.0", "Probe requires the recorded SDK version"
    assert version("httpx2") == "2.12.0", "Probe requires the recorded transport version"
    results = [probe(False), probe(True)]
    assert results == [
        {
            "sent_message_stop": False,
            "sdk_returned_snapshot": True,
            "stop_reason": "end_turn",
        },
        {
            "sent_message_stop": True,
            "sdk_returned_snapshot": True,
            "stop_reason": "end_turn",
        },
    ]
    for result in results:
        print(json.dumps(result))


if __name__ == "__main__":
    main()
