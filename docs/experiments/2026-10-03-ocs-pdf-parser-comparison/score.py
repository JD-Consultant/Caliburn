"""Evaluate fixed, visually checked source anchors against retained raw extraction."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import zipfile


def compact(value: object) -> str:
    return re.sub(r"\s+", "", str(value or ""))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("raw", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rubric = json.loads(Path(__file__).with_name("rubric.json").read_text(encoding="utf-8"))
    results = []
    engines = ["pdfplumber", "camelot", "camelot-lattice", "docling"]
    if args.raw.is_file():
        with zipfile.ZipFile(args.raw) as archive:
            payloads = {name: json.loads(archive.read(name)) for name in archive.namelist()
                        if name.endswith(".json")}
    else:
        payloads = {path.name: json.loads(path.read_text(encoding="utf-8"))
                    for path in args.raw.glob("*.json")}
    for engine in engines:
        documents = {Path(name).stem.split("-")[-1]: value for name, value in payloads.items()
                     if re.fullmatch(re.escape(engine) + r"-\d{2}\.json", name)}
        if not documents:
            continue

        def page_for(check: dict) -> dict:
            return next((page for page in documents.get(check["id"], {}).get("pages", [])
                         if page["number"] == check["page"]), {"text": "", "tables": []})

        for check in rubric["row_checks"]:
            matches = []
            for table in page_for(check)["tables"]:
                for row in table["grid"]:
                    if any(compact(value).startswith(check["task"]) for value in row):
                        matches.append(row)

            def ordered(row: list) -> bool:
                needles = [check["task"], check["indicator"], check["level"],
                           check["knowledge"], check["skill"]]
                previous = -1
                for index, needle in enumerate(needles):
                    candidates = [column for column, value in enumerate(row)
                                  if column > previous and
                                  (compact(value) == needle if index == 2 else needle in compact(value))]
                    if not candidates:
                        return False
                    previous = candidates[0]
                return True

            passed = any(ordered(row) for row in matches)
            results.append({"engine": engine, "kind": "row", "check": check,
                            "passed": passed, "matching_rows": matches})
        for check in rubric["text_checks"]:
            passed = compact(check["text"]) in compact(page_for(check)["text"])
            results.append({"engine": engine, "kind": "text", "check": check, "passed": passed,
                            "scope": "tables_only" if engine.startswith("camelot") else "page_text_and_tables"})
        for check in rubric["continuation_checks"]:
            matches = []
            for table in page_for(check)["tables"]:
                for row in table["grid"]:
                    matches.extend(value for value in row if check["code"] in compact(value))
            passed = any(compact(check["tail"]) in compact(value) for value in matches)
            results.append({"engine": engine, "kind": "continuation_cell", "check": check,
                            "passed": passed, "matching_cells": matches})
    args.output.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    for engine in engines:
        for kind in ["row", "text", "continuation_cell"]:
            group = [record for record in results if record["engine"] == engine and record["kind"] == kind]
            if group:
                print(engine, kind, sum(record["passed"] for record in group), "/", len(group))
                for record in group:
                    if not record["passed"]:
                        print("FAIL", record["check"], record.get("matching_rows", record.get("matching_cells", "")))


if __name__ == "__main__":
    main()
