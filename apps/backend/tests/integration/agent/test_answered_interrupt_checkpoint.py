"""已回答後故障的冷恢復保留第二題，並重用完成的模型及工具結果。"""

import json
import subprocess
import sys
from pathlib import Path


def test_answered_interrupt_failure_resumes_without_skipping_the_next_question(
    checkpoint_conninfo: str, tmp_path: Path
) -> None:
    for mode in ("writer", "recover", "reader"):
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "tests.integration.agent.answered_interrupt_process",
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

    original = json.loads((tmp_path / "writer.json").read_text())
    assert len(original) == 2
    assert original[0]["input"] == [{"role": "user", "content": "original question"}]
    assert [
        item
        for item in original[1]["input"]
        if item.get("type") == "function_call_output"
    ] == [
        {
            "type": "function_call_output",
            "call_id": "call_alpha",
            "output": "saved alpha",
        }
    ]
    for mode in ("recover", "reader"):
        assert json.loads((tmp_path / f"{mode}.json").read_text()) == []
    assert (tmp_path / "effects.jsonl").read_text().splitlines() == ['"alpha"']
    assert json.loads((tmp_path / "answers.json").read_text()) == [
        "first answer",
        "second answer",
    ]
    attempts = [
        json.loads(line)
        for line in (tmp_path / "attempts.jsonl").read_text().splitlines()
    ]
    assert len(attempts) == 4
    assert all(
        item == {"turn_id": "00000000-0000-0000-0000-000000000259", "model_step": 2}
        for item in attempts
    )
