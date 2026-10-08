"""Finite offline counterexamples; never fabricate a successful paid preflight."""

from copy import deepcopy
from types import SimpleNamespace
from uuid import uuid4

import pytest
import repaired_comparison
from langgraph.checkpoint.memory import InMemorySaver
from repaired_comparison import SMOKE, bind_case_observers, checkpoint_stage, read_json


@pytest.mark.parametrize(
    ("thread", "policy", "adopted", "expected"),
    [
        ("scope:job_consultant:prepared_history", {"compact_requested": True}, True, "pre-work"),
        ("scope:job_consultant:completed_work:compact:request", "missing", True, "unknown"),
        ("scope:job_consultant:completed_work:compact:request", None, False, "unknown"),
        ("scope:work_memory:completed_work:compact:request", None, True, "unknown"),
    ],
)
def test_only_explicit_adopted_within_work_checkpoint_is_midwork(thread, policy, adopted, expected):
    values = {
        "adopted": adopted,
        "compaction_snapshot": {"output": []},
        "request_snapshot": {"tools": [{"name": "revise_jd_profile"}]},
    }
    if policy != "missing":
        values["preparation_policy"] = policy
    assert checkpoint_stage(thread, values) == expected


class MemoryJournal:
    def __init__(self):
        self.lines = []

    def __truediv__(self, _name):
        return self

    def open(self, *_args, **_kwargs):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def write(self, line):
        self.lines.append(line)


class NoNetworkTransport:
    def __init__(self, *_args, **_kwargs):
        pass


def observer_setup(saver=InMemorySaver):
    released = []
    guard = SimpleNamespace(on_a_compact=lambda: released.append(True))
    batch = SimpleNamespace(GuardedTransport=NoNetworkTransport, ObservedSaver=saver)
    journal = MemoryJournal()
    bind_case_observers(batch, guard, journal)
    batch.GuardedTransport(guard)
    return batch, guard, released, journal


@pytest.mark.asyncio
async def test_response_and_prework_c_do_not_release_but_saved_midwork_does_once():
    batch, guard, released, journal = observer_setup()
    guard.on_a_compact()
    assert released == []
    actual = read_json(SMOKE / "native-midwork-adopted.json")
    values = actual["values"]
    saver = batch.ObservedSaver()
    checkpoint = {
        "v": 4,
        "id": str(uuid4()),
        "ts": "2026-10-07T00:00:00+00:00",
        "channel_values": deepcopy(values),
        "channel_versions": {key: 1 for key in values},
        "versions_seen": {},
    }
    metadata = {"source": "loop", "step": 1, "parents": {}}
    pre = deepcopy(checkpoint)
    pre["channel_values"]["preparation_policy"] = {"compact_requested": True}
    await saver.aput(
        {
            "configurable": {
                "thread_id": "scope:job_consultant:prepared_history",
                "checkpoint_ns": "",
            }
        },
        pre,
        metadata,
        pre["channel_versions"],
    )
    assert released == []
    config = {"configurable": {"thread_id": actual["thread_id"], "checkpoint_ns": ""}}
    await saver.aput(config, checkpoint, metadata, checkpoint["channel_versions"])
    await saver.aput(config, checkpoint, metadata, checkpoint["channel_versions"])
    assert released == [True]
    assert '"stage": "pre-work"' in journal.lines[0]
    assert '"saved_midwork_read_verified": true' in journal.lines[-1]


@pytest.mark.asyncio
async def test_unacknowledged_saver_write_cannot_release_pressure():
    class UnavailableSaver(InMemorySaver):
        async def aput(self, *_args, **_kwargs):
            raise RuntimeError("database save failed")

    batch, _guard, released, journal = observer_setup(UnavailableSaver)
    with pytest.raises(RuntimeError, match="database save failed"):
        await batch.ObservedSaver().aput({}, {}, {}, {})
    assert released == []
    assert journal.lines == []


def test_changed_semantic_receipt_cannot_admit_repaired_comparison(monkeypatch):
    monkeypatch.setattr(repaired_comparison, "RECEIPT_SHA", "0" * 64)
    with pytest.raises(ValueError, match="Actual repair smoke"):
        repaired_comparison.read_gate()


@pytest.mark.parametrize(
    ("stdout", "returncode", "query_error", "closed"),
    [
        ('{"count":0}', 0, None, True),
        ('{"count":1}', 0, None, False),
        ('{"count":0}', 1, None, False),
        ("", 0, OSError("query process unavailable"), False),
        ("not JSON", 0, None, False),
        ('{"count":true}', 0, None, False),
        ('{"count":-1}', 0, None, False),
    ],
)
def test_listener_inventory_is_authority_and_query_failure_is_closed(
    monkeypatch, stdout, returncode, query_error, closed
):
    calls = []

    def query(command, **kwargs):
        calls.append((command, kwargs))
        if query_error is not None:
            raise query_error
        return SimpleNamespace(returncode=returncode, stdout=stdout, stderr="")

    monkeypatch.setattr(repaired_comparison.subprocess, "run", query)
    if closed:
        repaired_comparison.require_closed_listener()
    else:
        with pytest.raises(RuntimeError):
            repaired_comparison.require_closed_listener()
    assert len(calls) == 1
    assert "Get-NetTCPConnection -State Listen -ErrorAction Stop" in calls[0][0][-1]
    assert "$_.LocalPort -eq 8177" in calls[0][0][-1]
