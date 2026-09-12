"""One local installation/session: bootstrap before any App resources exist.

The Win32 mutex serializes host generations; the exact old Job's zero active
process count proves prior managed execution stopped. Neither fact resolves a
PostgreSQL transaction. No PID registry, database authority, or process-tree
enumeration is introduced here. This entry point is for a dedicated host process,
not a reusable context manager inside a test runner or another application.
"""

import math
import os
import sys
import threading
import time
from uuid import UUID


class HostError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


_attempted = False
_lease = None
_retained = []
_constructor = object()


def _names(instance_key):
    prefix = "Local\\Caliburn.Relational." + instance_key
    return prefix + ".HostMutex", prefix + ".HostJob"


class _Win32:
    """Only the Win32 calls required by this bounded host lifecycle."""

    def __init__(self):
        import pywintypes
        import win32api
        import win32con
        import win32event
        import win32job
        self.types, self.api, self.con = pywintypes, win32api, win32con
        self.event, self.job = win32event, win32job

    def create_mutex(self, name):
        # NULL attributes use the creator token's default DACL and explicitly
        # produce a non-inheritable handle. A guessed user-only DACL breaks
        # restricted tokens, whose access must pass a second SID check.
        return self.event.CreateMutex(None, False, name)

    def wait_mutex(self, handle, milliseconds):
        return self.event.WaitForSingleObject(handle, milliseconds)

    def release_mutex(self, handle):
        self.event.ReleaseMutex(handle)

    def open_job(self, name):
        try:
            return self.job.OpenJobObject(self.job.JOB_OBJECT_QUERY | self.job.JOB_OBJECT_TERMINATE,
                                          False, name)
        except self.types.error as error:
            if error.winerror == 2:  # Only ERROR_FILE_NOT_FOUND means no prior named job.
                return None
            raise

    def terminate_job(self, handle):
        self.job.TerminateJobObject(handle, 1)

    def active_processes(self, handle):
        return self.job.QueryInformationJobObject(handle,
            self.job.JobObjectBasicAccountingInformation)["ActiveProcesses"]

    def create_job(self, name):
        self.api.SetLastError(0)
        handle = self.job.CreateJobObject(None, name)
        return handle, self.api.GetLastError() == 183  # ERROR_ALREADY_EXISTS

    def configure_job(self, handle):
        info = self.job.QueryInformationJobObject(handle, self.job.JobObjectExtendedLimitInformation)
        info["BasicLimitInformation"]["LimitFlags"] = self.job.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        self.job.SetInformationJobObject(handle, self.job.JobObjectExtendedLimitInformation, info)
        flags = self.job.QueryInformationJobObject(handle,
            self.job.JobObjectExtendedLimitInformation)["BasicLimitInformation"]["LimitFlags"]
        if flags != self.job.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE:
            raise HostError("host_containment_failed")
        if self.api.GetHandleInformation(handle) & self.con.HANDLE_FLAG_INHERIT:
            raise HostError("host_containment_failed")

    def assign_self(self, handle):
        self.job.AssignProcessToJobObject(handle, self.api.GetCurrentProcess())

    def is_self_in_job(self, handle):
        return self.job.IsProcessInJob(self.api.GetCurrentProcess(), handle)


class HostLease:
    """Process-lifetime proof, usable by local workers; no early close operation."""

    def __init__(self, token, native, job, mutex, instance_key):
        if token is not _constructor:
            raise HostError("host_lease_invalid")
        self._native, self._job, self._mutex = native, job, mutex
        self._instance_key = instance_key
        self._pid = os.getpid()
        self._owner = threading.main_thread()
        self._owner_ident = self._owner.ident

    def require_previous_stopped(self) -> None:
        """Nonblocking local capability check, never caller-supplied stopped=True."""
        if (self is not _lease or self._pid != os.getpid()
                or self._owner is not threading.main_thread()
                or self._owner.ident != self._owner_ident or not self._owner.is_alive()):
            raise HostError("host_lease_invalid")
        try:
            if not self._native.is_self_in_job(self._job):
                raise HostError("host_lease_invalid")
        except Exception:
            raise HostError("host_lease_invalid") from None


def _close(handle):
    if handle is not None:
        try:
            handle.Close()
        except Exception:
            pass


def bootstrap_host(instance_key: str, timeout: float = 10.0) -> HostLease:
    """Admit one dedicated Windows host; any failure requires that host to exit.

The installation key is trusted fixed configuration, shared by every entry point
using that installation's database. Local namespace supports one Windows login
session, not multiple sessions/installations sharing the same persistence owner.
"""
    global _attempted, _lease
    try:
        valid_key = type(instance_key) is str and str(UUID(instance_key)) == instance_key
    except ValueError:
        valid_key = False
    if (not valid_key or type(timeout) not in (int, float)
            or not math.isfinite(timeout) or not 0 <= timeout <= 60):
        raise HostError("invalid_host_configuration")
    if sys.platform != "win32":
        raise HostError("host_platform_unsupported")
    if threading.current_thread() is not threading.main_thread():
        raise HostError("host_main_thread_required")
    if _attempted:
        raise HostError("host_already_initialized")
    _attempted = True
    mutex = old_job = new_job = None
    owned = assigned = False
    native = None
    deadline = time.monotonic() + timeout
    try:
        native = _Win32()
        mutex_name, job_name = _names(instance_key)
        mutex = native.create_mutex(mutex_name)
        status = native.wait_mutex(mutex, max(0, math.ceil((deadline - time.monotonic()) * 1000)))
        if status == 258:  # WAIT_TIMEOUT
            raise HostError("host_already_running")
        if status not in (0, 128):  # WAIT_OBJECT_0 / WAIT_ABANDONED
            raise HostError("host_bootstrap_failed")
        owned = True
        # Abandonment proves only the mutex-owning thread ended. Always inspect
        # the exact old Job while this new process is still outside that Job.
        old_job = native.open_job(job_name)
        if old_job is not None:
            native.terminate_job(old_job)
            while native.active_processes(old_job) != 0:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise HostError("host_previous_group_unconfirmed")
                time.sleep(min(0.01, remaining))
            old_job.Close()
            old_job = None
        while True:
            new_job, existed = native.create_job(job_name)
            if not existed:
                break
            # The zero-member old object can briefly retain other references.
            # Never reuse it or terminate again: wait within the same startup
            # budget for its name to denote a freshly created kernel object.
            new_job.Close()
            new_job = None
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise HostError("host_job_conflict")
            time.sleep(min(0.01, remaining))
        native.configure_job(new_job)
        native.assign_self(new_job)
        assigned = True
        # PyHANDLE GC closes handles. Detach transfers their remaining lifetime
        # to the OS process handle table, including interpreter finalization.
        # Strong retention also covers the exceptional detach-allocation path.
        _retained.extend((new_job, mutex))
        raw_job, raw_mutex = new_job.Detach(), mutex.Detach()
        if not native.is_self_in_job(raw_job):
            raise HostError("host_containment_failed")
        _lease = HostLease(_constructor, native, raw_job, raw_mutex, instance_key)
        return _lease
    except HostError:
        raise
    except Exception:
        raise HostError("host_bootstrap_failed") from None
    finally:
        _close(old_job)
        if not assigned:
            _close(new_job)
            if owned and native is not None:
                try:
                    native.release_mutex(mutex)
                except Exception:
                    pass
            _close(mutex)
