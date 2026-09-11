"""No DB/provider; exercises the same bootstrap used before App resources."""
import json
import os
import subprocess
import sys
from analysis_agent.windows_lifecycle import bootstrap

if len(sys.argv)>2 and sys.argv[2] in {'before_assign_crash','after_assign_crash','old_stop_crash'}:
    import win32job
    mode=sys.argv[2]
    if mode=='old_stop_crash':
        terminate=win32job.TerminateJobObject
        def stopped_then_crash(job,code):
            terminate(job,code)
            print(json.dumps({'fault':'old_job_termination_sent','app_work':False}),flush=True)
            os._exit(91)
        win32job.TerminateJobObject=stopped_then_crash
    else:
        assign=win32job.AssignProcessToJobObject
        def assigned_boundary(job,process):
            if mode=='after_assign_crash': assign(job,process)
            print(json.dumps({'fault':mode,'app_work':False}),flush=True)
            os._exit(91)
        win32job.AssignProcessToJobObject=assigned_boundary

if len(sys.argv)>2 and sys.argv[2]=='nested_failure':
    import win32api,win32job
    outer = win32job.CreateJobObject(None,'Local\\Caliburn.'+sys.argv[1]+'.Outer')
    win32job.SetInformationJobObject(outer,win32job.JobObjectBasicUIRestrictions,{'UIRestrictionsClass':win32job.JOB_OBJECT_UILIMIT_HANDLES})
    win32job.AssignProcessToJobObject(outer,win32api.GetCurrentProcess())
if len(sys.argv)>2 and sys.argv[2]=='assignment_failure':
    import win32api,win32job
    actual_assign = win32job.AssignProcessToJobObject
    def deny_assignment(job,process):
        restricted = win32api.DuplicateHandle(win32api.GetCurrentProcess(),job,
            win32api.GetCurrentProcess(),win32job.JOB_OBJECT_QUERY,False,0)
        try:
            return actual_assign(restricted,process)
        finally:
            restricted.Close()
    win32job.AssignProcessToJobObject = deny_assignment

owner = bootstrap(sys.argv[1], mutex_timeout=.2, cleanup_timeout=2)
import win32api, win32con, win32job
child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'],
    close_fds=True, creationflags=subprocess.CREATE_NO_WINDOW)
handle = win32api.OpenProcess(win32con.PROCESS_QUERY_INFORMATION, False, child.pid)
member = win32job.IsProcessInJob(handle, owner.job)
handle.Close()
print(json.dumps({'ready': True, 'member': win32job.IsProcessInJob(win32api.GetCurrentProcess(), owner.job),
    'handle_inheritable': bool(win32api.GetHandleInformation(owner.job) & 1),
    'native_member': member, 'native_pid': child.pid, 'proof': owner.diagnostics}), flush=True)
command = sys.stdin.readline().strip()
if command == 'crash':
    os._exit(17)
if command == 'abandon':
    # Fault injection only: end the mutex-owning OS thread while another API
    # thread and the Node analogue remain alive. No ctypes in product code.
    from threading import Thread, Event
    Thread(target=Event().wait).start()
    import ctypes
    ctypes.windll.kernel32.ExitThread(0)
# Orderly resource close precedes process exit; Job itself stays alive to exit.
child.terminate(); child.wait(timeout=5)
