"""核對實際 JSONL 輸出與並行作用域，不只檢查 LogRecord。"""

import asyncio
import importlib
import io
import json
import logging
import os
import subprocess
import sys
import threading
import time
from datetime import datetime

import pytest


@pytest.fixture
def logging_module():
    return importlib.import_module("caliburn.adapters.logging")


@pytest.fixture
def output(logging_module, monkeypatch):
    stream = io.StringIO()
    monkeypatch.setattr("sys.stdout", stream)
    runtime = logging_module.configure_logging("INFO")
    yield stream, runtime
    runtime.close()


def rows(output):
    stream, runtime = output
    assert runtime.close()
    return [json.loads(line) for line in stream.getvalue().splitlines()]


def test_actual_handler_keeps_failure_identity_without_exception_or_unapproved_text(output):
    log = logging.getLogger("caliburn.workflows.execution_failures")
    try:
        raise ValueError("private prompt https://secret.invalid/?token=secret")
    except ValueError:
        log.warning(
            "Execution stopped; reconciling its terminal outcome",
            extra={
                "event": "execution.failure",
                "execution_id": "execution-1",
                "failure_kind": "ValueError",
                "prompt": "private prompt",
                "authorization": "secret",
            },
            exc_info=True,
        )

    [value] = rows(output)
    assert value["event"] == "execution.failure"
    assert value["module"] == "caliburn.workflows.execution_failures"
    assert value["execution_id"] == "execution-1"
    assert value["failure_kind"] == "ValueError"
    assert datetime.fromisoformat(value["timestamp"]).utcoffset().total_seconds() == 0
    assert "private" not in json.dumps(value)
    assert "secret" not in json.dumps(value)


async def test_parallel_contexts_and_nested_attempts_are_released(logging_module, output):
    log = logging.getLogger("caliburn.test")

    async def work(identity):
        with logging_module.bind_log_context(execution_id=identity, request_id="logical"):
            await asyncio.sleep(0)
            for attempt in ("one", "two"):
                with logging_module.bind_log_context(attempt_id=attempt):
                    log.info("provider.attempt")
            log.info("execution.finished")

    await asyncio.gather(work("first"), work("second"))
    log.info("app.idle")
    values = rows(output)
    for identity in ("first", "second"):
        attempts = [row for row in values if row.get("execution_id") == identity]
        assert [row.get("attempt_id") for row in attempts] == ["one", "two", None]
        assert all(row["request_id"] == "logical" for row in attempts)
    assert "execution_id" not in values[-1]
    assert "request_id" not in values[-1]


async def test_cancellation_releases_log_context(logging_module, output):
    log = logging.getLogger("caliburn.test")
    with pytest.raises(asyncio.CancelledError):
        with logging_module.bind_log_context(execution_id="cancelled"):
            log.info("execution.cancelled")
            raise asyncio.CancelledError
    log.info("app.available")
    cancelled, outside = rows(output)
    assert cancelled["execution_id"] == "cancelled"
    assert "execution_id" not in outside


def test_framework_access_and_sdk_errors_never_render_raw_urls_or_bodies(output):
    logging.getLogger("uvicorn.access").info(
        '%s - "%s %s HTTP/%s" %d', "client", "GET", "/?token=private", "1.1", 400
    )
    logging.getLogger("openai._base_client").error("Body: private prompt and sk-private")
    values = rows(output)
    assert len(values) == 2
    assert values[0]["http_status"] == 400
    assert "private" not in json.dumps(values)


def test_untrusted_metadata_is_bounded_and_cannot_forge_a_line(output):
    logging.getLogger("caliburn.test").warning(
        "execution.failure",
        extra={"failure_kind": "a\n\x1b\x00" + "x" * 1000, "duration_ms": float("nan")},
    )
    [value] = rows(output)
    assert len(value["failure_kind"]) <= 256
    assert value["truncated_fields"] == ["failure_kind"]
    assert "duration_ms" not in value


