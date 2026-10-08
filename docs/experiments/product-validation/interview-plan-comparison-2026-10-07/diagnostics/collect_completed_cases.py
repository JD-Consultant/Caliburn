"""Save pure operational evidence for mechanically complete cases; no quality scoring."""

import json
from hashlib import sha256
from pathlib import Path

from compaction_metadata import collect as collect_compaction
from completed_metadata import collect as collect_operations
from execution_status_metadata import collect as collect_status
from note_mechanism import extract

HERE = Path(__file__).resolve().parent.parent
ARTIFACT_ROOT = Path(
    "C:/Users/chenb/.codex/visualizations/2026/10/06/"
    "01a11182-e198-7652-87d2-d90d10463ed1/caliburn-intplan-comparison"
)
ORDER = [
    "warehouse-r1-P2",
    "course_admin-r1-P1",
    "course_admin-r1-P2",
    "warehouse-r2-P2",
    "warehouse-r2-P1",
    "course_admin-r2-P2",
    "course_admin-r2-P1",
]


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def save_once(path, value):
    if not path.exists():
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"path": str(path), "sha256": sha256(path.read_bytes()).hexdigest()}


def capture(directory, baseline):
    result = read(directory / "result.json")
    if not result["closure_submitted"] or result["turns"][-1]["status"] != "completed":
        raise ValueError("Incomplete case cannot enter completed operational evidence")
    output = ARTIFACT_ROOT / "operational-evidence"
    references = {}
    operations_path = output / (directory.name + "-operations.json")
    references["operations"] = save_once(operations_path, collect_operations(directory, baseline))
    compact_path = output / (directory.name + "-compaction.json")
    references["compaction"] = save_once(compact_path, collect_compaction(directory))
    status_path = output / (directory.name + "-executions.json")
    references["execution_kind_counts"] = (
        save_once(status_path, collect_status(directory))
        if not status_path.exists()
        else {"path": str(status_path), "sha256": sha256(status_path.read_bytes()).hexdigest()}
    )
    notes_path = output / (directory.name + "-notes.json")
    rows = [
        json.loads(line)
        for line in (directory / "provider-trace.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    notes = extract(rows)
    body = read(directory / "formal-plan.json")["plan"]
    notes["formal_note_body_kind"] = (
        "null" if body is None else "empty_string" if body == "" else "nonempty_string"
    )
    notes["input_journal"] = str(directory / "provider-trace.jsonl")
    references["notes"] = save_once(notes_path, notes)
    operations = read(operations_path)
    return {
        "case": directory.name,
        "baseline_spent_usd": baseline,
        "case_cost_usd": operations["cost_usd"],
        "role_cost_usd": operations["role_cost_usd"],
        "execution_counts": read(status_path)["counts"],
        "note_body_kind": notes["formal_note_body_kind"],
        "note_calls": notes["call_counts"],
        "note_result_categories": notes["categories"],
        "compaction_roles_boundaries": [
            {
                "role": item["role"],
                "adopted_boundaries": [saved["boundary"] for saved in item["adopted_checkpoints"]],
            }
            for item in read(compact_path)["native_compactions"]
        ],
        "evidence": references,
    }


def main():
    (ARTIFACT_ROOT / "operational-evidence").mkdir(exist_ok=True)
    captures = [capture(HERE / "formal-append/warehouse-r1-P1", "0.022429100")]
    baseline = "0.341333835"
    for name in ORDER:
        directory = ARTIFACT_ROOT / "formal-supplement-v2" / name
        path = directory / "result.json"
        if not path.exists():
            break
        result = read(path)
        if not result["closure_submitted"] or result["turns"][-1]["status"] != "completed":
            break
        captures.append(capture(directory, baseline))
        baseline = result["guard"]["spent_usd"]
    output = ARTIFACT_ROOT / "operational-evidence" / f"completed-{len(captures)}-case-index.json"
    saved = save_once(output, {"completed_cases": captures})
    print(json.dumps({"completed_case_count": len(captures), "index": saved}))


if __name__ == "__main__":
    main()
