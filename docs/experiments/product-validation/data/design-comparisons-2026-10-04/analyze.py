"""Recalculate every completed or incomplete trial; never hides failures."""

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path

from measurements import score_context, score_locator


def analyze(run_dir: Path, include: list[Path] | None = None) -> dict:
    sources = [*(include or []), run_dir]
    outcomes = [
        (source, json.loads(line))
        for source in sources
        for line in (source / "results.jsonl").read_text(encoding="utf-8").splitlines()
        if line
    ]
    rows = [row for _, row in outcomes]
    if len({row["trial_id"] for row in rows}) != len(rows):
        raise ValueError("Duplicate trial IDs cannot be pooled")
    cases = json.loads((run_dir / "cases.json").read_text(encoding="utf-8"))
    for source in sources:
        if json.loads((source / "cases.json").read_text(encoding="utf-8")) != cases:
            raise ValueError("Cannot pool different frozen cases")
    expected = {case["case_id"]: case for group in cases.values() for case in group}
    for row in rows:
        case = expected[row["case_id"]]
        if row["status"] == "completed":
            checks = (
                score_context(case["expected"], case["sources"], row["answer"])
                if row["suite"] == "context"
                else {"targets": score_locator(case["indices"], row["selected"])}
            )
            if checks != row["checks"] or all(checks.values()) != row["all_passed"]:
                raise ValueError("Saved grade does not match independent recalculation")
    for source, row in outcomes:
        trace = source / f"{row['trial_id']}.jsonl"
        row["cache_write_tokens"] = sum(
            json.loads(line)
            .get("usage", {})
            .get("input_tokens_details", {})
            .get("cache_write_tokens", 0)
            for line in trace.read_text(encoding="utf-8").splitlines()
            if json.loads(line).get("usage")
        )
    groups = defaultdict(list)
    for row in rows:
        groups[(row["suite"], row["arm"])].append(row)
    summaries = []
    for (suite, arm), group in sorted(groups.items()):
        counts = {
            name: sum(row[name] for row in group)
            for name in (
                "input_tokens",
                "output_tokens",
                "cached_input_tokens",
                "cache_write_tokens",
                "model_calls",
                "read_calls",
                "rejected_calls",
                "elapsed_seconds",
            )
        }
        summaries.append(
            {
                "suite": suite,
                "arm": arm,
                "trials": len(group),
                "completed": sum(row["status"] == "completed" for row in group),
                "passed": sum(row["all_passed"] for row in group),
                "checks_passed": sum(sum(row["checks"].values()) for row in group),
                "checks_expected": len(group) * (7 if suite == "context" else 1),
                **counts,
            }
        )
    pairs = defaultdict(dict)
    for row in rows:
        pairs[(row["suite"], row["case_id"], row["repeat"])][row["arm"]] = row
    reductions = {}
    for suite, arms in (
        ("context", ("full", "selective")),
        ("locator", ("uuid", "short")),
    ):
        paired = [
            pair
            for key, pair in pairs.items()
            if key[0] == suite and set(pair) == set(arms)
        ]
        baseline = sum(pair[arms[0]]["input_tokens"] for pair in paired)
        candidate = sum(pair[arms[1]]["input_tokens"] for pair in paired)
        reductions[suite] = {
            "paired_trials": len(paired),
            "baseline_input": baseline,
            "candidate_input": candidate,
            "reduction_percent": round((baseline - candidate) * 100 / baseline, 2)
            if baseline
            else None,
        }
    summary = {
        "observed_trials": len(rows),
        "planned_trials": 36,
        "source_files_sha256": {
            str(source / "results.jsonl"): hashlib.sha256(
                (source / "results.jsonl").read_bytes()
            ).hexdigest()
            for source in sources
        },
        "groups": summaries,
        "paired_input": reductions,
        "failures": [row for row in rows if not row["all_passed"]],
        "standard_price_estimate_usd": round(
            sum(
                (
                    row["input_tokens"]
                    - row["cached_input_tokens"]
                    - row["cache_write_tokens"]
                )
                * 0.1
                + row["cached_input_tokens"] * 0.01
                + row["cache_write_tokens"] * 0.125
                + row["output_tokens"] * 0.5
                for row in rows
            )
            / 1_000_000,
            6,
        ),
    }
    reported = {
        "responses": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "cached_tokens": 0,
        "cache_write_tokens": 0,
    }
    stops = []
    for source in sources:
        for trace in source.glob("*.jsonl"):
            for line in trace.read_text(encoding="utf-8").splitlines():
                event = json.loads(line)
                if event.get("event") == "stopped":
                    stops.append({"run": source.name, **event})
                usage = event.get("usage") if event.get("event") == "response" else None
                if usage:
                    reported["responses"] += 1
                    reported["input_tokens"] += usage["input_tokens"]
                    reported["output_tokens"] += usage["output_tokens"]
                    reported["cached_tokens"] += usage["input_tokens_details"].get(
                        "cached_tokens", 0
                    )
                    reported["cache_write_tokens"] += usage["input_tokens_details"].get(
                        "cache_write_tokens", 0
                    )
    reported["standard_price_estimate_usd"] = round(
        (
            (
                reported["input_tokens"]
                - reported["cached_tokens"]
                - reported["cache_write_tokens"]
            )
            * 0.1
            + reported["cached_tokens"] * 0.01
            + reported["cache_write_tokens"] * 0.125
            + reported["output_tokens"] * 0.5
        )
        / 1_000_000,
        6,
    )
    summary["all_reported_usage_including_interrupted_trials"] = reported
    summary["provider_stops"] = stops
    summary["analysis_script_sha256"] = hashlib.sha256(
        Path(__file__).read_bytes()
    ).hexdigest()
    (run_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    columns = [
        "trial_id",
        "suite",
        "case_id",
        "arm",
        "repeat",
        "status",
        "all_passed",
        "input_tokens",
        "output_tokens",
        "cached_input_tokens",
        "cache_write_tokens",
        "model_calls",
        "read_calls",
        "rejected_calls",
        "elapsed_seconds",
    ]
    with (run_dir / "metrics.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    lines = [
        "| 題目 | 重複 | 組別 | 全項通過 | 累計輸入 | 輸出 | 生成次數 | 讀取次數 | 秒 |",
        "|---|---:|---|---|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['case_id']} | {row['repeat']} | {row['arm']} | {'是' if row['all_passed'] else '否'} | {row['input_tokens']} | {row['output_tokens']} | {row['model_calls']} | {row['read_calls']} | {row['elapsed_seconds']} |"
        )
    (run_dir / "paired-table.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    hashes = [
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}"
        for path in sorted(run_dir.iterdir())
        if path.is_file() and path.name != "SHA256SUMS.txt"
    ]
    (run_dir / "SHA256SUMS.txt").write_text("\n".join(hashes) + "\n", encoding="utf-8")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument(
        "--include",
        type=Path,
        action="append",
        help="Pool retained, disjoint trials; original files remain unchanged",
    )
    args = parser.parse_args()
    result = analyze(args.run, args.include)
    print(
        json.dumps(
            {
                key: result[key]
                for key in (
                    "observed_trials",
                    "groups",
                    "paired_input",
                    "standard_price_estimate_usd",
                )
            },
            ensure_ascii=False,
            indent=2,
        )
    )
