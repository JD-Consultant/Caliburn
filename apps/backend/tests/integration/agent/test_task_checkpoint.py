"""Task 與工具 Command 在真 PG／冷程序中保留原生恢復語義。"""

import json
import subprocess
import sys
from pathlib import Path


def test_saved_tool_task_is_reused_after_wrapper_failure_in_another_process(
    checkpoint_conninfo: str, tmp_path: Path
) -> None:
    for mode in ("writer", "reader"):
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "tests.integration.agent.task_process",
                mode,
                checkpoint_conninfo,
                str(tmp_path),
            ],
            capture_output=True,
            text=True,
            timeout=45,
            check=False,
        )
        assert completed.returncode == 0, completed.stderr
    effects = [
        json.loads(line)
        for line in (tmp_path / "effects.jsonl").read_text().splitlines()
    ]
    assert effects == ["alpha"]
    original = json.loads((tmp_path / "writer.json").read_text())
    resumed = json.loads((tmp_path / "reader.json").read_text())
    assert len(original) == len(resumed) == 1
    assert resumed[0]["input"][-1] == {
        "type": "function_call_output",
        "call_id": "call_alpha",
        "output": "read alpha; approved",
    }
