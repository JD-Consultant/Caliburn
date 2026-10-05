from analyze_run import analyze


def row(event, path, **extra):
    return {
        "arm": "raw",
        "case_id": "c01",
        "event": event,
        "path": path,
        "accounting": {
            "actual_estimated_usd": "0",
            "count_estimated_usd": "0.0001",
            "pending_reserved_usd": "0.02",
        },
        **extra,
    }


def test_unsettled_reservations_are_not_reported_as_zero():
    rows = [row("request", "/v1/responses/input_tokens")]
    group = analyze(rows)["raw"]
    assert "completed" not in group
    assert group["totals"]["count_estimated_usd"] == "0.0001"
    assert group["totals"]["pending_reserved_usd"] == "0.02"
    assert group["totals"]["estimated_usd"] == "0.0201"


def test_compact_usage_is_counted_but_returned_historical_tools_are_not():
    rows = [
        row(
            "response",
            "/v1/responses/compact",
            duration_seconds=1,
            http_status=200,
            payload={
                "usage": {
                    "input_tokens": 5,
                    "output_tokens": 2,
                    "input_tokens_details": {"cache_write_tokens": 4},
                },
                "output": [
                    {
                        "type": "function_call",
                        "call_id": "old",
                        "name": "read_jd",
                        "arguments": "{}",
                    }
                ],
            },
        )
    ]
    totals = analyze(rows)["raw"]["totals"]
    assert totals["input_tokens"] == 5
    assert totals["cache_write_input_tokens"] == 4
    assert totals["tool_calls"] == {}
