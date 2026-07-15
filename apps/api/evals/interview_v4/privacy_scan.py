"""Privacy pre-screen for deidentified interview case candidates.

Findings contain only a category and structural location.  Matched source text
is never returned or printed.  This is a conservative pre-screen, not a claim
that ordinary data has passed manual privacy review. Owner-confirmed synthetic
fixtures retain findings for scanner regression but do not require that review.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from evals.interview_v4.exporter import find_direct_identifiers


_HEURISTICS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("TAIWAN_ID", re.compile(r"(?<![A-Za-z0-9])[A-Z][12]\d{8}(?!\d)")),
    ("IPV4", re.compile(r"(?<!\d)(?:\d{1,3}\.){3}\d{1,3}(?!\d)")),
    ("SECRET_ASSIGNMENT", re.compile(
        r"(?i)(?:api[_-]?key|access[_-]?token|password|passwd|secret)\s*[:=]\s*\S+"
    )),
    ("PERSON_CUE", re.compile(
        r"(?:我叫|我的名字(?:叫|是)|姓名(?:是|為)?|聯絡人(?:是|為)?)"
        r"[：:\s]*[\u4e00-\u9fff]{2,4}"
    )),
    ("ORGANIZATION_CUE", re.compile(
        r"[\u4e00-\u9fffA-Za-z0-9]{2,30}"
        r"(?:股份有限公司|有限公司|公司|銀行|醫院|學校|大學|基金會|協會)"
    )),
    ("CUSTOMER_CUE", re.compile(
        r"(?:客戶|供應商|合作夥伴)(?:叫|名稱(?:是|為)?|是|為)"
        r"[：:\s]*[\u4e00-\u9fffA-Za-z0-9_-]{2,30}"
    )),
    ("ADDRESS_CUE", re.compile(
        r"[\u4e00-\u9fff]{2,12}(?:縣|市)[\u4e00-\u9fff0-9-]{0,30}"
        r"(?:路|街|大道)[\u4e00-\u9fff0-9-]{0,16}號"
    )),
    ("LONG_NUMBER", re.compile(r"(?<!\d)\d{8,}(?!\d)")),
)


def _scan_value(value: Any, *, file_name: str) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []

    def walk(node: Any, path: str) -> None:
        if isinstance(node, str):
            for direct in find_direct_identifiers(node):
                findings.append({"kind": direct["kind"], "path": f"{file_name}:{path}"})
            for kind, pattern in _HEURISTICS:
                if pattern.search(node):
                    findings.append({"kind": kind, "path": f"{file_name}:{path}"})
        elif isinstance(node, dict):
            for index, item in enumerate(node.values()):
                walk(item, f"{path}.value[{index}]")
        elif isinstance(node, list):
            for index, item in enumerate(node):
                walk(item, f"{path}[{index}]")

    walk(value, "$")
    return findings


def scan_case(case_dir: str | Path) -> dict[str, Any]:
    root = Path(case_dir).resolve()
    if not root.is_dir():
        raise FileNotFoundError(root)
    findings: list[dict[str, str]] = []
    scanned_files: list[str] = []
    owner_confirmed_synthetic = False
    for path in sorted(root.iterdir()):
        if not path.is_file() or path.suffix.lower() not in {".json", ".jsonl", ".md"}:
            continue
        scanned_files.append(path.name)
        if path.suffix.lower() == ".json":
            values = [json.loads(path.read_text(encoding="utf-8"))]
            if path.name == "case.json":
                privacy = values[0].get("privacy") if isinstance(values[0], dict) else None
                owner_confirmed_synthetic = (
                    isinstance(privacy, dict) and privacy.get("status") == "synthetic"
                )
        elif path.suffix.lower() == ".jsonl":
            values = [
                json.loads(line)
                for line in path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
        else:
            values = [path.read_text(encoding="utf-8")]
        for index, value in enumerate(values):
            suffix = f"#{index + 1}" if len(values) > 1 else ""
            findings.extend(_scan_value(value, file_name=f"{path.name}{suffix}"))
    counts = Counter(item["kind"] for item in findings)
    return {
        "schema_version": "interview_eval_privacy_prescreen.v0.1",
        # Findings remain visible for scanner regression, but owner-confirmed
        # synthetic fixtures do not need a human privacy adjudication.
        "manual_review_still_required": not owner_confirmed_synthetic,
        "scanned_files": scanned_files,
        "finding_counts": dict(sorted(counts.items())),
        "findings": findings,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("case_dir")
    args = parser.parse_args()
    print(json.dumps(scan_case(args.case_dir), ensure_ascii=False, indent=2))
