"""Offline regression of trace/statistics verification; preserves all raw artifacts."""

import json
from copy import deepcopy

import pytest
from analyze import HERE, read_events, verify_trial


def fixture_data():
    run = HERE / "run-02-network"
    row = read_events(run / "results.jsonl")[0]
    case = json.loads((run / "cases.json").read_text(encoding="utf-8"))[0]
    return run, row, case


def test_independent_write_timestamps_do_not_change_result_payload():
    run, row, case = fixture_data()
    row["at"] = "different aggregate write time"
    verified = verify_trial(run, row, case)
    assert verified["checks_passed"] == 8
    assert verified["input_tokens"] == 7100


def test_altered_trace_usage_is_rejected(monkeypatch):
    run, row, case = fixture_data()
    events = deepcopy(read_events(run / f"{row['trial_id']}.jsonl"))
    response = next(event for event in events if event["event"] == "response")
    response["usage"]["input_tokens"] += 1
    monkeypatch.setattr("analyze.read_events", lambda path: events)
    with pytest.raises(ValueError, match="Wrong input_tokens"):
        verify_trial(run, row, case)


def test_different_gold_is_rejected_not_silently_rescored():
    run, row, case = fixture_data()
    case["expected"]["reference_action"] = "keep_pending"
    with pytest.raises(ValueError, match="Score drift"):
        verify_trial(run, row, case)
