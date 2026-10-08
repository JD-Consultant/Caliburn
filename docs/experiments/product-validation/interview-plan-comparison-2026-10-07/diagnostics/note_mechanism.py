"""Deduplicate real note calls and preserve exact model diff/result evidence."""

import json
from collections import Counter
from pathlib import Path

NAMES = {"read_interview_plan", "edit_interview_plan"}


def extract(rows):
    calls = {}
    results = {}
    for row in rows:
        for item in row.get("output", []):
            if item.get("type") == "function_call" and item.get("name") in NAMES:
                key = item["call_id"]
                value = {"name": item["name"], "argument_text": item["arguments"]}
                if key in calls and calls[key] != value:
                    raise ValueError("A note call ID has contradictory original arguments")
                calls[key] = value
        for item in row.get("input", []):
            if item.get("type") == "function_call_output":
                key = item["call_id"]
                if key in results and results[key] != item["output"]:
                    raise ValueError("A call ID has contradictory original tool results")
                results[key] = item["output"]
    evidence = []
    for key, call in calls.items():
        raw = results.get(key)
        parsed = json.loads(raw) if raw is not None else None
        if parsed is None:
            category = "result_unobserved"
        elif parsed.get("status") in {"updated", "unchanged"}:
            category = parsed["status"]
        elif parsed.get("status") == "rejected":
            code = parsed.get("code")
            category = {
                "invalid_patch": "format_rejected",
                "invalid_arguments": "arguments_rejected",
                "patch_context_not_found": "location_rejected",
                "patch_context_not_unique": "location_rejected",
                "patch_limit_exceeded": "capacity_rejected",
                "read_limit_exceeded": "capacity_rejected",
                "write_result_limit_exceeded": "capacity_rejected",
            }.get(code, "other_rejected")
        elif call["name"] == "read_interview_plan":
            category = "read"
        else:
            category = "unclassified_result"
        evidence.append(
            {"call_id": key, **call, "result_text": raw, "result": parsed, "category": category}
        )
    return {
        "calls": evidence,
        "call_counts": dict(Counter(call["name"] for call in calls.values())),
        "categories": dict(Counter(item["category"] for item in evidence)),
        "exact_rejection_reasons": dict(
            Counter(
                (item["result"].get("code", "unknown") + ": " + item["result"].get("message", ""))
                for item in evidence
                if item["result"] is not None and item["result"].get("status") == "rejected"
            )
        ),
    }


def main():
    import sys

    directory = Path(sys.argv[1])
    output = Path(sys.argv[2])
    if output.exists():
        raise RuntimeError("Mechanism evidence already exists")
    rows = [
        json.loads(line)
        for line in (directory / "provider-trace.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    result = extract(rows)
    plan = json.loads((directory / "formal-plan.json").read_text(encoding="utf-8"))
    result["formal_note_body_present"] = plan["plan"] is not None
    result["formal_note_body_kind"] = (
        "null"
        if plan["plan"] is None
        else "empty_string"
        if plan["plan"] == ""
        else "nonempty_string"
    )
    result["input_journal"] = str(directory / "provider-trace.jsonl")
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {key: value for key, value in result.items() if key != "calls"}, ensure_ascii=False
        )
    )


if __name__ == "__main__":
    main()
