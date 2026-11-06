"""公開 Agent 入口的逐工具保存與真正跨程序冷恢復。"""

import json
import subprocess
import sys
from pathlib import Path


def test_cold_resume_keeps_sdk_items_and_does_not_repeat_saved_tool(
    checkpoint_conninfo: str, tmp_path: Path
) -> None:
    for mode in ("control", "writer", "reader"):
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "tests.integration.agent.checkpoint_process",
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
    assert effects == ["alpha", "beta", "beta", "gamma"]
    original = json.loads((tmp_path / "writer.json").read_text())
    resumed = json.loads((tmp_path / "reader.json").read_text())
    control = json.loads((tmp_path / "control.json").read_text())
    assert resumed[0] == control[1]
    assert len(original) == len(resumed) == 1
    assert original[0]["input"] == [{"role": "user", "content": "Synthetic input"}]
    items = resumed[0]["input"]
    assert [
        item["call_id"] for item in items if item.get("type") == "function_call_output"
    ] == ["call_alpha", "call_beta", "call_gamma"]
    assert items[1]["encrypted_content"] == "synthetic-opaque-content"
    assert items[2]["future_call_field"] == {"retained": True}
    assert "parsed_arguments" not in items[2]
    assert "parsed" not in items[5]["content"][0]