def test_broken_sink_does_not_raise_or_print_original_record(logging_module, monkeypatch, capsys):
    class BrokenStream(io.StringIO):
        def write(self, value):
            raise OSError("private connection credentials")

    monkeypatch.setattr("sys.stdout", BrokenStream())
    runtime = logging_module.configure_logging()
    logging.getLogger("caliburn.test").error("execution.failure")
    assert runtime.close()
    assert runtime.output_failures == 1
    assert "private" not in capsys.readouterr().err


def test_slow_sink_has_bounded_queue_and_bounded_shutdown(logging_module, monkeypatch):
    entered, release = threading.Event(), threading.Event()

    class SlowStream(io.StringIO):
        def write(self, value):
            entered.set()
            release.wait(2)
            return super().write(value)

    monkeypatch.setattr("sys.stdout", SlowStream())
    monkeypatch.setattr(logging_module, "QUEUE_CAPACITY", 2)
    runtime = logging_module.configure_logging()
    log = logging.getLogger("caliburn.test")
    try:
        log.info("execution.started")
        assert entered.wait(1)
        for _ in range(10):
            log.info("execution.progress")
        assert runtime.dropped_records == 8
        started = time.monotonic()
        assert not runtime.close(timeout=0.01)
        assert time.monotonic() - started < 0.5
    finally:
        release.set()
        assert runtime.close()


def test_reconfiguration_closes_the_previous_listener_without_duplicate_output(
    logging_module, monkeypatch
):
    stream = io.StringIO()
    monkeypatch.setattr("sys.stdout", stream)
    first = logging_module.configure_logging()
    logging.getLogger("caliburn.test").info("execution.started")
    second = logging_module.configure_logging()
    logging.getLogger("caliburn.test").info("execution.finished")
    assert first.closed
    assert first.close(timeout=0)
    assert second.close()
    assert len(stream.getvalue().splitlines()) == 2


def test_recovered_output_reports_prior_sink_failures(logging_module, monkeypatch):
    class RecoveringStream(io.StringIO):
        broken = True

        def write(self, value):
            if self.broken:
                raise OSError("secret output failure")
            return super().write(value)

    stream = RecoveringStream()
    monkeypatch.setattr("sys.stdout", stream)
    runtime = logging_module.configure_logging()
    logging.getLogger("caliburn.test").warning("execution.first")
    runtime.handler.queue.join()
    stream.broken = False
    logging.getLogger("caliburn.test").warning("execution.second")
    assert runtime.close()
    [value] = [json.loads(line) for line in stream.getvalue().splitlines()]
    assert value["logging_output_failures"] == 1


def test_queue_recovery_reports_dropped_records(logging_module, monkeypatch):
    entered, release = threading.Event(), threading.Event()

    class SlowStream(io.StringIO):
        def write(self, value):
            entered.set()
            release.wait(2)
            return super().write(value)

    stream = SlowStream()
    monkeypatch.setattr("sys.stdout", stream)
    monkeypatch.setattr(logging_module, "QUEUE_CAPACITY", 2)
    runtime = logging_module.configure_logging()
    log = logging.getLogger("caliburn.test")
    try:
        log.info("execution.started")
        assert entered.wait(1)
        for _ in range(10):
            log.info("execution.progress")
        release.set()
        runtime.handler.queue.join()
        log.info("execution.finished")
        assert runtime.close()
        last = json.loads(stream.getvalue().splitlines()[-1])
        assert last["logging_dropped_records"] == 8
    finally:
        release.set()
        runtime.close()


def test_standard_logging_shutdown_cannot_wait_for_slow_stdout(logging_module, monkeypatch):
    entered, release, stopped = threading.Event(), threading.Event(), threading.Event()

    class SlowStream(io.StringIO):
        def write(self, value):
            entered.set()
            release.wait(2)
            return super().write(value)

    monkeypatch.setattr("sys.stdout", SlowStream())
    runtime = logging_module.configure_logging()
    logging.getLogger("caliburn.test").warning("execution.pending")
    assert entered.wait(1)

    def shutdown():
        logging.shutdown()
        stopped.set()

    thread = threading.Thread(target=shutdown, daemon=True)
    thread.start()
    try:
        assert stopped.wait(0.2)
    finally:
        release.set()
        thread.join(1)
        assert runtime.close()


