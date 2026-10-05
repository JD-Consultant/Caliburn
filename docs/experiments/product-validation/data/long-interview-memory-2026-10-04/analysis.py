"""Offline evidence audit and token accounting; semantic grading stays explicit."""

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from support import assert_isolated_recall_context

HERE = Path(__file__).resolve().parent
ROOT = next(parent for parent in HERE.parents if (parent / "AGENTS.md").exists())
INFRASTRUCTURE_ERRORS = {
    "scope_not_allowed",
    "source_not_available",
    "target_stale",
    "read_limit_exceeded",
}
ARM_LABELS = {
    "full_history": "完整歷史",
    "flat_summary": "單層摘要",
    "hierarchical_memory": "三層 Memory",
    "recent_only": "只有近期",
}


def audit_tool_document(document: dict[str, Any]) -> None:
    if (
        document.get("status") == "rejected"
        and document.get("code") in INFRASTRUCTURE_ERRORS
    ):
        raise ValueError(f"Infrastructure failure: {document['code']}")


def json_lines(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]


def aggregate_usage(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups = {}
    for event in events:
        if event.get("path", "").endswith("/compact"):
            raise ValueError(
                "This generation-only budget cannot validate a compaction run"
            )
        if event["event"] == "provider_error":
            raise ValueError(
                "Provider failure must remain outside valid recall results"
            )
        if event["event"] != "response" or not event.get("path", "").endswith(
            "/responses"
        ):
            continue
        usage = event["payload"]["usage"]
        if usage is None:
            raise ValueError("Completed generation lacks provider usage")
        key = (
            event["phase"],
            event.get("batch"),
            event.get("arm"),
            event.get("repeat"),
        )
        row = groups.setdefault(
            key,
            {
                "phase": key[0],
                "batch": key[1],
                "arm": key[2],
                "repeat": key[3],
                "generation_calls": 0,
                "initial_input_tokens": usage["input_tokens"],
                "input_tokens": 0,
                "output_tokens": 0,
                "cached_tokens": 0,
                "cache_write_tokens": 0,
                "reasoning_tokens": 0,
            },
        )
        for name in ("input_tokens", "output_tokens"):
            row[name] += usage[name]
        details = usage.get("input_tokens_details", {})
        row["cached_tokens"] += details.get("cached_tokens", 0)
        row["cache_write_tokens"] += details.get("cache_write_tokens", 0)
        row["reasoning_tokens"] += usage.get("output_tokens_details", {}).get(
            "reasoning_tokens", 0
        )
        row["generation_calls"] += 1
    for row in groups.values():
        uncached = (
            row["input_tokens"] - row["cached_tokens"] - row["cache_write_tokens"]
        )
        if uncached < 0:
            raise ValueError("Cached input exceeds total input")
        row["estimated_cost_usd"] = (
            uncached * 0.10
            + row["cached_tokens"] * 0.01
            + row["cache_write_tokens"] * 0.125
            + row["output_tokens"] * 0.50
        ) / 1_000_000
    return list(groups.values())


def audit_public_payload(value: Any) -> None:
    if isinstance(value, dict):
        if "encrypted_content" in value:
            raise ValueError("Public evidence contains an opaque provider value")
        for child in value.values():
            audit_public_payload(child)
    elif isinstance(value, list):
        for child in value:
            audit_public_payload(child)


def aggregate_grades(
    grades: list[dict[str, Any]], cases: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Sum documented semantic decisions; never infer correctness from text matching."""
    definitions = {case["case_id"]: case for case in cases}
    rows = []
    for grade in grades:
        selected = grade["cases"]
        if len(selected) != len(definitions) or {
            case["case_id"] for case in selected
        } != set(definitions):
            raise ValueError("Every frozen case needs exactly one semantic decision")
        row = {
            "arm": grade["arm"],
            "repeat": grade["repeat"],
            "fact_pass": 0,
            "fact_total": 0,
            "case_pass": 0,
            "case_total": len(definitions),
            "early_fact_pass": 0,
            "early_fact_total": 0,
            "fully_supported_cases": 0,
            "unsupported_claims": 0,
        }
        for assessment in selected:
            case = definitions[assessment["case_id"]]
            indices = assessment["facts_pass"]
            if len(indices) != len(set(indices)) or any(
                type(index) is not int or not 1 <= index <= len(case["facts"])
                for index in indices
            ):
                raise ValueError("Semantic fact indices are invalid or duplicated")
            if assessment["citation_support"] not in ("complete", "partial", "none"):
                raise ValueError("Unknown citation decision")
            row["fact_pass"] += len(indices)
            row["fact_total"] += len(case["facts"])
            claims = len(assessment.get("unsupported_claims", []))
            row["unsupported_claims"] += claims
            row["case_pass"] += len(indices) == len(case["facts"]) and not claims
            row["fully_supported_cases"] += (
                assessment["citation_support"] == "complete"
                and not assessment["invalid_sequences"]
            )
            if case["range"] == "前段":
                row["early_fact_pass"] += len(indices)
                row["early_fact_total"] += len(case["facts"])
        rows.append(row)
    return rows


def check_report_tables(report: str, measurements: dict[str, Any]) -> None:
    """Check B.13 numbers against audited usage and documented semantic decisions."""
    expected_rows = []
    for grade in measurements["semantic_grades"]:
        expected_rows.append(
            f"| {ARM_LABELS[grade['arm']]} | {grade['repeat']} | "
            f"{grade['fact_pass']}／{grade['fact_total']} | "
            f"{grade['early_fact_pass']}／{grade['early_fact_total']} | "
            f"{grade['fully_supported_cases']}／{grade['case_total']} |"
        )
    reads = {
        (trial["arm"], trial["repeat"]): trial["read_calls"]
        for trial in measurements["trials"]
    }
    for usage in measurements["usage"]:
        if usage["phase"] == "recall":
            expected_rows.append(
                f"| {ARM_LABELS[usage['arm']]} | {usage['repeat']} | "
                f"{usage['initial_input_tokens']:,} | {usage['input_tokens']:,} | "
                f"{usage['generation_calls']} | "
                f"{reads[usage['arm'], usage['repeat']]} |"
            )
    for phase, label in (
        ("memory_capture", "三層 Memory"),
        ("flat_capture", "單層摘要"),
    ):
        captures = [row for row in measurements["usage"] if row["phase"] == phase]
        if captures:
            expected_rows.append(
                f"| {label} | {sum(row['generation_calls'] for row in captures)} | "
                f"{sum(row['input_tokens'] for row in captures):,} | "
                f"{sum(row['output_tokens'] for row in captures):,} | "
                f"{sum(row['estimated_cost_usd'] for row in captures):.6f} |"
            )
    lines = {line.strip() for line in report.splitlines()}
    for row in expected_rows:
        if row not in lines:
            raise ValueError(f"Missing or inconsistent report table row: {row}")


def analyze(run_dir: Path) -> dict[str, Any]:
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    for name, expected in manifest["files_sha256"].items():
        if hashlib.sha256((HERE / name).read_bytes()).hexdigest() != expected:
            raise ValueError(f"Frozen protocol file changed: {name}")
    for name, expected in manifest["supporting_files_sha256"].items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != expected:
            raise ValueError(f"Frozen dependency changed: {name}")
    trace = json_lines(run_dir / "trace.jsonl")
    audit_public_payload(trace)
    for event in trace:
        if event["event"] == "request":
            for item in event.get("payload", {}).get("input", []):
                if item.get("type") == "function_call_output":
                    try:
                        document = json.loads(item["output"])
                    except json.JSONDecodeError:
                        continue  # Successful difference reads are Markdown; rejections are JSON.
                    if isinstance(document, dict):
                        audit_tool_document(document)
    usage = aggregate_usage(trace)
    completed = json_lines(run_dir / "run.jsonl")[-1]
    if completed["event"] != "completed":
        raise ValueError("Run did not finish; do not score a partial run as complete")
    results = json_lines(run_dir / "results.jsonl")
    expected_trials = {
        (arm, repeat)
        for arm in (
            "full_history",
            "flat_summary",
            "hierarchical_memory",
            "recent_only",
        )
        for repeat in (1, 2)
    }
    if {
        (result["arm"], result["repeat"]) for result in results
    } != expected_trials or len(results) != 8:
        raise ValueError("Missing or repeated recall trial")
    for result in results:
        if result["status"] != "completed":
            raise ValueError(f"Incomplete recall: {result['arm']}/{result['repeat']}")
        for read in result["reads"]:
            audit_tool_document(read["output"])
        if result["arm"] != "full_history":
            initial = json.loads(
                (
                    run_dir / f"initial-{result['arm']}-{result['repeat']}.json"
                ).read_text(encoding="utf-8")
            )
            assert_isolated_recall_context(initial)
    maps = json.loads((run_dir / "published-maps.json").read_text(encoding="utf-8"))
    for document in maps.values():
        audit_tool_document(document)
    corpus = json.loads((run_dir / "corpus.json").read_text(encoding="utf-8"))
    captures = json_lines(run_dir / "capture.jsonl")
    if len(captures) != 2 or not all(capture["published"] for capture in captures):
        raise ValueError("Both current Memory batches must publish")
    calls = sum(row["generation_calls"] for row in usage)
    inputs = sum(row["input_tokens"] for row in usage)
    if calls != completed["generation_calls"]:
        raise ValueError("Not every admitted generation has recorded usage")
    if (
        calls > manifest["maximum_calls"]
        or completed["admitted_input_tokens"] > manifest["maximum_input"]
    ):
        raise ValueError("Observed budget exceeded frozen generation bounds")
    measurements = {
        "schema": manifest["schema"],
        "model": manifest["model"],
        "interview_messages": len(corpus),
        "text_characters": sum(len(item["text"]) for item in corpus),
        "generation_calls": calls,
        "input_tokens": inputs,
        "output_tokens": sum(row["output_tokens"] for row in usage),
        "estimated_cost_usd": sum(row["estimated_cost_usd"] for row in usage),
        "compaction_calls": 0,
        "usage": usage,
        "trials": [
            {key: result[key] for key in ("arm", "repeat", "status", "model_calls")}
            | {
                "read_calls": len(result["reads"]),
            }
            for result in results
        ],
        "audits": [
            "frozen_files",
            "isolated_initial_context",
            "successful_read_scope",
            "two_published_snapshots",
            "generation_budget",
            "opaque_projection",
        ],
    }
    review_path = run_dir / "semantic-review.json"
    if review_path.exists():
        review = json.loads(review_path.read_text(encoding="utf-8"))
        if (
            review["results_sha256"]
            != hashlib.sha256((run_dir / "results.jsonl").read_bytes()).hexdigest()
        ):
            raise ValueError("Semantic review does not identify these original answers")
        if (
            len(review["trials"]) != 8
            or {(trial["arm"], trial["repeat"]) for trial in review["trials"]}
            != expected_trials
        ):
            raise ValueError("Semantic review lacks a trial")
        cases = json.loads((HERE / "cases.json").read_text(encoding="utf-8"))
        measurements["semantic_grades"] = aggregate_grades(review["trials"], cases)
    return measurements


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument(
        "--check-report",
        action="store_true",
        help="Check B.13 tables against audited measurements",
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help="Save derived metrics.json; original outputs stay unchanged",
    )
    arguments = parser.parse_args()
    measurements = analyze(arguments.run)
    if arguments.check_report:
        report = (ROOT / "docs/reports/project-report/report.md").read_text(
            encoding="utf-8"
        )
        check_report_tables(report, measurements)
    rendered = json.dumps(measurements, ensure_ascii=False, indent=2)
    if arguments.save:
        (arguments.run / "metrics.json").write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
