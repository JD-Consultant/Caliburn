"""Single-attempt fixed Node bridge. Node receives no database or model secrets."""
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
from threading import Event, Thread, RLock
from dataclasses import dataclass, field
import time
from jsonschema import ValidationError

from analysis_agent.jd_contract import PROFILE, validate
from analysis_agent.jd_types import JdCandidate


class JdEngineFailure(RuntimeError):
    def __init__(self, code='engine_failed', *, quiescent=True, command_index=None):
        super().__init__('Fixed JD engine failed: ' + code)
        self.code, self.quiescent, self.command_index = code, quiescent, command_index


@dataclass
class _NativeCall:
    reap: object
    budget: float
    process: object = None
    threads: list = field(default_factory=list)
    ready: bool = False
    cleanup_pending: bool = False
    lock: object = field(default_factory=RLock)


class JdNativeCalls:
    """Ephemeral handles, never a receipt or a durable execution registry."""
    def __init__(self):
        self._entries = {}
        self._lock = RLock()

    @property
    def quiescent(self):
        with self._lock:
            return not self._entries

    def snapshot(self):
        with self._lock:
            return tuple({'spawning': not c.ready,
                          'process_present': c.process is not None,
                          'io_alive': sum(t.is_alive() for t in c.threads)}
                         for c in self._entries.values())

    @property
    def blocked(self):
        with self._lock:
            return any(c.cleanup_pending for c in self._entries.values())

    def register(self, reap, budget):
        token, call = object(), _NativeCall(reap, budget)
        with self._lock:
            if any(c.cleanup_pending for c in self._entries.values()):
                raise JdEngineFailure('engine_failed',quiescent=False)
            self._entries[token] = call
        return token, call

    def finish(self, token, *, terminate=False):
        with self._lock:
            call = self._entries.get(token)
        if call is None:
            return True
        with call.lock:
            call.cleanup_pending = True
            if not call.ready:
                return False
            process = call.process
            if process is not None:
                if process.poll() is None and (not terminate or not call.reap(process)):
                    return False
                deadline = time.monotonic() + call.budget
                for thread in call.threads:
                    if thread.ident is not None:
                        thread.join(max(0, deadline - time.monotonic()))
                if any(t.is_alive() for t in call.threads):
                    return False
                for pipe in (process.stdin, process.stdout, process.stderr):
                    if pipe is not None and not pipe.closed:
                        pipe.close()
            with self._lock:
                self._entries.pop(token, None)
            return True

    def cleanup(self):
        with self._lock:
            tokens = tuple(self._entries)
        results = [self.finish(token, terminate=True) for token in tokens]
        return all(results) and self.quiescent


