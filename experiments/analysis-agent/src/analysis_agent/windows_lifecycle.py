"""Windows API/child lifetime containment. No database or document authority.

The main thread retains both handles until process exit. Closing our own Job
as a normal context-manager resource would terminate this API prematurely.
"""
from dataclasses import dataclass
import math
import os
import re
import threading
import time

_owner = None


class LifecycleError(RuntimeError):
    pass


@dataclass(frozen=True)
class WindowsLifecycle:
    key: str
    mutex: object
    job: object
    thread_id: int
    prior_object: str

    @property
    def diagnostics(self):
        return {'key': self.key, 'version': 1, 'prior_group_stopped': True,
                'prior_object': self.prior_object, 'pid': os.getpid()}

    def verify(self):
        import win32api, win32job
        if self is not _owner or not win32job.IsProcessInJob(win32api.GetCurrentProcess(), self.job):
            raise LifecycleError('managed_membership_unavailable')
        return self


def require_bootstrap():
    if _owner is None:
        raise LifecycleError('bootstrap_required_before_app_resources')
    return _owner.verify()


def bootstrap(key=None, *, mutex_timeout=2, cleanup_timeout=10):
    """One explicit bounded startup, called before any App work on main thread.

    The configured installation must have completed controlled legacy shutdown.
    An absent exact object proves prior exit only for this managed installation.
    """
    global _owner
    key = key or os.environ.get('Q019_LIFECYCLE_INSTALLATION')
    if not isinstance(key, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', key):
        raise LifecycleError('stable_installation_key_required')
    if threading.current_thread() is not threading.main_thread():
        raise LifecycleError('bootstrap_requires_main_thread')
    if _owner is not None:
        if _owner.key != key:
            raise LifecycleError('installation_key_conflict')
        return _owner.verify()
    if not all(math.isfinite(v) and v > 0 for v in (mutex_timeout, cleanup_timeout)):
        raise ValueError('Lifecycle budgets must be positive and finite')
    import pywintypes, win32api, win32con, win32event, win32job, win32security
    token = win32security.OpenProcessToken(win32api.GetCurrentProcess(), win32con.TOKEN_QUERY)
    try:
        sid = win32security.ConvertSidToStringSid(win32security.GetTokenInformation(token, win32security.TokenUser)[0])
    finally:
        token.Close()
    security = pywintypes.SECURITY_ATTRIBUTES()
    security.bInheritHandle = False
    security.SECURITY_DESCRIPTOR = win32security.ConvertStringSecurityDescriptorToSecurityDescriptor(
        'D:P(A;;GA;;;SY)(A;;GA;;;' + sid + ')', win32security.SDDL_REVISION_1)
    name = 'Local\\Caliburn.' + key
    mutex = win32event.CreateMutex(security, False, name + '.ApiMutex')
    owns_mutex, job, assigned = False, None, False
    try:
        waited = win32event.WaitForSingleObject(mutex, int(mutex_timeout * 1000))
        if waited not in (win32event.WAIT_OBJECT_0, win32event.WAIT_ABANDONED):
            raise LifecycleError('already_running')
        owns_mutex = True
        prior = 'absent'
        try:
            old = win32job.OpenJobObject(win32job.JOB_OBJECT_QUERY | win32job.JOB_OBJECT_TERMINATE,
                                         False, name + '.ApiJob')
        except pywintypes.error as exc:
            if exc.winerror != 2:
                raise LifecycleError('prior_job_open_failed') from exc
        else:
            try:
                win32job.TerminateJobObject(old, 1)
                deadline = time.monotonic() + cleanup_timeout
                while win32job.QueryInformationJobObject(old, win32job.JobObjectBasicAccountingInformation)['ActiveProcesses']:
                    if time.monotonic() >= deadline:
                        raise LifecycleError('prior_job_stop_unconfirmed')
                    time.sleep(min(.01, max(0, deadline - time.monotonic())))
                prior = 'active_zero'
            finally:
                old.Close()
        job = win32job.CreateJobObject(security, name + '.ApiJob')
        if win32api.GetLastError() == 183:
            raise LifecycleError('prior_job_object_still_exists')
        info = win32job.QueryInformationJobObject(job, win32job.JobObjectExtendedLimitInformation)
        info['BasicLimitInformation']['LimitFlags'] = win32job.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        win32job.SetInformationJobObject(job, win32job.JobObjectExtendedLimitInformation, info)
        checked = win32job.QueryInformationJobObject(job, win32job.JobObjectExtendedLimitInformation)
        if checked['BasicLimitInformation']['LimitFlags'] != win32job.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE:
            raise LifecycleError('job_limits_unconfirmed')
        # Retain before assign: after membership begins no finally may close it.
        _owner = WindowsLifecycle(key, mutex, job, threading.get_ident(), prior)
        win32job.AssignProcessToJobObject(job, win32api.GetCurrentProcess())
        assigned = True
        return _owner.verify()
    except BaseException:
        if not assigned:
            _owner = None
            if job is not None:
                job.Close()
            if owns_mutex:
                win32event.ReleaseMutex(mutex)
            mutex.Close()
        raise
