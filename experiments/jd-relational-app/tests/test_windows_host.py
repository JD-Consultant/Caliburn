"""Windows-only host ownership; native assignments run in fresh helpers only."""

import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
from uuid import uuid4

import pytest

from jd_relational import windows_host as host
from jd_relational.windows_host import HostError, bootstrap_host


pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="native Windows host only")


def test_invalid_key_never_enters_native_bootstrap():
    with pytest.raises(HostError, match="^invalid_host_configuration$"):
        bootstrap_host("not-an-installation-uuid")


@pytest.mark.parametrize("timeout", [True, -1, 61, float("nan"), float("inf")])
def test_invalid_budget_never_enters_native_bootstrap(timeout):
    with pytest.raises(HostError, match="^invalid_host_configuration$"):
        bootstrap_host(str(uuid4()), timeout)


class Handle:
    def __init__(self, name, calls):
        self.name, self.calls, self.closed = name, calls, False

    def Close(self):
        self.closed = True
        self.calls.append("close:" + self.name)

    def Detach(self):
        self.calls.append("detach:" + self.name)
        return self.name


class FakeWin32:
    """Branch-only evidence; this adapter never assigns pytest to a real Job."""
    def __init__(self):
        self.calls = []
        self.wait_result = 0
        self.old = True
        self.active = [1, 0]
        self.exists = False
        self.failure = None
        self.member = True

    def step(self, phase):
        self.calls.append(phase)
        if self.failure == phase:
            raise OSError("synthetic private Windows error detail")

    def create_mutex(self, name):
        self.step("mutex")
        return Handle("mutex", self.calls)

    def wait_mutex(self, value, timeout):
        self.step("wait")
        assert 0 <= timeout <= 60000
        return self.wait_result

    def release_mutex(self, value):
        self.step("release")

    def open_job(self, name):
        self.step("open")
        return Handle("old", self.calls) if self.old else None

    def terminate_job(self, value):
        assert value.name == "old" and "assign" not in self.calls
        self.step("terminate")

    def active_processes(self, value):
        assert value.name == "old" and "assign" not in self.calls
        self.step("query")
        return self.active.pop(0) if len(self.active) > 1 else self.active[0]

    def create_job(self, name):
        self.step("create")
        exists = self.exists.pop(0) if isinstance(self.exists, list) else self.exists
        return Handle("new", self.calls), exists

    def configure_job(self, value):
        self.step("configure")

    def assign_self(self, value):
        self.step("assign")

    def is_self_in_job(self, value):
        self.step("member")
        return self.member


@pytest.fixture
def fake(monkeypatch):
    native = FakeWin32()
    monkeypatch.setattr(host, "_attempted", False)
    monkeypatch.setattr(host, "_lease", None)
    monkeypatch.setattr(host, "_retained", [])
    monkeypatch.setattr(host, "_Win32", lambda: native)
    return native


def test_main_thread_only_before_any_native_mutation(fake):
    failures = []
    def try_from_worker():
        try:
            bootstrap_host(str(uuid4()))
        except HostError as error:
            failures.append(error.code)
    thread = threading.Thread(target=try_from_worker)
    thread.start()
    thread.join(2)
    assert not thread.is_alive() and failures == ["host_main_thread_required"]
    assert fake.calls == []


def test_fake_old_group_zero_precedes_assignment_and_handles_never_close(fake):
    fake.wait_result = 128  # Abandoned does not skip old-group cleanup.
    lease = bootstrap_host(str(uuid4()))
    lease.require_previous_stopped()
    assert fake.calls.index("close:old") < fake.calls.index("create") < fake.calls.index("assign")
    assert fake.calls.count("query") == 2
    assert not {"close:new", "close:mutex", "release"}.intersection(fake.calls)
    assert not hasattr(lease, "close")
    with pytest.raises(HostError, match="^host_already_initialized$"):
        bootstrap_host(str(uuid4()))


@pytest.mark.parametrize("phase", ["mutex", "wait", "open", "terminate", "query", "create", "configure", "assign", "member"])
def test_fake_native_errors_are_fixed_and_never_issue_lease(fake, phase):
    fake.failure = phase
    with pytest.raises(HostError, match="^host_bootstrap_failed$") as error:
        bootstrap_host(str(uuid4()))
    assert error.value.__suppress_context__ and "private" not in str(error.value)
    assert host._lease is None
    if phase == "member":
        assert not {"close:new", "close:mutex", "release"}.intersection(fake.calls)
    elif "wait" in fake.calls and phase != "wait":
        assert "release" in fake.calls


def test_fake_mutex_timeout_never_touches_or_terminates_old_job(fake):
    fake.wait_result = 258
    with pytest.raises(HostError, match="^host_already_running$"):
        bootstrap_host(str(uuid4()), timeout=0)
    assert fake.calls == ["mutex", "wait", "close:mutex"]


def test_fake_cleanup_budget_never_claims_zero_or_assigns_new_host(fake):
    fake.active = [1]
    with pytest.raises(HostError, match="^host_previous_group_unconfirmed$"):
        bootstrap_host(str(uuid4()), timeout=0)
    assert "assign" not in fake.calls and "close:old" in fake.calls


def test_fake_existing_terminated_object_is_never_reused(fake):
    fake.exists = True
    fake.active = [0]
    with pytest.raises(HostError, match="^host_job_conflict$"):
        bootstrap_host(str(uuid4()), timeout=0)
    assert "assign" not in fake.calls and "close:new" in fake.calls


