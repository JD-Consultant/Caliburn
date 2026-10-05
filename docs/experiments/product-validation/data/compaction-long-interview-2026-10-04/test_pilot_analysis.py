"""Keep remote counting separate from generation usage and unfinished sends."""

import hashlib
from pathlib import Path

import analyze_pilot
from analyze_pilot import audit_native_chains, executed_script, summarize_trace


def test_counts_are_not_generations_and_an_unanswered_send_is_retained():
    rows = [
        {"event": "request", "path": "/v1/responses/input_tokens", "payload": {}},
        {
            "event": "response",
            "path": "/v1/responses/input_tokens",
            "payload": {"input_tokens": 9999},
        },
        {
            "event": "request",
            "path": "/v1/responses",
            "phase": "consultant",
            "payload": {},
        },
        {
            "event": "response",
            "path": "/v1/responses",
            "phase": "consultant",
            "payload": {
                "usage": {
                    "input_tokens": 300,
                    "output_tokens": 20,
                    "input_tokens_details": {"cached_tokens": 100},
                    "output_tokens_details": {"reasoning_tokens": 5},
                },
                "output": [{"type": "function_call", "name": "read_jd"}],
            },
        },
        {
            "event": "request",
            "path": "/v1/responses",
            "phase": "consultant",
            "payload": {},
        },
    ]
    result = summarize_trace(rows)
    assert result["generation_sends"] == 2
    assert result["generation_responses"] == 1
    assert result["unanswered_sends"] == 1
    assert result["input_tokens"] == 300
    assert result["peak_generation_input_tokens"] == 300
    assert result["tools"] == {"read_jd": 1}


def test_missing_usage_is_unknown_not_zero():
    result = summarize_trace(
        [{"event": "response", "path": "/v1/responses", "payload": {"output": []}}]
    )
    assert result["input_tokens"] is None
    assert result["missing_usage_responses"] == 1


def test_executed_source_accepts_the_recorded_windows_path():
    source = Path(analyze_pilot.__file__).with_name("pilot.py").read_text(encoding="utf-8")
    expected = hashlib.sha256(source.encode()).hexdigest()
    key = r"docs\experiments\pilot.py"
    recovered = executed_script(Path(__file__).parent, {"sha256": {key: expected}})
    assert recovered["sha256"] == expected
    assert recovered["source_path"] == key
    assert recovered["text"] == source


def chain_rows(*, preserve_phase=True, call_id="call_original"):
    output = [
        {"type": "message", "phase": "commentary", "status": "completed"},
        {"type": "function_call", "call_id": "call_original", "status": "completed"},
    ]
    projected = [{k: v for k, v in item.items() if k != "status"} for item in output]
    if not preserve_phase:
        del projected[0]["phase"]
    first = {"instructions": "A", "input": [{"role": "user", "content": "原文"}]}
    followup = {
        "instructions": "A",
        "input": first["input"]
        + projected
        + [{"type": "function_call_output", "call_id": call_id, "output": "結果"}],
    }
    return [
        {"event": "request", "path": "/v1/responses", "phase": "consultant", "payload": first},
        {
            "event": "response",
            "path": "/v1/responses",
            "phase": "consultant",
            "payload": {"output": output},
        },
        {"event": "request", "path": "/v1/responses", "phase": "consultant", "payload": followup},
    ]


def test_native_projection_keeps_phase_and_reports_a_dropped_phase():
    assert audit_native_chains(chain_rows())["issues"] == []
    assert audit_native_chains(chain_rows(preserve_phase=False))["issues"] == [
        {"request_index": 2, "kind": "native_prefix_changed"}
    ]


def test_tool_result_must_match_the_original_call():
    assert audit_native_chains(chain_rows(call_id="wrong_call"))["issues"] == [
        {"request_index": 2, "kind": "tool_call_pairing_changed"}
    ]
