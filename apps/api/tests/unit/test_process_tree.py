"""A test's process tree is reaped as a whole; killing only its leader leaves a child running."""

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from tests.fixtures.process_tree import popen_owned, reap_owned_tree

LEADER = """
import subprocess, sys
from pathlib import Path
heartbeat = Path(sys.argv[1])
subprocess.Popen([sys.executable, "-c", '''
import os, sys, time
from pathlib import Path
heartbeat = Path(sys.argv[1])
deadline = time.monotonic() + 60  # Never outlives a failed test by more than a minute.
while time.monotonic() < deadline:
    heartbeat.write_text(f"{os.getpid()} {time.monotonic_ns()}")
    time.sleep(0.05)
''', str(heartbeat)])
time.sleep(60)
"""


def _read_heartbeat(heartbeat: Path) -> tuple[int, int]:
    """The grandchild's pid and tick; a read can catch the file mid-rewrite, so retry briefly."""
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        try:
            pid, tick = heartbeat.read_text().split()
            return int(pid), int(tick)
        except OSError, ValueError:
            time.sleep(0.01)
    raise AssertionError("The grandchild heartbeat is unreadable")


def _beating(heartbeat: Path) -> bool:
    """A live grandchild rewrites its heartbeat every 50 ms; a dead one leaves it unchanged."""
    first = _read_heartbeat(heartbeat)
    time.sleep(0.4)
    return _read_heartbeat(heartbeat) != first


def _start(heartbeat: Path) -> subprocess.Popen[bytes]:
    leader = popen_owned([sys.executable, "-c", "import time\n" + LEADER, str(heartbeat)])
    deadline = time.monotonic() + 10
    while not heartbeat.exists() and time.monotonic() < deadline:
        time.sleep(0.02)
    if not _beating(heartbeat):
        reap_owned_tree(leader, grace_seconds=0)
        pytest.fail("The grandchild never started beating")
    return leader


def test_reaping_the_tree_stops_the_grandchild(tmp_path: Path) -> None:
    heartbeat = tmp_path / "heartbeat"
    leader = _start(heartbeat)
    reap_owned_tree(leader, grace_seconds=0.1)
    assert leader.poll() is not None
    assert not _beating(heartbeat)


def test_reaping_a_finished_tree_is_a_quiet_no_op(tmp_path: Path) -> None:
    leader = popen_owned([sys.executable, "-c", "pass"])
    leader.wait(timeout=10)
    reap_owned_tree(leader, grace_seconds=0.1)
    assert leader.returncode == 0


def test_killing_only_the_leader_leaves_the_grandchild_running(tmp_path: Path) -> None:
    """The failure the old cleanup produced: it proves the heartbeat probe can see a leak."""
    heartbeat = tmp_path / "heartbeat"
    leader = _start(heartbeat)
    grandchild_pid, _ = _read_heartbeat(heartbeat)
    try:
        leader.kill()
        leader.wait(timeout=10)
        leaked = _beating(heartbeat)
    finally:
        # The leader is gone, so the tree is no longer addressable through it; end the one
        # grandchild whose pid it reported itself.
        _stop_grandchild(grandchild_pid)
    assert leaked, "Killing the leader alone is expected to leak its child"
    assert not _beating(heartbeat)


def _stop_grandchild(pid: int) -> None:
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/F"], check=False, capture_output=True, timeout=10
        )
        return
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX process groups")
def test_the_leader_owns_a_distinct_process_group() -> None:
    leader = popen_owned([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        assert os.getpgid(leader.pid) == leader.pid != os.getpgid(0)
    finally:
        reap_owned_tree(leader, grace_seconds=0.1)
