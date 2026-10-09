"""背景監督失敗可追查，日誌不得改變停止、原件保留或釋放所有權的行為。"""

import asyncio
import json
import logging

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from caliburn.adapters.logging import SafeJsonFormatter
from caliburn.workflows.consultant_supervisor import ConsultantSupervisor
from caliburn.workflows.memory_supervisor import MemorySupervisor


class Leader:
    def __init__(self):
        self.release_error = None
        self.release_calls = 0

    async def acquire(self):
        pass

    async def check(self):
        pass

    async def close(self):
        self.release_calls += 1
        if self.release_error is not None:
            raise self.release_error


def make_supervisor(kind):
    leader = Leader()

    async def unexpected_runner(_writer):
        pytest.fail("A diagnostic test must not dispatch a product execution")

    if kind == "consultant_turn":
        supervisor = ConsultantSupervisor(
            sessions=async_sessionmaker(),
            run=unexpected_runner,
            process_lock=leader,
            poll_interval_seconds=60,
        )
        return supervisor, leader, "_scan"
    supervisor = MemorySupervisor(
        async_sessionmaker(),
        run=unexpected_runner,
        check_leadership=leader.check,
        poll_interval_seconds=60,
    )
    return supervisor, leader, "scan"


def logged_failures(caplog):
    records = [record for record in caplog.records if record.name.endswith("_supervisor")]
    assert all(record.exc_info is None for record in records)
    assert "private" not in str([record.__dict__ for record in records])
    return [json.loads(SafeJsonFormatter().format(record)) for record in records]


@pytest.mark.parametrize("kind", ["consultant_turn", "memory_batch"])
async def test_monitor_failure_logs_safe_metadata_and_preserves_failure_kind(
    kind, monkeypatch, caplog
):
    supervisor, _leader, scan_method = make_supervisor(kind)
    failure = ConnectionError("private database URL and credentials")
    scans = 0

    async def scan():
        nonlocal scans
        scans += 1
        if scans > 1:
            raise failure

    monkeypatch.setattr(supervisor, scan_method, scan)
    caplog.set_level(logging.ERROR)
    try:
        await supervisor.start()
        supervisor.notify()
        await asyncio.wait_for(asyncio.shield(supervisor._monitor), 1)
        assert supervisor.failure.error_type == type(failure).__name__
        assert scans == 2
        [payload] = logged_failures(caplog)
        assert payload["event"] == "supervisor.monitor_failed"
        assert payload["level"] == "ERROR"
        assert payload["execution_kind"] == kind
        assert payload["operation"] == "scan"
        assert payload["failure_kind"] == "ConnectionError"
        assert "execution_id" not in payload
        assert "job_file_id" not in payload
    finally:
        await supervisor.close()


@pytest.mark.parametrize("scan_fails", [False, True])
async def test_consultant_release_failure_is_logged_without_replacing_or_retrying_failure(
    scan_fails, monkeypatch, caplog
):
    supervisor, leader, scan_method = make_supervisor("consultant_turn")
    scan_error = ConnectionError("private scan details")
    release_error = OSError("private release details")
    leader.release_error = release_error
    observed_scan = asyncio.Event()
    scans = 0

    async def scan():
        nonlocal scans
        scans += 1
        if scans > 1:
            observed_scan.set()
            if scan_fails:
                raise scan_error

    monkeypatch.setattr(supervisor, scan_method, scan)
    caplog.set_level(logging.ERROR)
    await supervisor.start()
    try:
        supervisor.notify()
        await asyncio.wait_for(observed_scan.wait(), 1)
        if scan_fails:
            await asyncio.wait_for(asyncio.shield(supervisor._monitor), 1)
        with pytest.raises(OSError) as stopped:
            await supervisor.close()
        assert stopped.value is release_error
        assert (
            supervisor.failure.error_type
            == type(scan_error if scan_fails else release_error).__name__
        )
        assert leader.release_calls == 1
        payloads = logged_failures(caplog)
        assert [payload["event"] for payload in payloads] == (
            ["supervisor.monitor_failed", "supervisor.release_failed"]
            if scan_fails
            else ["supervisor.release_failed"]
        )
        assert payloads[-1]["level"] == "ERROR"
        assert payloads[-1]["execution_kind"] == "consultant_turn"
        assert payloads[-1]["operation"] == "release_leadership"
        assert payloads[-1]["failure_kind"] == "OSError"
    finally:
        with pytest.raises(OSError):
            await supervisor.close()


@pytest.mark.parametrize("kind", ["consultant_turn", "memory_batch"])
async def test_normal_monitor_cancellation_does_not_log_a_failure(kind, monkeypatch, caplog):
    supervisor, _leader, scan_method = make_supervisor(kind)
    observed_scan = asyncio.Event()

    async def scan():
        observed_scan.set()

    monkeypatch.setattr(supervisor, scan_method, scan)
    caplog.set_level(logging.ERROR)
    await supervisor.start()
    try:
        observed_scan.clear()
        supervisor.notify()
        await asyncio.wait_for(observed_scan.wait(), 1)
    finally:
        await supervisor.close()
    assert supervisor.failure is None
    assert logged_failures(caplog) == []
