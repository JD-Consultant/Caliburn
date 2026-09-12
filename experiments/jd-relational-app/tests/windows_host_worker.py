"""Synthetic native host/child helpers. Never run inside the pytest process."""

import json
import os
from pathlib import Path
import subprocess
import sys
import threading

import win32api
import win32con
import win32event
import win32job

from jd_relational.windows_host import HostError, _Win32, _names, bootstrap_host


def emit(value):
    print(json.dumps(value), flush=True)


def main():
    mode, key = sys.argv[1:3]
    mutex_name, job_name = _names(key)
    outer = win32job.IsProcessInJob(win32api.GetCurrentProcess(), None)
    if mode == "child":
        handle = win32job.OpenJobObject(win32job.JOB_OBJECT_QUERY, False, job_name)
        try:
            member = win32job.IsProcessInJob(win32api.GetCurrentProcess(), handle)
        finally:
            handle.Close()
        emit({"child_pid": os.getpid(), "member": member})
        threading.Event().wait()  # No EOF/parent pipe makes this child exit normally.
        return
    if mode == "abandoned":
        # Synthetic old generation: mutex-owner thread dies while its process
        # remains alive. This is not an allowed new bootstrap entry point.
        native = _Win32()
        job, exists = native.create_job(job_name)
        assert not exists
        native.configure_job(job)
        native.assign_self(job)
        retained = [job.Detach()]

        def abandon():
            mutex = native.create_mutex(mutex_name)
            assert native.wait_mutex(mutex, 0) == win32event.WAIT_OBJECT_0
            retained.append(mutex.Detach())

        thread = threading.Thread(target=abandon)
        thread.start()
        thread.join()
        assert len(retained) == 2
        emit({"ready": True, "pid": os.getpid(), "abandoned_owner": True})
        threading.Event().wait()
        return
    try:
        lease = bootstrap_host(key, timeout=float(sys.argv[3]) if len(sys.argv) > 3 else 5)
        lease.require_previous_stopped()
        checked = []

        def worker_check():
            lease.require_previous_stopped()
            checked.append(True)

        worker = threading.Thread(target=worker_check)
        worker.start()
        worker.join()
        assert checked == [True]
        assert win32api.GetHandleInformation(lease._job) & win32con.HANDLE_FLAG_INHERIT == 0
        assert win32api.GetHandleInformation(lease._mutex) & win32con.HANDLE_FLAG_INHERIT == 0
        try:
            bootstrap_host(key)
        except HostError as error:
            assert error.code == "host_already_initialized"
        else:
            raise AssertionError("Second same-process bootstrap was allowed.")
        payload = {"ready": True, "pid": os.getpid(), "outer_job": outer, "worker_valid": True,
            "member": win32job.IsProcessInJob(win32api.GetCurrentProcess(), lease._job),
            "handles_inherit": False, "early_close_api": hasattr(lease, "close")}
        if mode == "with_child":
            child = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "child", key],
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, encoding="utf-8", close_fds=True, creationflags=subprocess.CREATE_NO_WINDOW)
            payload["child"] = json.loads(child.stdout.readline())
        emit(payload)
        if mode != "once":
            command = sys.stdin.readline().strip()
            if command == "crash":
                os._exit(17)
            assert command == "stop"
        # Deliberately do not close/release lease handles: OS process exit owns
        # them after all Python cleanup. A normal return is part of the test.
    except HostError as error:
        emit({"error": error.code})
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
