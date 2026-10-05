"""Audit native continuation and full canonical compact adoption separately."""

from analyze_main import audit_chains, retrievals


def row(event, path, payload):
    return {
        "event": event,
        "path": path,
        "payload": payload,
        "arm": "synthetic",
        "phase": "consultant",
    }


def test_compact_canonical_window_is_adopted_whole_not_reported_as_prefix_loss():
    raw = [{"role": "user", "content": "original"}]
    call = {"type": "function_call", "call_id": "c1", "name": "read_jd"}
    result = {"type": "function_call_output", "call_id": "c1", "output": "body"}
    complete = [*raw, call, result]
    canonical = [
        {"role": "user", "content": "retained"},
        {"type": "compaction", "encrypted_content": {"sha256": "opaque"}},
    ]
    rows = [
        row(
            "request",
            "/v1/responses",
            {"instructions": "role", "model": "gpt-6-luna", "input": raw},
        ),
        row("response", "/v1/responses", {"output": [{**call, "status": "completed"}]}),
        row(
            "request",
            "/v1/responses/input_tokens",
            {"instructions": "role", "model": "gpt-6-luna", "input": complete},
        ),
        row("request", "/v1/responses/compact", {"model": "gpt-6-luna", "input": complete}),
        row("response", "/v1/responses/compact", {"output": canonical}),
        row(
            "request",
            "/v1/responses",
            {"instructions": "role", "model": "gpt-6-luna", "input": canonical},
        ),
        row("response", "/v1/responses", {"output": []}),
    ]
    result = audit_chains(rows)
    assert result["issues"] == []
    assert result["compaction_adoptions_checked"] == 1
    assert result["tool_results_checked"] == 1


def test_dropping_retained_user_from_compact_output_is_detected():
    full = [{"role": "user", "content": "retained"}, {"type": "compaction", "id": "cmp"}]
    rows = [
        row(
            "request",
            "/v1/responses/input_tokens",
            {"instructions": "role", "model": "gpt-6-luna", "input": []},
        ),
        row("request", "/v1/responses/compact", {"model": "gpt-6-luna", "input": []}),
        row("response", "/v1/responses/compact", {"output": full}),
        row(
            "request",
            "/v1/responses",
            {"instructions": "role", "model": "gpt-6-luna", "input": full[1:]},
        ),
    ]
    assert audit_chains(rows)["issues"][0]["kind"] == "native_prefix_changed"


def test_result_first_sent_to_compact_is_counted_once_even_when_later_retained():
    call = {
        "type": "function_call",
        "call_id": "c1",
        "name": "read_interview",
        "arguments": '{"sequences":[2]}',
    }
    result = {"type": "function_call_output", "call_id": "c1", "output": "original"}
    rows = [
        row("response", "/v1/responses", {"output": [call]}),
        row("request", "/v1/responses/compact", {"input": [call, result]}),
        row("request", "/v1/responses", {"input": [call, result]}),
        row("request", "/v1/responses", {"input": [call, result]}),
    ]
    assert retrievals(rows)["completed_tool_results"] == 1
    assert retrievals(rows[:2])["completed_tool_results"] == 1
