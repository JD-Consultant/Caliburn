"""Start a process tree a test owns, then reap all of it, never matching by name or port.

`Popen.kill()` and `terminate()` signal only the direct child (Python `subprocess` docs), so a
grandchild survives a killed leader. On POSIX the leader gets its own process group and the group
is signalled with `os.killpg`; on Windows `taskkill /T` resolves the tree from the leader's pid.
A killed grandchild is reaped by init, so a minimal container needs one (`docker run --init`).
Windows resolves the tree through the live leader, so a tree whose leader already exited cannot be
reaped there; POSIX can, because the group outlives its leader.
"""

import os
import signal
import subprocess
import time
from typing import Any

_POSIX = os.name != "nt"


def popen_owned(args: list[str], **options: Any) -> subprocess.Popen[bytes]:
    """The leader of a process group (POSIX), so one signal reaches everything it starts."""
    if _POSIX:
        options.setdefault("process_group", 0)
    return subprocess.Popen(args, **options)


def reap_owned_tree(process: subprocess.Popen[bytes], *, grace_seconds: float = 10.0) -> None:
    """Give the leader `grace_seconds` to finish by itself, then kill the whole tree.

    Always waits for the leader. Safe after a normal exit: a finished leader with no remaining
    group members signals nothing. The wait for the group to empty is best effort and never
    raises, so it cannot hide the failure that led to cleanup.
    """
    try:
        process.wait(timeout=grace_seconds)
    except subprocess.TimeoutExpired:
        pass
    if _POSIX:
        _kill_group(process.pid)
    elif process.poll() is None:
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            check=False,
            capture_output=True,
            timeout=10,
        )
    process.wait(timeout=10)
    if _POSIX:
        _wait_group_empty(process.pid)


def _kill_group(group_id: int) -> None:
    try:
        os.killpg(group_id, signal.SIGKILL)
    except ProcessLookupError:
        pass  # Already empty.


def _wait_group_empty(group_id: int, timeout_seconds: float = 5.0) -> None:
    """Zombies still count as members until init reaps them, hence no failure on timeout."""
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            os.killpg(group_id, 0)
        except ProcessLookupError:
            return
        time.sleep(0.02)
