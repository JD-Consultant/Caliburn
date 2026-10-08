"""Counterexamples for evidence classification; no files, key, DB or provider."""

import json
from copy import deepcopy

from compaction_metadata import collect
from guard import digest


class Node:
    def __init__(self, name, rows):
        self.name = name
        self.body = "\n".join(json.dumps(row) for row in rows)

    def read_text(self, *, encoding):
        return self.body

    def read_bytes(self):
        return self.body.encode()


class Directory:
    name = "synthetic-case"

    def __init__(self, trace, checkpoints):
        self.nodes = {
            "provider-trace.jsonl": Node("provider-trace.jsonl", trace),
            "checkpoint-witness.jsonl": Node("checkpoint-witness.jsonl", checkpoints),
        }

    def __truediv__(self, name):
        return self.nodes[name]


def fixture():
    original = [digest({"type": "message"}), digest({"encrypted_content": "original"})]
    parent = [digest({"parent": "original"})]
    item = {"role": "user", "content": json.dumps({"plan": None})}
    trace = [
        {
            "event": "admitted",
            "endpoint": "/v1/responses/compact",
            "attempt": "c",
            "role": "A",
            "time": "1",
            "input_item_sha256": parent,
        },
        {
            "event": "received",
            "endpoint": "/v1/responses/compact",
            "attempt": "c",
            "response_id": "original-C",
            "role": "A",
            "time": "2",
            "output_item_sha256": original,
        },
        {
            "event": "admitted",
            "endpoint": "/v1/responses",
            "attempt": "next",
            "role": "A",
            "time": "3",
            "input_item_sha256": original + [digest(item)],
        },
    ]
    c = {
        "thread_id": "job:execution:job_consultant:responses:compact:request",
        "checkpoint_id": "saved-C",
        "saved_at": "2",
        "adopted": True,
        "preparation_policy": None,
        "compaction_item_sha256": original,
        "request_input_item_sha256": parent,
    }
    projection = {
        "thread_id": "job:execution:job_consultant:responses:plan_projection:request",
        "checkpoint_id": "saved-plan",
        "input_binding": {
            "compact_position": {
                "thread_id": c["thread_id"],
                "checkpoint_id": c["checkpoint_id"],
            },
            "source_request_id": "request",
        },
        "projection": {"plan_item": item},
    }
    return trace, [c, projection]


def test_prework_and_missing_policy_do_not_count_as_midwork():
    trace, checkpoints = fixture()
    checkpoints[0]["thread_id"] = "job:execution:job_consultant:prepared_history"
    checkpoints[0]["preparation_policy"] = {"compact_requested": True}
    result = collect(Directory(trace, checkpoints))["native_compactions"][0]
    assert result["adopted_checkpoints"][0]["boundary"] == "pre-work"
    del checkpoints[0]["preparation_policy"]
    result = collect(Directory(trace, checkpoints))["native_compactions"][0]
    assert result["adopted_checkpoints"][0]["boundary"] == "unknown"


def test_all_original_items_must_match_in_order():
    trace, checkpoints = fixture()
    trace[-1]["input_item_sha256"][1] = digest({"encrypted_content": "other"})
    result = collect(Directory(trace, checkpoints))["native_compactions"][0]
    assert result["subsequent_exact_prefix_requests"] == []
    assert (
        result["adopted_checkpoints"][0]["bound_plan_projections"][0][
            "next_exact_plan_item_attempts"
        ]
        == []
    )


def test_projection_requires_exact_c_position_and_complete_plan_item():
    trace, checkpoints = fixture()
    original = collect(Directory(trace, checkpoints))["native_compactions"][0]
    projection = original["adopted_checkpoints"][0]["bound_plan_projections"][0]
    assert projection["plan_body_kind"] == "null"
    assert projection["same_parent_request_thread"] is True
    assert projection["next_exact_plan_item_attempts"] == ["next"]
    wrong_position = deepcopy(checkpoints)
    wrong_position[-1]["input_binding"]["compact_position"]["checkpoint_id"] = "other-C"
    mismatch = collect(Directory(trace, wrong_position))["native_compactions"][0]
    assert mismatch["adopted_checkpoints"][0]["bound_plan_projections"] == []
    trace[-1]["input_item_sha256"][-1] = digest({"role": "user", "content": "other plan"})
    mismatch = collect(Directory(trace, checkpoints))["native_compactions"][0]
    assert (
        mismatch["adopted_checkpoints"][0]["bound_plan_projections"][0][
            "next_exact_plan_item_attempts"
        ]
        == []
    )


def test_saved_parent_request_mismatch_is_explicit():
    trace, checkpoints = fixture()
    checkpoints[0]["request_input_item_sha256"] = [digest({"parent": "different"})]
    result = collect(Directory(trace, checkpoints))["native_compactions"][0]
    assert (
        result["adopted_checkpoints"][0]["original_compact_input_equal_saved_parent_request"]
        is False
    )
    assert result["adopted_checkpoints"][0]["boundary"] == "unknown"
