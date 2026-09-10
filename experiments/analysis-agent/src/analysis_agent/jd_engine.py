"""Single-attempt fixed Node bridge. Node receives no database or model secrets."""
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
from threading import Event, Thread
import time
from jsonschema import ValidationError

from analysis_agent.jd_contract import PROFILE, validate
from analysis_agent.jd_types import JdCandidate


class JdEngineFailure(RuntimeError):
    def __init__(self, code='engine_failed', *, quiescent=True, command_index=None):
        super().__init__('Fixed JD engine failed: ' + code)
        self.code, self.quiescent, self.command_index = code, quiescent, command_index


class JdEngine:
    def __init__(self, *, timeout=30, cleanup_timeout=5, max_bytes=16 * 1024 * 1024):
        if not all(math.isfinite(x) and x > 0 for x in (timeout, cleanup_timeout, max_bytes)):
            raise ValueError('Engine limits must be positive and finite')
        self.timeout, self.cleanup_timeout, self.max_bytes = timeout, cleanup_timeout, int(max_bytes)
        self.node = shutil.which('node')
        self.entry = Path(__file__).resolve().parents[3] / 'jd-editor/native/dist/bridge.js'

    def _call(self, entry, request, *, cancel=None):
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
        try:
            process = subprocess.Popen([self.node, str(self.entry), entry], shell=False,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        except OSError as exc:
            raise JdEngineFailure() from exc
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
                process.stdin.close()
            except OSError:
                io_error.set()

        threads = [Thread(target=read, args=(process.stdout, self.max_bytes, True), daemon=True),
                   Thread(target=read, args=(process.stderr, 8192, False), daemon=True),
                   Thread(target=write, daemon=True)]
        for thread in threads:
            thread.start()
        failure = None
        try:
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
            self._reap(process)
            raise
        if failure:
            quiet = self._reap(process)
            raise JdEngineFailure(failure, quiescent=quiet)
        for thread in threads:
            thread.join(max(0, self.timeout - (time.monotonic() - started)))
        if process.returncode != 0 or overflow.is_set() or io_error.is_set() or any(t.is_alive() for t in threads):
            raise JdEngineFailure()
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

    def validate_value(self, value, *, cancel=None):
        r = self._call('validate-value', {'profile': PROFILE, 'value': value}, cancel=cancel)
        return JdCandidate(r['value'], r['native_operations'], r['affected_element_ids'])

    def transform(self, value, commands, *, cancel=None):
        r = self._call('transform', {'profile': PROFILE, 'base_value': value, 'commands': commands}, cancel=cancel)
        return JdCandidate(r['value'], r['native_operations'], r['affected_element_ids'])

    def selection(self, value, selection, *, cancel=None):
        return self._call('read-selection', {'profile': PROFILE, 'value': value, 'range': selection}, cancel=cancel)