class JdEngine:
    def __init__(self, *, timeout=30, cleanup_timeout=5, max_bytes=16 * 1024 * 1024):
        if not all(math.isfinite(x) and x > 0 for x in (timeout, cleanup_timeout, max_bytes)):
            raise ValueError('Engine limits must be positive and finite')
        self.timeout, self.cleanup_timeout, self.max_bytes = timeout, cleanup_timeout, int(max_bytes)
        self.node = shutil.which('node')
        self.entry = Path(__file__).resolve().parents[3] / 'jd-editor/native/dist/bridge.js'
        self.native_calls = JdNativeCalls()

    def _call(self, entry, request, *, cancel=None, native_calls=None):
        names = {'transform': 'JdPlateTransform', 'validate-value': 'JdPlateValidateValue',
                 'read-selection': 'JdPlateReadSelection'}
        name = names[entry]
        started = time.monotonic()
        try:
            validate(name + 'Request', request)
            data = json.dumps(request, ensure_ascii=False, allow_nan=False).encode('utf-8')
        except (ValueError, TypeError, ValidationError) as exc:
            raise JdEngineFailure('invalid_input') from exc
        if len(data) > self.max_bytes or not self.node or not self.entry.is_file():
            raise JdEngineFailure()
        if cancel and cancel.is_set():
            raise JdEngineFailure('cancelled')
        if time.monotonic() - started >= self.timeout:
            raise JdEngineFailure('engine_timeout')
        # Allow only OS runtime necessities. In particular no inherited DSN,
        # provider settings, original interview text, NODE_OPTIONS or loader.
        env = {k: v for k, v in os.environ.items() if k.upper() in
               {'SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP', 'PATH', 'PATHEXT'}}
        owner = native_calls if native_calls is not None else self.native_calls
        if owner.blocked:
            raise JdEngineFailure('engine_failed',quiescent=False)
        token, call = owner.register(lambda p: self._reap(p), self.cleanup_timeout)
        try:
            process = subprocess.Popen([self.node, str(self.entry), entry], shell=False,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env,
                close_fds=True,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            call.process = process
        except BaseException as exc:
            call.ready = True
            owner.finish(token)
            if isinstance(exc, OSError):
                raise JdEngineFailure() from exc
            raise
        overflow, io_error = Event(), Event()
        output = bytearray()

        def read(stream, limit, collect):
            size = 0
            try:
                while chunk := stream.read(8192):
                    size += len(chunk)
                    if size > limit:
                        overflow.set()
                        break
                    if collect:
                        output.extend(chunk)
            except OSError:
                io_error.set()
            finally:
                stream.close()

        def write():
            try:
                process.stdin.write(data)
            except OSError:
                io_error.set()
            finally:
                process.stdin.close()

        failure = None
        try:
            threads = [Thread(target=read, args=(process.stdout, self.max_bytes, True), daemon=True),
                       Thread(target=read, args=(process.stderr, 8192, False), daemon=True),
                       Thread(target=write, daemon=True)]
            call.threads = threads
            for thread in threads:
                thread.start()
            call.ready = True
            while process.poll() is None:
                if overflow.is_set() or io_error.is_set():
                    failure = 'engine_failed'
                    break
                if cancel and cancel.is_set():
                    failure = 'cancelled'
                    break
                if time.monotonic() - started >= self.timeout:
                    failure = 'engine_timeout'
                    break
                time.sleep(min(.01, max(.001, self.timeout - (time.monotonic() - started))))
        except BaseException:
            call.ready = True
            owner.finish(token, terminate=True)
            raise
        if failure:
            quiet = owner.finish(token, terminate=True)
            raise JdEngineFailure(failure, quiescent=quiet)
        quiet = owner.finish(token)
        if process.returncode != 0 or overflow.is_set() or io_error.is_set() or not quiet:
            raise JdEngineFailure(quiescent=quiet)
        try:
            result = validate(name + 'Result', json.loads(output))
        except (ValueError, TypeError, ValidationError) as exc:
            raise JdEngineFailure() from exc
        if time.monotonic() - started >= self.timeout:
            raise JdEngineFailure('engine_timeout')
        if not result['ok']:
            error = result['error']
            raise JdEngineFailure(error['code'], command_index=error['command_index'])
        return result

    def _reap(self, process):
        for action in (process.terminate, process.kill):
            try:
                action()
                process.wait(timeout=self.cleanup_timeout)
                return True
            except subprocess.TimeoutExpired:
                continue
            except OSError:
                if process.poll() is not None:
                    return True
        return process.poll() is not None

    def validate_value(self, value, *, cancel=None, native_calls=None):
        r = self._call('validate-value', {'profile': PROFILE, 'value': value}, cancel=cancel, native_calls=native_calls)
        return JdCandidate(r['value'], r['native_operations'], r['affected_element_ids'])

    def transform(self, value, commands, *, cancel=None, native_calls=None):
        r = self._call('transform', {'profile': PROFILE, 'base_value': value, 'commands': commands}, cancel=cancel, native_calls=native_calls)
        return JdCandidate(r['value'], r['native_operations'], r['affected_element_ids'])

    def selection(self, value, selection, *, cancel=None, native_calls=None):
        return self._call('read-selection', {'profile': PROFILE, 'value': value, 'range': selection}, cancel=cancel, native_calls=native_calls)