def test_real_process_exits_when_stdout_pipe_is_full_without_leaking_sensitive_content():
    program = """
import json
import logging
import sys
from caliburn.adapters.logging import configure_logging

runtime = configure_logging()
log = logging.getLogger('caliburn.test.subprocess')
for _ in range(4000):
    try:
        raise ValueError('private exception text')
    except ValueError:
        log.warning('operation.finished', extra={
            'operation': 'x' * 256,
            'prompt': 'private prompt text',
            'authorization': 'private credentials',
        }, exc_info=True)
completed = runtime.close(timeout=0.05)
sys.stderr.write(json.dumps({'completed': completed, 'dropped': runtime.dropped_records}) + '\\n')
sys.stderr.flush()
"""
    process = subprocess.Popen(
        [sys.executable, "-c", program], stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    try:
        # 先等真正退出，刻意不讀 stdout；communicate 會排空 pipe 而掩蓋故障。
        returncode = process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        process.kill()
        stdout, stderr = process.communicate(timeout=3)
        pytest.fail(f"Filled stdout prevented interpreter exit: {stderr[:300]!r}")
    else:
        stdout, stderr = process.communicate(timeout=3)
        assert returncode == 0, stderr
    assert b"private" not in stdout + stderr
    assert b"_enter_buffered_busy" not in stderr
    result = json.loads(stderr)
    assert result["completed"] is False
    assert result["dropped"] > 0


def test_raw_output_closes_only_its_own_descriptor_after_draining(logging_module, monkeypatch):
    reader, writer = os.pipe()
    stream = os.fdopen(writer, "w", encoding="utf-8")
    monkeypatch.setattr("sys.stdout", stream)
    runtime = logging_module.configure_logging()
    write = os.write

    def write_partial(descriptor, data):
        return write(descriptor, data[:7])

    monkeypatch.setattr(logging_module.os, "write", write_partial)
    try:
        logging.getLogger("caliburn.test").info("operation.finished")
        assert runtime.close()
        assert not stream.closed
        stream.close()
        os.set_blocking(reader, False)
        result = json.loads(os.read(reader, 4096))
        assert result["event"] == "operation.finished"
        # 若自有 duplicate 尚未關閉，空 pipe 會報 BlockingIOError，而非 EOF。
        assert os.read(reader, 1) == b""
    finally:
        runtime.close()
        stream.close()
        os.close(reader)


def test_unavailable_descriptor_does_not_fall_back_to_a_shared_buffer(logging_module, monkeypatch):
    class UnavailableOutput(io.TextIOBase):
        def write(self, value):
            pytest.fail("The listener must not acquire an unknown output's buffer lock")

    monkeypatch.setattr("sys.stdout", UnavailableOutput())
    runtime = logging_module.configure_logging()
    logging.getLogger("caliburn.test").error("operation.failed")
    assert runtime.close()
    assert runtime.output_failures == 1


def test_closed_pipe_is_counted_without_delaying_process_exit_or_printing_errors():
    program = """
import json
import logging
import sys
from caliburn.adapters.logging import configure_logging

sys.stdin.read(1)
runtime = configure_logging()
log = logging.getLogger('caliburn.test.subprocess')
for _ in range(10):
    log.error('operation.failed', extra={'prompt': 'private prompt', 'url': 'private URL'})
completed = runtime.close(timeout=1)
sys.stderr.write(json.dumps({'completed': completed, 'failed': runtime.output_failures}))
"""
    process = subprocess.Popen(
        [sys.executable, "-c", program],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        process.stdout.close()
        process.stdin.write(b"1")
        process.stdin.close()
        assert process.wait(timeout=3) == 0
        stderr = process.stderr.read()
        assert b"private" not in stderr
        assert json.loads(stderr) == {"completed": True, "failed": 10}
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=3)
        process.stdout.close()
        process.stdin.close()
        process.stderr.close()
