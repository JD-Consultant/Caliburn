"""Offline observation of a continued journey; no model call or automatic semantic score."""

import argparse
import json
from pathlib import Path
from typing import Any

from analyze_main import analyze, audit_chains, retrievals
from analyze_pilot import summarize_trace
from preparation import ARMS


def user_text(item: dict[str, Any]) -> str | None:
    if item.get("role") != "user":
        return None
    content = item.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            part["text"]
            for part in content
            if part.get("type") in ("input_text", "output_text", "text")
            and isinstance(part.get("text"), str)
        )
    return None


def visible_interview_events(
    items: list[dict[str, Any]],
    events: list[dict[str, Any]],
) -> dict[str, Any]:
    texts = [text for item in items if (text := user_text(item)) is not None]
    standalone = [
        event["event_id"] for event in events if event["employee_text"] in texts
    ]
    app_copy = [
        event["event_id"]
        for event in events
        if any(
            event["employee_text"] in text and text != event["employee_text"]
            for text in texts
        )
    ]
    return {
        "standalone_user": standalone,
        "app_copy": app_copy,
        "opaque_state_present": any(
            "encrypted_content" in item or "encrypted_sha256" in item for item in items
        ),
        "scope": "User strings and canonical content blocks; opaque meaning is not inspected.",
    }


def read_rows(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as source:
        return [json.loads(line) for line in source]


def prefix_rows(
    rows: list[dict[str, Any]], safe_items: list[Any]
) -> list[dict[str, Any]]:
    completed = [
        row
        for row in rows
        if row.get("arm") == ARMS[0]
        and (
            row.get("phase") == "consultant"
            and row.get("turn", 10_000) <= 51
            or row.get("phase") == "memory"
            and row.get("after_event") in ("e012", "e028", "e044")
        )
    ]
    preparation = []
    for row in rows:
        if row.get("arm") != ARMS[0] or row.get("event_id") != "e052":
            continue
        if row.get("path") == "/v1/responses":
            break
        preparation.append(row)
        if (
            row.get("event") == "response"
            and row.get("path") == "/v1/responses/compact"
            and row["payload"]["output"] == safe_items
        ):
            return [*completed, *preparation]
    raise ValueError("The reused safe compaction is missing from the prior trace")


def observe(run_dir: Path) -> dict[str, Any]:
    root = run_dir.parent
    new_rows = read_rows(run_dir / "trace.jsonl")
    prior_rows = read_rows(root / "main-02/trace.jsonl")
    preflight = json.loads(
        (root / "continuation-preflight.json").read_text(encoding="utf-8")
    )
    prefix = prefix_rows(prior_rows, preflight["safe_native_items"])
    observations = analyze(run_dir)
    scenario = json.loads((root / "employee-scenario.json").read_text(encoding="utf-8"))
    first = next(
        (
            row
            for row in new_rows
            if row.get("arm") == ARMS[0]
            and row.get("event") == "request"
            and row.get("path") == "/v1/responses"
        ),
        None,
    )
    safe_items_match = (
        first is not None
        and first["payload"]["input"][:-2] == preflight["safe_native_items"]
    )
    observations["continuation"] = {
        "completed_prefix_events": 51,
        "prefix_native_audit": audit_chains(prefix),
        "first_new_request_reuses_exact_safe_items": safe_items_match,
        "prior_incomplete_event_052": "Failed generations and Step compaction excluded from completed-method metrics; adopted pre-work compaction/count retained. All attempts remain in cumulative budget.",
        "native_visibility_authority": "Use native_visibility for original-source availability; the earlier turn_start_contexts field only inspected string-form user messages and undercounts canonical content blocks.",
    }
    for arm, result in observations["arms"].items():
        selected = [row for row in new_rows if row.get("arm") == arm]
        method_rows = [*prefix, *selected] if arm == ARMS[0] else selected
        result["complete_method_trace"] = summarize_trace(method_rows)
        result["complete_method_phase_usage"] = {
            phase: summarize_trace(
                [row for row in method_rows if row["phase"] == phase]
            )
            for phase in sorted({row["phase"] for row in method_rows})
        }
        result["complete_method_retrievals"] = retrievals(method_rows)
        result["native_visibility"] = []
        seen = set()
        for row in method_rows:
            if (
                row.get("phase") != "consultant"
                or row.get("event") != "request"
                or row.get("path") != "/v1/responses"
                or row["turn"] in seen
            ):
                continue
            seen.add(row["turn"])
            result["native_visibility"].append(
                {
                    "event_id": row["event_id"],
                    "turn": row["turn"],
                    **visible_interview_events(
                        row["payload"]["input"][:-2],
                        scenario["events"][: row["turn"] - 1],
                    ),
                }
            )
        result["arm_status"] = (
            "completed" if (run_dir / arm / "result.json").is_file() else "incomplete"
        )
        result["prefix_rows_included"] = len(prefix) if arm == ARMS[0] else 0
    observations["cumulative_spend_scope"] = (
        "main-01 reserve + every main-02 attempt + this phase, including discarded attempts; see allowance/result, not complete-method tokens alone."
    )
    return observations


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Use a new observation output; never overwrite prior evidence")
    args.output.write_text(
        json.dumps(observe(args.run_dir), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
