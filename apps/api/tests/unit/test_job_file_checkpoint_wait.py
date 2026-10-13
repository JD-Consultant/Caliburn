"""Cancellation must not starve the loop or release a still-running save fence."""

import json
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize("mode", ["scope", "raw", "repeated"])
@pytest.mark.parametrize("outcome", ["success", "failure"])
def test_cancel_waits_for_physical_save_without_adopting_its_late_result(mode, outcome):
    result = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).parents[1] / "fixtures/checkpoint_scope_worker.py"),
            mode,
            outcome,
        ],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout) == {"saved": True, "adopted": False, "released": True}
