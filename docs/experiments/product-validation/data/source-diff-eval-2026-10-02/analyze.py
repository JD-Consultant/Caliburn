"""Verify frozen traces and regenerate descriptive tables; no model or DB access."""

import argparse
import csv
import hashlib
import json
from io import StringIO
from pathlib import Path
from statistics import median

HERE = Path(__file__).resolve().parent
ROOT = next(parent for parent in HERE.parents if (parent / "AGENTS.md").is_file())
FACT_FIELDS = ("frequency", "actor", "approver", "deadline", "scope")
OTHER_FIELDS = ("decision", "reference_action", "protected_task")
CASE_LABELS = {
    "frequency": "頻率更正",
    "actor_scope": "局部分工更正",
    "chain_only": "直接情境依據改變",
    "removed": "來源移除",
    "same_text": "同文新修訂",
    "unknown": "期限未知",
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_events(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_trial(run_dir, row, case):
    events = read_events(run_dir / f"{row['trial_id']}.jsonl")
    responses = [event for event in events if event["event"] == "response"]
    requests = [event for event in events if event["event"] == "request"]
    admitted = [event for event in events if event["event"] == "admitted"]
    tools = [event for event in events if event["event"] == "tool_result"]
    outcomes = [event for event in events if event["event"] == "outcome"]
    require(len(outcomes) == 1, "Expected one outcome")
    # Trace and aggregate rows are appended separately; compare payload, not write time.
    payload = {k: value for k, value in row.items() if k != "at"}
    require(
        {k: outcomes[0][k] for k in payload} == payload,
        "Outcome differs from result row",
    )
    require(
        row["status"] == "completed", "Only complete batch supported by this analysis"
    )
    require(
        len(responses) == len(requests) == len(admitted) == row["model_calls"],
        "Call mismatch",
    )
    require(len(tools) == row["read_calls"], "Tool count mismatch")
    require(
        all(event["status"] == "completed" and event["usage"] for event in responses),
        "Missing usage",
    )
    require(all(event["model"] == "gpt-6-luna" for event in responses), "Model changed")
    for key in ("input_tokens", "output_tokens"):
        require(
            sum(event["usage"][key] for event in responses) == row[key], f"Wrong {key}"
        )
    require(
        sum(
            event["usage"]["input_tokens_details"]["cached_tokens"]
            for event in responses
        )
        == row["cached_input_tokens"],
        "Wrong cached input",
    )
    submissions = [
        item
        for event in responses
        for item in event["output"]
        if item.get("type") == "function_call" and item["name"] == "submit_review"
    ]
    require(len(submissions) == 1, "Expected one submitted review")
    result = json.loads(submissions[0]["arguments"])
    require(result == row["result"], "Submitted review changed")
    expected = case["expected"]
    checks = {
        field: result["facts"][field] == expected["facts"][field]
        for field in FACT_FIELDS
    }
    checks.update({field: result[field] == expected[field] for field in OTHER_FIELDS})
    require(
        checks == row["checks"] and all(checks.values()) == row["all_passed"],
        "Score drift",
    )
    return {
        **row,
        "first_input_tokens": responses[0]["usage"]["input_tokens"],
        "counted_input": sum(event["counted_input"] for event in admitted),
        "checks_passed": sum(checks.values()),
    }


def analyze(run_dir, check_product_code=False):
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    cases = json.loads((run_dir / "cases.json").read_text(encoding="utf-8"))
    case_hash = hashlib.sha256(
        json.dumps(cases, ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()
    require(case_hash == manifest["cases_sha256"], "Frozen cases changed")
    for path, expected_hash in manifest["files_sha256"].items():
        normalized = path.replace("\\", "/")
        # Product code can evolve; the frozen experiment remains independently auditable.
        if normalized.startswith("apps/") and not check_product_code:
            continue
        # Keep the recorded manifest intact after archiving the whole data package.
        historical_prefix = (
            "docs/plans/2026-09-29-target-rebuild/evidence/data/"
            "source-diff-eval-2026-10-02/"
        )
        frozen_file = (
            HERE / normalized.removeprefix(historical_prefix)
            if normalized.startswith(historical_prefix)
            else ROOT / normalized
        )
        require(
            sha256(frozen_file) == expected_hash,
            f"Frozen file changed: {path}",
        )
    rows = read_events(run_dir / "results.jsonl")
    expected_ids = {
        f"{case['case_id']}-{repeat}-{arm}"
        for case in cases
        for repeat in (1, 2)
        for arm in ("full", "diff")
    }
    require(
        len(rows) == len(expected_ids)
        and {r["trial_id"] for r in rows} == expected_ids,
        "Missing/duplicate trials",
    )
    case_index = {case["case_id"]: case for case in cases}
    verified = [verify_trial(run_dir, row, case_index[row["case_id"]]) for row in rows]
    run_events = read_events(run_dir / "run.jsonl")
    require(
        len(run_events) == 1 and run_events[0]["event"] == "completed",
        "Run not complete",
    )
    require(
        sum(r["model_calls"] for r in verified) == run_events[0]["model_calls"],
        "Run calls mismatch",
    )
    require(
        sum(r["counted_input"] for r in verified) == run_events[0]["admitted_input"],
        "Run budget mismatch",
    )
    groups = {}
    for arm in ("full", "diff"):
        group = [row for row in verified if row["arm"] == arm]
        groups[arm] = {
            "trials": len(group),
            "all_passed": sum(row["all_passed"] for row in group),
            **{
                key: sum(row[key] for row in group)
                for key in (
                    "input_tokens",
                    "output_tokens",
                    "cached_input_tokens",
                    "model_calls",
                    "read_calls",
                    "checks_passed",
                    "first_input_tokens",
                    "first_data_characters",
                )
            },
            "elapsed_seconds_sum": round(
                sum(row["elapsed_seconds"] for row in group), 3
            ),
            "elapsed_seconds_median": round(
                median(row["elapsed_seconds"] for row in group), 3
            ),
            "by_check": {
                key: sum(row["checks"][key] for row in group)
                for key in (*FACT_FIELDS, *OTHER_FIELDS)
            },
        }
    files = [
        run_dir / "manifest.json",
        run_dir / "cases.json",
        run_dir / "results.jsonl",
        run_dir / "run.jsonl",
    ]
    files += [run_dir / f"{row['trial_id']}.jsonl" for row in verified]
    summary = {
        "arms": groups,
        "input_reduction_percent": round(
            100 * (1 - groups["diff"]["input_tokens"] / groups["full"]["input_tokens"]),
            2,
        ),
        "raw_files_sha256": {path.name: sha256(path) for path in files},
    }
    table = [
        "| 案例 | 次序 | 全文輸入 tokens | 差異輸入 tokens | 全文通過項／8 | 差異通過項／8 | 全文／差異讀取次數 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    index = {row["trial_id"]: row for row in verified}
    for case in cases:
        for repeat in (1, 2):
            full = index[f"{case['case_id']}-{repeat}-full"]
            diff = index[f"{case['case_id']}-{repeat}-diff"]
            table.append(
                f"| {CASE_LABELS[case['case_id']]} | {repeat} | {full['input_tokens']:,} | {diff['input_tokens']:,}"
                f" | {full['checks_passed']} | {diff['checks_passed']} | {full['read_calls']}／{diff['read_calls']} |"
            )
    return summary, verified, "\n".join(table) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", default="run-02-network", choices=("run-02-network",))
    parser.add_argument(
        "--write", action="store_true", help="Regenerate derived outputs only"
    )
    parser.add_argument(
        "--check-report",
        action="store_true",
        help="Require exact appendix table in report",
    )
    parser.add_argument(
        "--check-code",
        action="store_true",
        help="Also require current product code to match run hashes",
    )
    args = parser.parse_args()
    run_dir = HERE / args.run
    summary, rows, table = analyze(run_dir, args.check_code)
    outputs = {
        "summary.json": json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        "paired-table.md": table,
    }
    fields = [
        "trial_id",
        "arm",
        "repeat",
        "input_tokens",
        "output_tokens",
        "cached_input_tokens",
        "first_input_tokens",
        "model_calls",
        "read_calls",
        "elapsed_seconds",
        "checks_passed",
        "all_passed",
    ]
    stream = StringIO(newline="")
    writer = csv.DictWriter(
        stream, fieldnames=fields, extrasaction="ignore", lineterminator="\n"
    )
    writer.writeheader()
    writer.writerows(rows)
    outputs["metrics.csv"] = stream.getvalue()
    if args.write:
        for name, value in outputs.items():
            (run_dir / name).write_text(value, encoding="utf-8")
    else:
        for name, value in outputs.items():
            require(
                (run_dir / name).read_text(encoding="utf-8") == value,
                f"Derived output changed: {name}",
            )
    if args.check_report:
        report = (ROOT / "docs/reports/project-report/report.md").read_text(
            encoding="utf-8"
        )
        require(table.strip() in report, "Appendix table differs from traces")
    print(
        json.dumps(
            {k: v for k, v in summary.items() if k != "raw_files_sha256"},
            ensure_ascii=False,
            indent=2,
        )
    )
    print(
        "Verified 24 trials, 28 raw artifacts, frozen experiment hashes and unchanged exact scores."
    )
    if args.check_code:
        print("Current product code also matches all three recorded hashes.")


if __name__ == "__main__":
    main()
