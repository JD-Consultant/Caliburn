from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent
VALIDATOR = ROOT / "validate_cases.py"
EXPECTED_CASES = (
    ("CR-01-tools-not-tasks", "CR-01"),
    ("CR-02-one-story-many-work", "CR-02"),
    ("CR-03-many-stories-one-task", "CR-03"),
    ("CR-04-responsibility-boundary", "CR-04"),
    ("CR-05-correction-and-negation", "CR-05"),
    ("CR-06-insufficient-evidence", "CR-06"),
)


def _case(case_id: str, family_id: str) -> dict[str, object]:
    return {
        "case_id": case_id,
        "case_family_id": family_id,
        "source_type": "constructed_edge",
        "title": "測試案例",
        "primary_risk": "測試風險",
        "applicable_critical_checks": [
            "C1_TOOL_BOUNDARY",
            "C6_SOURCE_FIDELITY",
        ],
        "transcript": [
            {
                "source_id": "turn-001",
                "role": "consultant",
                "text": "請描述你的工作。",
            },
            {
                "source_id": "turn-002",
                "role": "employee",
                "text": "我每天整理資料，並寄給主管。",
            },
        ],
        "claim_table": [
            {
                "claim_id": "claim-001",
                "speaker": "employee",
                "literal_text": "我每天整理資料",
                "source_turn_ids": ["turn-002"],
                "sequence_index": 1,
            },
            {
                "claim_id": "claim-002",
                "speaker": "employee",
                "literal_text": "寄給主管",
                "source_turn_ids": ["turn-002"],
                "sequence_index": 2,
            },
        ],
        "relevant_span_ids": ["turn-002"],
        "adjudication": {
            "must_retain_tasks": ["整理資料並交付主管"],
            "must_not_create_tasks_from": [],
            "allowed_task_variants": ["整理並交付資料"],
            "required_uncertainties": [],
            "notes": "逐字切分保留兩項獨立陳述；相關片段包含唯一員工回答。",
        },
    }


def _write_suite(directory: Path) -> list[Path]:
    paths: list[Path] = []
    for case_id, family_id in EXPECTED_CASES:
        path = directory / f"{case_id}.json"
        path.write_text(
            json.dumps(_case(case_id, family_id), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        paths.append(path)
    return paths


def _run_validator(directory: Path) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PYTHONUTF8"] = "1"
    return subprocess.run(
        [sys.executable, str(VALIDATOR), str(directory)],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=environment,
    )


class ValidateCasesTests(unittest.TestCase):
    def setUp(self) -> None:
        test_root = ROOT / ".test-work"
        self.directory = test_root / self._testMethodName
        self.assertTrue(self.directory.resolve().is_relative_to(ROOT.resolve()))
        if self.directory.exists():
            shutil.rmtree(self.directory)
        self.directory.mkdir(parents=True)

    def tearDown(self) -> None:
        test_root = ROOT / ".test-work"
        if self.directory.exists():
            shutil.rmtree(self.directory)
        if test_root.exists() and not any(test_root.iterdir()):
            test_root.rmdir()

    def test_accepts_complete_literal_six_case_suite(self) -> None:
        _write_suite(self.directory)

        result = _run_validator(self.directory)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("validated 6 cases", result.stdout)

    def test_rejects_claim_that_is_not_a_literal_turn_substring(self) -> None:
        paths = _write_suite(self.directory)
        record = json.loads(paths[0].read_text(encoding="utf-8"))
        record["claim_table"][0]["literal_text"] = "模型改寫過的資料整理工作"
        paths[0].write_text(
            json.dumps(record, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        result = _run_validator(self.directory)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("逐字子字串", result.stderr)

    def test_rejects_answer_label_fields_in_claim_table(self) -> None:
        paths = _write_suite(self.directory)
        record = json.loads(paths[0].read_text(encoding="utf-8"))
        record["claim_table"][0]["responsibility"] = "self"
        paths[0].write_text(
            json.dumps(record, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        result = _run_validator(self.directory)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("claim 欄位", result.stderr)

    def test_rejects_non_contiguous_claim_sequence(self) -> None:
        paths = _write_suite(self.directory)
        record = json.loads(paths[0].read_text(encoding="utf-8"))
        record["claim_table"][1]["sequence_index"] = 3
        paths[0].write_text(
            json.dumps(record, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        result = _run_validator(self.directory)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("sequence_index", result.stderr)

    def test_rejects_template_placeholder_text(self) -> None:
        paths = _write_suite(self.directory)
        record = json.loads(paths[0].read_text(encoding="utf-8"))
        record["transcript"][1]["text"] = "案例正式內容會在執行前寫入。"
        paths[0].write_text(
            json.dumps(record, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        result = _run_validator(self.directory)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("模板占位文字", result.stderr)


if __name__ == "__main__":
    unittest.main()