def test_fake_name_retirement_wait_does_not_repeat_termination_or_assign_old_object(fake):
    fake.exists = [True, False]
    lease = bootstrap_host(str(uuid4()))
    lease.require_previous_stopped()
    assert fake.calls.count("terminate") == 1 and fake.calls.count("create") == 2
    assert fake.calls.count("assign") == 1
    assert fake.calls.index("close:new") < fake.calls.index("assign")


def test_fake_lease_rechecks_membership_and_rejects_unissued_objects(fake):
    lease = bootstrap_host(str(uuid4()))
    fake.member = False
    with pytest.raises(HostError, match="^host_lease_invalid$"):
        lease.require_previous_stopped()
    with pytest.raises(HostError, match="^host_lease_invalid$"):
        host.HostLease(object(), fake, "invented-job", "invented-mutex", str(uuid4()))


@pytest.mark.parametrize("failure", ["pid", "main_thread_dead", "copied_lease", "query_error"])
def test_fake_lease_checks_process_owner_and_exact_capability(fake, monkeypatch, failure):
    from copy import copy
    lease = bootstrap_host(str(uuid4()))
    with monkeypatch.context() as scope:
        if failure == "pid":
            scope.setattr(host.os, "getpid", lambda: lease._pid + 1)
        elif failure == "main_thread_dead":
            scope.setattr(lease._owner, "is_alive", lambda: False)
        elif failure == "copied_lease":
            lease = copy(lease)
        else:
            fake.failure = "member"
        with pytest.raises(HostError, match="^host_lease_invalid$"):
            lease.require_previous_stopped()


@pytest.fixture
def helpers():
    processes = []
    worker = Path(__file__).with_name("windows_host_worker.py")
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONPATH": str(worker.parents[1] / "src")}

    def launch(mode, key, timeout=5):
        process = subprocess.Popen([sys.executable, str(worker), mode, key, str(timeout)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", env=env, close_fds=True,
            creationflags=subprocess.CREATE_NO_WINDOW)
        processes.append(process)
        return process

    try:
        yield launch
    finally:
        for process in reversed(processes):
            if process.poll() is None:
                # Only this exact test-created Popen handle is ever terminated.
                process.terminate()
            process.wait(timeout=10)
            for stream in (process.stdin, process.stdout, process.stderr):
                stream.close()
            process._handle.Close()  # Release test process reference before later zero-count checks.


def line(process, timeout=8):
    result = queue.Queue()
    def read():
        result.put(process.stdout.readline())
    threading.Thread(target=read, daemon=True).start()
    value = result.get(timeout=timeout)
    assert value, "Native helper exited without a result."
    return json.loads(value)


def stop(process):
    process.stdin.write("stop\n")
    process.stdin.flush()
    assert process.wait(timeout=8) == 0
    process._handle.Close()


def test_native_competition_nested_membership_and_orderly_restart(helpers):
    import win32api
    import win32job
    key = str(uuid4())
    first = helpers("hold", key)
    ready = line(first)
    assert ready["ready"] and ready["member"] and ready["worker_valid"]
    assert ready["outer_job"] == win32job.IsProcessInJob(win32api.GetCurrentProcess(), None)
    assert not ready["handles_inherit"] and not ready["early_close_api"]
    contender = helpers("once", key, timeout=0.1)
    assert line(contender) == {"error": "host_already_running"}
    assert contender.wait(timeout=5) == 1 and first.poll() is None
    stop(first)
    restarted = helpers("once", key)
    assert line(restarted)["member"] and restarted.wait(timeout=5) == 0


def test_native_abandoned_mutex_does_not_mistake_live_old_process_for_stopped(helpers):
    key = str(uuid4())
    old = helpers("abandoned", key)
    assert line(old)["abandoned_owner"] and old.poll() is None
    replacement = helpers("hold", key)
    assert old.wait(timeout=5) != 0
    old._handle.Close()
    ready = line(replacement)
    assert ready.get("member"), ready
    stop(replacement)


def test_native_child_membership_kill_on_parent_exit_and_fresh_recovery(helpers):
    import win32api
    import win32con
    import win32event
    key = str(uuid4())
    parent = helpers("with_child", key)
    ready = line(parent)
    assert ready["child"]["member"]
    child = win32api.OpenProcess(win32con.SYNCHRONIZE, False, ready["child"]["child_pid"])
    try:
        parent.stdin.write("crash\n")
        parent.stdin.flush()
        assert parent.wait(timeout=5) == 17
        parent._handle.Close()
        assert win32event.WaitForSingleObject(child, 5000) == win32event.WAIT_OBJECT_0
    finally:
        child.Close()
    replacement = helpers("once", key)
    assert line(replacement)["member"] and replacement.wait(timeout=5) == 0


def test_native_extra_job_handle_prevents_reuse_until_exact_old_object_is_gone(helpers):
    import win32job
    key = str(uuid4())
    old = helpers("hold", key)
    assert line(old)["member"]
    retained = win32job.OpenJobObject(win32job.JOB_OBJECT_QUERY, False, host._names(key)[1])
    try:
        stop(old)
        assert win32job.QueryInformationJobObject(retained,
            win32job.JobObjectBasicAccountingInformation)["ActiveProcesses"] == 0
        attempt = helpers("once", key, timeout=0.1)
        assert line(attempt) == {"error": "host_job_conflict"}
        assert attempt.wait(timeout=5) == 1
    finally:
        retained.Close()
    replacement = helpers("once", key)
    assert line(replacement)["member"] and replacement.wait(timeout=5) == 0
