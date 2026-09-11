"""Actual kernel containment; test parent observes and injects crashes only."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

import pytest

pytestmark = pytest.mark.skipif(sys.platform != 'win32', reason='Windows kernel acceptance')
WORKER = Path(__file__).with_name('windows_lifecycle_worker.py')


def launch(key, *args):
    return subprocess.Popen([sys.executable, str(WORKER), key,*args], stdin=subprocess.PIPE,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, close_fds=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
        env={**os.environ, 'PYTHONPATH': str(Path(__file__).parents[1] / 'src')})


def test_actual_bootstrap_mutex_competitor_cannot_terminate_live_api():
    assert importlib.util.find_spec('analysis_agent.windows_lifecycle'), 'App bootstrap is absent'
    key = 'test-' + uuid4().hex
    first = launch(key)
    try:
        ready = json.loads(first.stdout.readline())
        assert ready['ready'] and ready['member'] and not ready['handle_inheritable']
        second = launch(key)
        output, error = second.communicate(timeout=10)
        assert second.returncode != 0 and 'already_running' in error
        assert first.poll() is None
    finally:
        first.communicate('exit\n', timeout=10)


def test_actual_bootstrap_after_api_crash_covers_inherited_native_membership():
    assert importlib.util.find_spec('analysis_agent.windows_lifecycle'), 'App bootstrap is absent'
    import win32api, win32event, win32con
    key = 'test-' + uuid4().hex
    first = launch(key)
    ready = json.loads(first.stdout.readline())
    assert ready['ready'] and ready['native_member']
    child_handle = win32api.OpenProcess(win32con.SYNCHRONIZE, False, ready['native_pid'])
    first.communicate('crash\n', timeout=10)
    assert win32event.WaitForSingleObject(child_handle, 5000) == win32event.WAIT_OBJECT_0
    child_handle.Close()
    second = launch(key)
    try:
        raw = second.stdout.readline()
        assert raw, second.stderr.read()
        reopened = json.loads(raw)
        assert reopened['ready'] and reopened['proof']['prior_group_stopped']
        assert reopened['proof']['key'] == key
        assert reopened['proof']['version'] == 1
    finally:
        second.communicate('exit\n', timeout=10)


def test_normal_resources_refuse_unmanaged_entry_before_settings_or_clients():
    result=subprocess.run([sys.executable,'-c',
        'from analysis_agent.api import open_service\nwith open_service(): pass'],
        capture_output=True,text=True,timeout=15,creationflags=subprocess.CREATE_NO_WINDOW)
    assert result.returncode!=0 and 'bootstrap_required_before_app_resources' in result.stderr


def test_abandoned_main_thread_still_requires_product_to_stop_exact_old_job():
    key = 'test-'+uuid4().hex
    first = launch(key)
    ready = json.loads(first.stdout.readline())
    first.stdin.write('abandon\n'); first.stdin.flush()
    second = launch(key)
    output,error = second.communicate(timeout=10)
    assert second.returncode != 0 and 'prior_job_object_still_exists' in error
    assert first.wait(timeout=5) != 0 and ready['native_member']
    first.communicate(timeout=5)
    # Release the observer's terminated-process handle, not a live process.
    del first
    import gc
    gc.collect()
    third = launch(key)
    try:
        reopened = json.loads(third.stdout.readline())
        assert reopened['ready'] and reopened['proof']['prior_group_stopped']
    finally:
        third.communicate('exit\n',timeout=10)


def test_external_old_job_handle_prevents_reuse_until_a_new_explicit_start():
    import win32job
    key = 'test-'+uuid4().hex
    first = launch(key)
    assert json.loads(first.stdout.readline())['ready']
    external = win32job.OpenJobObject(win32job.JOB_OBJECT_QUERY,False,'Local\\Caliburn.'+key+'.ApiJob')
    try:
        first.stdin.write('crash\n'); first.stdin.flush(); first.wait(timeout=5)
        second = launch(key)
        output,error = second.communicate(timeout=10)
        assert second.returncode != 0 and 'prior_job_object_still_exists' in error
    finally:
        external.Close()
        first.communicate(timeout=5)
    third = launch(key)
    try:
        assert json.loads(third.stdout.readline())['ready']
    finally:
        third.communicate('exit\n',timeout=10)


def test_os_assignment_access_failure_exits_before_app_work():
    child = launch('test-'+uuid4().hex,'assignment_failure')
    output,error = child.communicate(timeout=10)
    assert child.returncode != 0 and not output
    assert 'AssignProcessToJobObject' in error


def test_this_machine_supports_nested_job_even_with_outer_handle_ui_limit():
    child = launch('test-'+uuid4().hex,'nested_failure')
    output,error = child.communicate('exit\n',timeout=10)
    assert child.returncode == 0 and json.loads(output)['member']


@pytest.mark.parametrize('mode',['before_assign_crash','after_assign_crash'])
def test_bootstrap_crash_before_app_work_can_reopen_same_installation(mode):
    key='test-'+uuid4().hex
    first=launch(key,mode)
    output,error=first.communicate(timeout=10)
    assert first.returncode==91 and json.loads(output)=={'fault':mode,'app_work':False}
    print(output.strip())
    del first
    import gc
    gc.collect()
    fresh=launch(key)
    try:
        assert json.loads(fresh.stdout.readline())['ready']
    finally:
        fresh.communicate('exit\n',timeout=10)


def test_new_bootstrap_crash_during_old_job_stop_never_claims_app_admission():
    key='test-'+uuid4().hex
    first=launch(key)
    assert json.loads(first.stdout.readline())['ready']
    first.stdin.write('abandon\n');first.stdin.flush()
    second=launch(key,'old_stop_crash')
    output,error=second.communicate(timeout=10)
    assert second.returncode==91 and json.loads(output)=={'fault':'old_job_termination_sent','app_work':False}
    assert first.wait(timeout=5)!=0
    first.communicate(timeout=5)
    print(output.strip())
    del first,second
    import gc
    gc.collect()
    fresh=launch(key)
    try:
        assert json.loads(fresh.stdout.readline())['ready']
    finally:
        fresh.communicate('exit\n',timeout=10)
