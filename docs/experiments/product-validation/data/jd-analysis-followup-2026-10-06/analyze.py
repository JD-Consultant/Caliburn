"""Derive observable measures; semantic grading remains explicit in results.md."""

import json
from collections import Counter
from decimal import Decimal
from hashlib import sha256
from pathlib import Path

HERE = Path(__file__).resolve().parent
EDIT_TOOLS = {
    "create_jd_item",
    "create_jd_task",
    "revise_jd_item",
    "revise_jd_profile",
    "move_jd_item",
    "delete_jd_item",
}


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def analyze_stage(folder):
    manifest = read_json(folder / "manifest.json")
    result = read_json(folder / "result.json")
    calls = {}
    rejections = {}
    for line in (folder / "trace.jsonl").read_text(encoding="utf-8").splitlines():
        event = json.loads(line)
        key = (event.get("case_id"), event.get("arm"))
        if event["event"] == "response" and event.get("path") == "/v1/responses":
            calls.setdefault(key, []).extend(
                item["name"]
                for item in event["payload"].get("output", [])
                if item.get("type") == "function_call"
            )
        if event["event"] == "request" and event.get("path") == "/v1/responses":
            for item in event["payload"]["input"]:
                if item.get("type") != "function_call_output":
                    continue
                try:
                    output = json.loads(item["output"])
                except (ValueError, TypeError):
                    continue
                if isinstance(output, dict) and output.get("status") == "rejected":
                    rejections.setdefault(key, {})[item["call_id"]] = output["code"]
    rows = []
    for phase in result["completed"]:
        case_id, arm = phase["case_id"], phase["arm"]
        key = (case_id, arm)
        fixture = next(
            item
            for item in manifest["fixtures"]
            if (item["case_id"], item["arm"]) == key
        )
        after = read_json(folder / f"{case_id}-{arm}-after.json")
        before = fixture["before"]
        before_tasks = {item["task_id"] for item in before["work"]["tasks"]}
        after_tasks = {item["task_id"] for item in after["work"]["tasks"]}
        old_task_citations = {
            item["citation_id"]
            for item in before["sources"]["references"]
            if item["target"]["kind"] == "task"
        }
        after_citations = {
            item["citation_id"] for item in after["sources"]["references"]
        }
        tools = Counter(calls.get(key, []))
        rows.append(
            {
                **phase,
                "areas_before": len(before["work"]["areas"]),
                "areas_after": len(after["work"]["areas"]),
                "area_titles": [item["title"] for item in after["work"]["areas"]],
                "knowledge": [
                    item["name"]
                    for item in after["work"]["capabilities"]
                    if item["kind"] == "knowledge"
                ],
                "skills": [
                    item["name"]
                    for item in after["work"]["capabilities"]
                    if item["kind"] == "skill"
                ],
                "task_links": len(after["work"]["task_links"]),
                "original_task_ids_retained": before_tasks <= after_tasks,
                "original_task_citations_retained": old_task_citations
                <= after_citations,
                "task_descriptions_unchanged": all(
                    any(
                        old["task_id"] == new["task_id"]
                        and old["description"] == new["description"]
                        for new in after["work"]["tasks"]
                    )
                    for old in before["work"]["tasks"]
                ),
                "formal_revision_unchanged": before["profile"]["revision_id"]
                == after["profile"]["revision_id"],
                "needs_recheck": sum(
                    item["needs_recheck"] for item in after["sources"]["references"]
                ),
                "tool_calls": dict(tools),
                "jd_edit_calls": sum(tools[name] for name in EDIT_TOOLS),
                "rejected_call_codes": dict(rejections.get(key, {})),
            }
        )
    return {
        "stage": folder.name,
        "rows": rows,
        "accounting": result["accounting"],
        "result_sha256": sha256((folder / "result.json").read_bytes()).hexdigest(),
    }


if __name__ == "__main__":
    stages = [
        analyze_stage(HERE / name)
        for name in ("live-01", "followup-01", "regression-01")
    ]
    summary = {
        "stages": stages,
        "completed_turns": sum(len(stage["rows"]) for stage in stages),
        "occupied_usd": str(
            sum(Decimal(stage["accounting"]["batch_occupied_usd"]) for stage in stages)
        ),
        "estimated_generation_usd": str(
            sum(
                Decimal(stage["accounting"]["actual_estimated_usd"]) for stage in stages
            )
        ),
        "count_estimate_usd": str(
            sum(Decimal(stage["accounting"]["count_estimated_usd"]) for stage in stages)
        ),
        "observed_usage": {
            key: sum(stage["accounting"][key] for stage in stages)
            for key in (
                "input_tokens",
                "output_tokens",
                "reasoning_tokens",
                "cached_input_tokens",
                "cache_write_input_tokens",
            )
        },
    }
    with (HERE / "measurements.json").open("x", encoding="utf-8") as stream:
        json.dump(summary, stream, ensure_ascii=False, indent=2)
    for stage in stages:
        for row in stage["rows"]:
            print(
                stage["stage"],
                row["case_id"],
                row["arm"],
                row["areas_after"],
                len(row["knowledge"]),
                len(row["skills"]),
                row["task_links"],
                row["original_task_ids_retained"],
                row["formal_revision_unchanged"],
                row["rejected_call_codes"],
            )
    print(
        "TOTAL",
        summary["completed_turns"],
        summary["occupied_usd"],
        summary["observed_usage"],
    )
