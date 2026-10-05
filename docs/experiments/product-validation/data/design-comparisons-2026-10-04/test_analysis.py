"""Pooling must use the trace that belongs to each saved outcome."""

import json

from analyze import analyze


def test_same_named_interrupted_trace_does_not_replace_completed_usage(tmp_path):
    interrupted = tmp_path / "interrupted"
    completed = tmp_path / "completed"
    cases = {"context": [], "locator": [{"case_id": "selection", "indices": [1]}]}
    for folder, cache_write in ((interrupted, 5), (completed, 60)):
        folder.mkdir()
        (folder / "cases.json").write_text(json.dumps(cases), encoding="utf-8")
        (folder / "results.jsonl").write_text("", encoding="utf-8")
        response = {
            "event": "response",
            "usage": {
                "input_tokens": 100,
                "output_tokens": 2,
                "input_tokens_details": {
                    "cached_tokens": 10,
                    "cache_write_tokens": cache_write,
                },
            },
        }
        (folder / "selection-uuid.jsonl").write_text(
            json.dumps(response) + "\n", encoding="utf-8"
        )
    outcome = {
        "trial_id": "selection-uuid",
        "suite": "locator",
        "case_id": "selection",
        "arm": "uuid",
        "repeat": 1,
        "status": "completed",
        "selected": [1],
        "checks": {"targets": True},
        "all_passed": True,
        "input_tokens": 100,
        "output_tokens": 2,
        "cached_input_tokens": 10,
        "model_calls": 1,
        "read_calls": 0,
        "rejected_calls": 0,
        "elapsed_seconds": 1,
    }
    (completed / "results.jsonl").write_text(
        json.dumps(outcome) + "\n", encoding="utf-8"
    )

    result = analyze(completed, [interrupted])

    assert result["groups"][0]["cache_write_tokens"] == 60
    assert (
        result["all_reported_usage_including_interrupted_trials"]["cache_write_tokens"]
        == 65
    )
