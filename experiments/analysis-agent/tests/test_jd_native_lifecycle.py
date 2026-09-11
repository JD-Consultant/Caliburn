"""NL02–04: retained native work is independent of Python/tool completion."""
import subprocess
import sys
from threading import Event, Thread

import pytest
from analysis_agent.jd_engine import JdEngine, JdEngineFailure

VALUE = [{'id': 'p', 'type': 'p', 'children': [{'text': ''}]}]


def test_thread_construction_baseexception_keeps_cleanup_reachable(monkeypatch):
    import analysis_agent.jd_engine as module
    engine=JdEngine(timeout=.2,cleanup_timeout=.2)
    def interrupted(*args,**kwargs):
        raise KeyboardInterrupt('I/O setup interrupted')
    monkeypatch.setattr(module,'Thread',interrupted)
    with pytest.raises(KeyboardInterrupt):
        engine.validate_value(VALUE)
    assert engine.native_calls.cleanup(), 'Successful Popen must remain cleanable when I/O construction fails'
    assert engine.native_calls.quiescent


def test_exited_process_with_live_io_never_becomes_quiescent():
    from analysis_agent.jd_engine import JdNativeCalls
    owner=JdNativeCalls(); release=Event()
    process=subprocess.Popen([sys.executable,'-c','pass'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
        creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    process.wait(timeout=5)
    thread=Thread(target=lambda:release.wait(5));thread.start()
    token,call=owner.register(lambda p:True,.01)
    call.process=process;call.threads=[thread];call.ready=True
    try:
        assert not owner.cleanup() and not owner.quiescent
        assert owner.snapshot()[0]['io_alive']==1
    finally:
        release.set();thread.join(5)
    assert owner.cleanup() and owner.quiescent


def test_unreaped_handle_survives_tool_return_and_explicit_cleanup_uses_same_process(monkeypatch):
    engine = JdEngine(timeout=.2, cleanup_timeout=.2)
    assert hasattr(engine, 'native_calls'), 'Native ownership must survive _call return'
    actual, launched = subprocess.Popen, []
    def launch(argv, **kwargs):
        process = actual([sys.executable, '-c', 'import time; time.sleep(60)'], **kwargs)
        launched.append(process)
        return process
    monkeypatch.setattr(subprocess, 'Popen', launch)
    original_reap = engine._reap
    monkeypatch.setattr(engine, '_reap', lambda process: False)
    try:
        with pytest.raises(JdEngineFailure) as caught:
            engine.validate_value(VALUE)
        assert not caught.value.quiescent
        assert not engine.native_calls.quiescent
        assert len(engine.native_calls.snapshot()) == 1
        with pytest.raises(JdEngineFailure) as second:
            engine.validate_value(VALUE)
        assert not second.value.quiescent and len(launched) == 1
        monkeypatch.setattr(engine, '_reap', original_reap)
        assert engine.native_calls.cleanup()
        assert engine.native_calls.quiescent and len(launched) == 1
        assert launched[0].poll() is not None
    finally:
        # Test cleanup after assertions is not product proof.
        for process in launched:
            if process.poll() is None:
                process.kill(); process.wait()


def test_spawn_in_progress_blocks_quiescence_and_late_return_is_cleaned_once(monkeypatch):
    engine = JdEngine(timeout=.2, cleanup_timeout=.2)
    assert hasattr(engine, 'native_calls'), 'Spawn must register before Popen'
    entered, release, stop = Event(), Event(), Event()
    actual, launched, errors = subprocess.Popen, [], []
    def launch(argv, **kwargs):
        entered.set()
        assert release.wait(5)
        process = actual([sys.executable, '-c', 'import time; time.sleep(60)'], **kwargs)
        launched.append(process)
        return process
    def run():
        try:
            engine.validate_value(VALUE, cancel=stop)
        except BaseException as exc:
            errors.append(exc)
    monkeypatch.setattr(subprocess, 'Popen', launch)
    thread = Thread(target=run)
    thread.start()
    try:
        assert entered.wait(5)
        assert not engine.native_calls.quiescent
        assert not engine.native_calls.cleanup()
        stop.set(); release.set(); thread.join(5)
        assert not thread.is_alive()
        assert len(errors) == 1 and isinstance(errors[0], JdEngineFailure)
        assert errors[0].quiescent and engine.native_calls.quiescent
        assert len(launched) == 1 and launched[0].poll() is not None
    finally:
        release.set(); thread.join(5)
        for process in launched:
            if process.poll() is None:
                process.kill(); process.wait()
