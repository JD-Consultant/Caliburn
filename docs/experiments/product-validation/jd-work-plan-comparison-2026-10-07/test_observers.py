"""No provider C or unacknowledged saver write may release controlled pressure."""

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from observers import bind_case_observers, checkpoint_stage


@pytest.mark.parametrize(
    "thread,policy,adopted,stage",
    [
        ("scope:job_consultant:prepared_history", {}, True, "pre-work"),
        ("scope:job_consultant:completed_work:compact:request", None, True, "mid-work"),
        ("scope:job_consultant:completed_work:compact:request", None, False, "unknown"),
        ("scope:work_memory:completed_work:compact:request", None, True, "unknown"),
    ],
)
def test_only_actual_adopted_a_within_work_position_is_midwork(
    thread, policy, adopted, stage
):
    values = {
        "adopted": adopted,
        "preparation_policy": policy,
        "compaction_snapshot": {"output": []},
        "request_snapshot": {"tools": [{"name": "revise_jd_profile"}]},
    }
    assert checkpoint_stage(thread, values) == stage


@pytest.mark.asyncio
async def test_unacknowledged_official_saver_and_provider_callback_do_not_release(
    tmp_path,
):
    released = []

    class FailedSaver:
        async def aput(self, *args):
            raise RuntimeError("official PostgreSQL write failed")

    class Transport:
        def __init__(self, *args):
            pass

    guard = SimpleNamespace(on_a_compact=lambda: released.append(True))
    batch = SimpleNamespace(GuardedTransport=Transport, ObservedSaver=FailedSaver)
    bind_case_observers(batch, guard, tmp_path)
    batch.GuardedTransport(guard)
    guard.on_a_compact()
    assert not released
    with pytest.raises(RuntimeError, match="official PostgreSQL"):
        await batch.ObservedSaver().aput({}, {}, {}, {})
    assert not released
    assert not (tmp_path / "pressure-adoption.jsonl").exists()
