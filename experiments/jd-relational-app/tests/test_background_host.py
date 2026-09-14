"""Registering background B work on the host that already owns this document.

One bounded worker, the same close that already drains foreground attempts and
registered reads, and no app-wide lock: a batch on one document must never stop
another document's manual or foreground work. Nothing polls and nothing lives
between batches -- a job is admitted, runs once, and exits.
"""
from concurrent.futures import TimeoutError as FutureTimeout
from threading import Event
from uuid import uuid4

import pytest

from jd_relational.manual_runtime import RuntimeFailure

from test_manual_runtime import runtime  # noqa: F401


def held(release, started=None):
    """One bounded job that finishes only when the test lets it."""
    def work():
        if started is not None:
            started.set()
        assert release.wait(5)
        return "done"
    return work


def test_a_registered_background_job_is_drained_before_close_returns(runtime):
    """Closing waits for admitted work to actually exit, as it does elsewhere."""
    owner, _, storage = runtime
    document, release, started = str(uuid4()), Event(), Event()
    future = owner.admit_background(document, held(release, started))
    assert started.wait(5)
    release.set()
    storage.release.set()
    assert owner.close(timeout=5)
    assert future.result(0) == "done"


def test_close_stops_new_background_admission_before_it_drains(runtime):
    """Admission closes first, so nothing new joins the work being drained."""
    owner, _, storage = runtime
    storage.release.set()
    assert owner.close(timeout=5)
    with pytest.raises(RuntimeFailure, match="^runtime_closed$"):
        owner.admit_background(str(uuid4()), lambda: None)


def test_a_background_job_never_blocks_another_document(runtime):
    """A single background worker is a capacity choice, not an app-wide lock."""
    owner, checkpoints, storage = runtime
    busy, other = str(uuid4()), str(uuid4())
    release, started = Event(), Event()
    owner.admit_background(busy, held(release, started))
    assert started.wait(5)
    # Reading another document goes through the same owner and must not wait.
    assert owner.inspect_document(other, lambda: "read") == "read"
    release.set()
    storage.release.set()
    assert owner.close(timeout=5)


def test_background_batches_run_one_at_a_time(runtime):
    """Bounded means bounded: the second batch waits rather than running now."""
    owner, _, storage = runtime
    first_release, first_started = Event(), Event()
    second_release, second_started = Event(), Event()
    owner.admit_background(str(uuid4()), held(first_release, first_started))
    assert first_started.wait(5)
    owner.admit_background(str(uuid4()), held(second_release, second_started))
    assert not second_started.wait(0.2), "the worker is already busy"
    first_release.set()
    assert second_started.wait(5), "and it starts as soon as the worker is free"
    second_release.set()
    storage.release.set()
    assert owner.close(timeout=5)


def test_an_overrunning_job_is_reported_rather_than_left_hanging(runtime):
    """Close returns a plain failure; it never waits without a deadline."""
    owner, _, storage = runtime
    release = Event()
    owner.admit_background(str(uuid4()), held(release))
    storage.release.set()
    assert owner.close(timeout=1) is False
    release.set()
    assert owner.close(timeout=5)
