from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent
ASSEMBLER = ROOT / "assemble_context.py"
CASE = ROOT / "cases" / "CR-01-tools-not-tasks.json"


def _assemble(arm: str) -> dict[str, object]:
    environment = os.environ.copy()
    environment["PYTHONUTF8"] = "1"
    result = subprocess.run(
        [sys.executable, str(ASSEMBLER), str(CASE), arm],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=environment,
    )
    if result.returncode != 0:
        raise AssertionError(result.stderr)
    return json.loads(result.stdout)


class AssembleContextTests(unittest.TestCase):
    def test_hybrid_differs_from_raw_plus_spans_only_by_claim_table(self) -> None:
        raw_plus_spans = _assemble("raw_plus_spans")["context_payload"]
        hybrid = _assemble("hybrid")["context_payload"]

        self.assertEqual(raw_plus_spans["transcript"], hybrid["transcript"])
        self.assertEqual(raw_plus_spans["relevant_spans"], hybrid["relevant_spans"])
        self.assertEqual(set(hybrid), set(raw_plus_spans) | {"claim_table"})

    def test_structured_only_keeps_consultant_turns_without_employee_full_text(self) -> None:
        case = json.loads(CASE.read_text(encoding="utf-8"))
        assembled = _assemble("structured_only")
        stream = assembled["context_payload"]["stream"]
        serialized = json.dumps(stream, ensure_ascii=False)

        consultant_texts = [
            turn["text"] for turn in case["transcript"] if turn["role"] == "consultant"
        ]
        employee_texts = [
            turn["text"] for turn in case["transcript"] if turn["role"] == "employee"
        ]
        self.assertTrue(all(text in serialized for text in consultant_texts))
        self.assertTrue(all(text not in serialized for text in employee_texts))
        self.assertTrue(all(claim["literal_text"] in serialized for claim in case["claim_table"]))

    def test_subject_request_excludes_case_metadata_and_adjudication(self) -> None:
        case = json.loads(CASE.read_text(encoding="utf-8"))
        assembled = _assemble("hybrid")
        subject_request = assembled["subject_request"]

        self.assertNotIn(case["case_id"], subject_request)
        self.assertNotIn(case["primary_risk"], subject_request)
        self.assertNotIn("adjudication", subject_request)
        self.assertNotIn("hybrid", subject_request)
        self.assertEqual(assembled["visible_input_char_count"], len(subject_request))
        self.assertGreater(assembled["span_duplicated_char_count"], 0)


if __name__ == "__main__":
    unittest.main()
