"""A finished native callable is closing even while its owner callback drains."""

from concurrent.futures import Future
from threading import Event
from types import SimpleNamespace

import pytest

from jd_relational.ai_runtime import AiRuntime
from jd_relational.manual_runtime import ForegroundHandle, ForegroundPermit, _Foreground
from test_foreground_runtime import foreground, run_identity


def pending_attempt():
    entry = _Foreground(ForegroundPermit(run_identity()), future=Future())
    handle = ForegroundHandle(entry)
    return entry, handle, SimpleNamespace(handle=handle, closure_error=None)


@pytest.mark.parametrize("completion", ["success", "error", "cancelled"])
def test_finished_future_is_closing_before_owner_callback_is_settled(completion):
    entry, handle, attempt = pending_attempt()
    if completion == "success":
        entry.future.set_result(None)
    elif completion == "error":
        entry.future.set_exception(RuntimeError("synthetic-private-worker-error"))
    else:
        assert entry.future.cancel()
    assert entry.future.done() and not entry.future.running()
    assert not entry.settled.is_set()
    assert handle.execution_running is False
    assert AiRuntime._active_status(attempt) == ("closing", False)
    # The corrected display must not relax ownership/recovery's existing wait.
    with pytest.raises(TimeoutError, match="^foreground_still_running$"):
        handle.wait(0)
    assert not entry.closed


@pytest.mark.parametrize("started", [False, True])
def test_pending_or_running_native_future_remains_active(started):
    entry, handle, attempt = pending_attempt()
    if started:
        assert entry.future.set_running_or_notify_cancel()
    assert not entry.future.done()
    assert handle.execution_running is True
    assert AiRuntime._active_status(attempt) == ("running", False)
    handle.request_stop()
    assert AiRuntime._active_status(attempt) == ("running", True)
    assert not entry.future.cancelled()


def test_finished_foreground_wait_and_failed_closure_are_distinct():
    entry, handle, attempt = pending_attempt()
    entry.future.set_result(None)
    entry.settled.set()
    assert handle.wait(0).write_blocked is True
    assert AiRuntime._active_status(attempt) == ("closing", False)
    attempt.closure_error = "run_recovery_required"
    assert AiRuntime._active_status(attempt) == ("recovery_required", False)
    handle.request_stop()
    assert not handle.permit.stop_event.is_set()  # No late cancellation fiction.


@pytest.mark.parametrize("attempt", [None, SimpleNamespace(handle=None)])
def test_absent_local_future_never_proves_execution_or_closure(attempt):
    assert AiRuntime._active_status(attempt) == ("recovery_required", None)


def test_real_owner_callback_can_pause_after_future_completion_without_reporting_running(foreground, monkeypatch):
    owner, _, _, _, handles = foreground
    work_entered, work_release = Event(), Event()
    callback_entered, callback_release = Event(), Event()
    original = owner._foreground_finished

    def callback(slot, entry, future):
        callback_entered.set()
        assert callback_release.wait(3), "test must release the native done callback"
        original(slot, entry, future)

    def work(_permit):
        work_entered.set()
        assert work_release.wait(3), "test must release the callable"

    monkeypatch.setattr(owner, "_foreground_finished", callback)
    handle = owner.start_foreground(run_identity(), work)
    handles.append(handle)
    try:
        assert work_entered.wait(2)
        assert handle.execution_running is True
        work_release.set()
        assert callback_entered.wait(2)
        assert handle._entry.future.done()
        assert not handle._entry.settled.is_set()
        assert handle.execution_running is False
        assert AiRuntime._active_status(SimpleNamespace(handle=handle, closure_error=None)) == ("closing", False)
        with pytest.raises(TimeoutError, match="^foreground_still_running$"):
            handle.wait(0)
    finally:
        work_release.set()
        callback_release.set()
    assert handle.wait(2).write_blocked is True
