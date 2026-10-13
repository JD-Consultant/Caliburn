"""控制觀察須有原 interrupt 身分及同範圍的 checkpoint 父子關係。"""

from copy import deepcopy

import pytest

from caliburn.diagnostics.control_history import collect_control_history


def checkpoint(checkpoint_id, parent=None, *, completed_steps=0, namespace=""):
    return {
        "thread_id": "thread",
        "checkpoint_ns": namespace,
        "checkpoint_id": checkpoint_id,
        "parent_checkpoint_id": parent,
        "checkpoint_time": "2026-10-10T00:00:00Z",
        "role": "job_consultant",
        "source": "checkpoint",
        "values": {"completed_steps": completed_steps, "request_id": "request"},
    }


def paused(base):
    return {
        **deepcopy(base),
        "source": "pending_write",
        "task_id": "paused-task",
        "values": {
            **base["values"],
            "__interrupt__": [
                {"id": "pause-id", "value": {"kind": "step_pause", "completed_steps": 1}}
            ],
        },
    }


def test_continuation_uses_committed_boundary_and_parent_chain_not_input_order():
    base = checkpoint("cp1")
    rows = [
        checkpoint("cp3", "cp2", completed_steps=1),
        checkpoint("cp2", "cp1"),
        paused(base),
        base,
    ]
    before = deepcopy(rows)
    result = collect_control_history(rows)
    assert result[0]["interrupt_id"] == "pause-id"
    assert result[0]["completed_steps"] == 1
    assert result[0]["continuation"]["checkpoint_path"] == ["cp1", "cp2", "cp3"]
    assert result[0]["continuation"]["state"] == "observed"
    assert rows == before


def test_retained_interrupt_does_not_claim_resumed_pending_request_was_paused():
    base = checkpoint("cp1")
    resumed = paused(base)
    resumed["values"]["request_id"] = "next-request"
    later = checkpoint("cp2", "cp1", completed_steps=1)
    later["values"]["request_id"] = "next-request"

    pause = collect_control_history([base, resumed, later])[0]

    assert "request_id" not in pause
    assert pause["interrupt_id"] == "pause-id"
    assert pause["completed_steps"] == 1
    assert pause["checkpoint_id"] == "cp1"
    assert pause["continuation"]["request_id"] == "next-request"


@pytest.mark.parametrize(
    "case",
    ["other_thread", "other_namespace", "unrelated", "missing_parent", "pending", "incomplete"],
)
def test_unproven_later_observation_does_not_claim_continuation(case):
    base = checkpoint("cp1")
    later = checkpoint("cp2", "cp1", completed_steps=1)
    if case == "other_thread":
        later["thread_id"] = "other"
    elif case == "other_namespace":
        later["checkpoint_ns"] = "nested"
    elif case == "unrelated":
        later["parent_checkpoint_id"] = None
    elif case == "missing_parent":
        later["parent_checkpoint_id"] = "missing"
    elif case == "pending":
        later["source"] = "pending_write"
    else:
        later["values"]["completed_steps"] = 0
    result = collect_control_history([base, paused(base), later])
    assert result[0]["continuation"] == {"state": "not_observed"}
