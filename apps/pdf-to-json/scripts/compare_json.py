"""Compare retained OCS JSON with one conversion run; never modify source data."""

import argparse
from collections import Counter
from pathlib import Path

from jd_pdf_to_json.conversion import write_report
from jd_pdf_to_json.core.models import OCSDocument


def codes(document: dict, field: str) -> set[str]:
    values = set()
    for unit in document["ocs_content"]["ocu_units"]:
        for task in unit["tasks"]:
            if field == "tasks":
                values.update(item["code"] for item in task["task_codes"] if item["code"])
            else:
                for block in task["competency_blocks"]:
                    values.update(item["code"] for item in block[field] if item["code"])
    return values


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--old-dir", type=Path, required=True)
    parser.add_argument("--new-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    files = []
    section_counts = Counter()
    for path in sorted(args.new_dir.glob("*.json")):
        previous = args.old_dir / path.name
        entry = {"source": path.name, "changed_sections": []}
        if not previous.exists():
            entry["status"] = "new"
        else:
            old = OCSDocument.model_validate_json(previous.read_text("utf-8")).model_dump()
            new = OCSDocument.model_validate_json(path.read_text("utf-8")).model_dump()
            entry["changed_sections"] = [section for section in old if old[section] != new[section]]
            section_counts.update(entry["changed_sections"])
            entry["status"] = "changed" if entry["changed_sections"] else "unchanged"
            entry["code_changes"] = {}
            for field in ("tasks", "indicators", "outputs", "knowledge", "skills"):
                before, after = codes(old, field), codes(new, field)
                if before != after:
                    entry["code_changes"][field] = {
                        "removed": sorted(before - after),
                        "added": sorted(after - before),
                    }
        files.append(entry)
    write_report(
        {
            "summary": dict(Counter(entry["status"] for entry in files)),
            "changed_sections": dict(section_counts),
            "files": files,
        },
        args.report,
    )
    print(f"Compared {len(files)} converted documents: {args.report}")


if __name__ == "__main__":
    main()
