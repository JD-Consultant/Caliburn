"""Verify formal source equality and stage two opaque bundles in one C directory."""

import json
import re
import shutil
import sys
from hashlib import sha256
from pathlib import Path

ARTIFACT_ROOT = Path(
    "C:/Users/chenb/.codex/visualizations/2026/10/06/"
    "01a11182-e198-7652-87d2-d90d10463ed1/caliburn-intplan-comparison"
)
FIELDS = ["source_id", "interview_sequence", "speaker", "interview_text"]


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def stage(case_directory):
    mapping = read(case_directory.parent / "blind-map.json")
    matches = [key for key, value in mapping.items() if Path(value).resolve() == case_directory]
    if len(matches) != 1 or not re.fullmatch(r"[0-9a-f]{32}", matches[0]):
        raise ValueError("Expected exactly one opaque mapping for the completed case")
    opaque = matches[0]
    result = read(case_directory / "result.json")
    if not result["closure_submitted"] or result["turns"][-1]["status"] != "completed":
        raise ValueError("Only actually completed closure cases enter blind review")
    source = case_directory.parent.parent / "blind-input" / (opaque + ".json")
    bundle = read(source)
    if set(bundle) != {"case_id", "formal_jd", "employee_originals", "fixed_source_contents"}:
        raise ValueError("Bundle contains fields outside the frozen quality-only envelope")
    if bundle["case_id"] != opaque:
        raise ValueError("Opaque bundle identity mismatch")
    originals = [
        {key: item[key] for key in FIELDS}
        for item in read(case_directory / "formal-interviews.json")["messages"]
        if item["speaker"] == "employee"
    ]
    if (
        bundle["formal_jd"] != read(case_directory / "formal-jd.json")
        or bundle["fixed_source_contents"] != read(case_directory / "fixed-source-contents.json")
        or bundle["employee_originals"] != originals
    ):
        raise ValueError("Bundle differs from actual formal HTTP JD/employee/fixed sources")
    destination = ARTIFACT_ROOT / "blind-input" / source.name
    original_hash = sha256(source.read_bytes()).hexdigest()
    if destination.exists():
        if sha256(destination.read_bytes()).hexdigest() != original_hash:
            raise ValueError("Existing opaque C copy differs from the original bytes")
    else:
        shutil.copyfile(source, destination)
    if sha256(destination.read_bytes()).hexdigest() != original_hash:
        raise ValueError("Opaque C copy verification failed")
    return {"opaque_id": opaque, "path": str(destination), "sha256": original_hash}


def main():
    first, second, output = (
        Path(sys.argv[1]).resolve(),
        Path(sys.argv[2]).resolve(),
        Path(sys.argv[3]),
    )
    if output.exists():
        raise RuntimeError("Opaque pair delivery already exists")
    result = sorted([stage(first), stage(second)], key=lambda item: item["opaque_id"])
    if result[0]["opaque_id"] == result[1]["opaque_id"]:
        raise ValueError("A pair requires two distinct completed cases")
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
