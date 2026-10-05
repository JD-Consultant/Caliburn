"""Offline audit; semantic grading remains an explicitly separate manual step."""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from analyze_pilot import summarize_trace
from caliburn.adapters.openai_models import model_profile
from caliburn.adapters.response_serialization import restore_response
from main_support import window_fingerprint
from openai.types.responses.compacted_response import CompactedResponse
from preparation import ARMS


def audit_chains(rows: list[dict[str, Any]]) -> dict[str, Any]:
    prefixes: dict[tuple[str, str], list[Any]] = {}
    pending: dict[tuple[str, str], list[str]] = {}
    owners: dict[tuple[str, str], tuple[str, str]] = {}
    awaiting_adoption: set[tuple[str, str]] = set()
    key = None
    issues = []
    continuations = 0
    tool_results = 0
    adoptions = 0

    def check(items: list[Any], owner: tuple[str, str], index: int) -> None:
        nonlocal continuations, tool_results
        if owner not in prefixes:
            return
        continuations += 1
        prefix = prefixes[owner]
        if items[: len(prefix)] != prefix:
            issues.append({"row": index, "kind": "native_prefix_changed"})
        results = [
            item["call_id"]
            for item in items[len(prefix) :]
            if item.get("type") == "function_call_output"
        ]
        if results != pending.get(owner, []):
            issues.append({"row": index, "kind": "tool_call_pairing_changed"})
        tool_results += len(pending.get(owner, []))
        pending[owner] = []

    for index, row in enumerate(rows, 1):
        path = row.get("path")
        if row.get("event") not in {"request", "response"}:
            continue
        payload = row["payload"]
        arm = row["arm"]
        if row["event"] == "request":
            if path == "/v1/responses/input_tokens":
                owner = (arm, hashlib.sha256(payload["instructions"].encode()).hexdigest())
                owners[arm, window_fingerprint(payload)] = owner
            elif path == "/v1/responses":
                key = (arm, hashlib.sha256(payload["instructions"].encode()).hexdigest())
                check(payload["input"], key, index)
                if key in awaiting_adoption:
                    adoptions += 1
                    awaiting_adoption.remove(key)
                prefixes[key] = payload["input"]
            elif path == "/v1/responses/compact":
                key = owners.get((arm, window_fingerprint(payload)))
                if key is None:
                    issues.append({"row": index, "kind": "compact_without_counted_role"})
                else:
                    check(payload["input"], key, index)
        elif path == "/v1/responses" and key is not None:
            prefixes[key] = prefixes[key] + [
                {field: value for field, value in item.items() if field != "status"}
                for item in payload["output"]
            ]
            pending[key] = [
                item["call_id"] for item in payload["output"] if item["type"] == "function_call"
            ]
        elif path == "/v1/responses/compact" and key is not None:
            prefixes[key] = payload["output"]
            pending[key] = []
            awaiting_adoption.add(key)
    return {
        "chain_count": len(prefixes),
        "continuations_checked": continuations,
        "tool_results_checked": tool_results,
        "compaction_adoptions_checked": adoptions,
        "compactions_not_yet_used_by_generation": len(awaiting_adoption),
        "pending_tool_results": sum(map(len, pending.values())),
        "issues": issues,
    }


def retrievals(rows: list[dict[str, Any]]) -> dict[str, Any]:
    calls = {}
    seen = set()
    reads = []
    for row in rows:
        if row.get("path") not in {"/v1/responses", "/v1/responses/compact"}:
            continue
        payload = row["payload"]
        if row["event"] == "response" and row["path"] == "/v1/responses":
            for item in payload["output"]:
                if item["type"] == "function_call":
                    calls[item["call_id"]] = {
                        "name": item["name"],
                        "arguments": item["arguments"],
                        "event_id": row.get("event_id"),
                        "phase": row["phase"],
                    }
        elif row["event"] == "request":
            for item in payload["input"]:
                if item.get("type") != "function_call_output" or item["call_id"] in seen:
                    continue
                seen.add(item["call_id"])
                call = calls.get(item["call_id"])
                if call is None:
                    continue
                content = item["output"]
                reads.append(
                    {
                        **call,
                        "call_id": item["call_id"],
                        "result_utf8_bytes": len(content.encode()),
                        "result_sha256": hashlib.sha256(content.encode()).hexdigest(),
                        "result": content,
                    }
                )
    names = Counter(item["name"] for item in reads)
    repeated = Counter(
        (item["name"], item["result_sha256"]) for item in reads if item["name"].startswith("read_")
    )
    return {
        "completed_tool_results": len(reads),
        "names": dict(names),
        "repeat_read_results": sum(n - 1 for n in repeated.values()),
        "size_unit": "UTF-8 bytes, not provider tokens; exact overall tokens are separate",
        "entries": reads,
    }


def first_turn_contexts(rows: list[dict[str, Any]], scenario: dict[str, Any]) -> list[Any]:
    seen = set()
    observed = []
    for row in rows:
        if (
            row.get("event") != "request"
            or row.get("path") != "/v1/responses"
            or row.get("phase") != "consultant"
            or row["turn"] in seen
        ):
            continue
        seen.add(row["turn"])
        payload = row["payload"]
        items = payload["input"]
        app = json.loads(items[-2]["content"])
        previous_texts = {
            item["content"]
            for item in items[:-2]
            if item.get("role") == "user" and isinstance(item.get("content"), str)
        }
        expected = next(e for e in scenario["events"] if e["event_id"] == row["event_id"])
        early_raw = [
            e["event_id"]
            for e in scenario["events"][: row["turn"] - 1]
            if e["employee_text"] in previous_texts
        ]
        observed.append(
            {
                "event_id": row["event_id"],
                "turn": row["turn"],
                "raw_current_input_unchanged": items[-1]
                == {"role": "user", "content": expected["employee_text"]},
                "app_data_role": items[-2]["role"],
                "app_fields": list(app),
                "recent_sequences": [
                    m["interview_sequence"] for m in app["historical_interview"]["messages"]
                ],
                "interview_read_boundary": app["interview_read_boundary"],
                "prior_employee_inputs_still_plaintext_native": early_raw,
                "scope_note": (
                    "exact standalone user messages only; "
                    "App copies, tool output and opaque states may retain more"
                ),
                "tools": [tool["name"] for tool in payload["tools"]],
            }
        )
    return observed


def analyze(run_dir: Path) -> dict[str, Any]:
    rows = [json.loads(line) for line in (run_dir / "trace.jsonl").read_text("utf-8").splitlines()]
    manifest = json.loads((run_dir / "manifest.json").read_text("utf-8"))
    scenario = json.loads(Path(__file__).with_name("employee-scenario.json").read_text("utf-8"))
    source_issues = []
    for path, value in manifest["sources"].items():
        source = value["source"]
        source_hashes = {
            hashlib.sha256(text.encode()).hexdigest()
            for text in (source, source.replace("\n", "\r\n"))
        }
        if value["sha256"] not in source_hashes:
            source_issues.append({"path": path, "kind": "frozen_copy_mismatch"})
        local = Path(path)
        if local.exists() and hashlib.sha256(local.read_bytes()).hexdigest() != value["sha256"]:
            source_issues.append({"path": path, "kind": "current_source_changed"})
    arms = {}
    pricing = model_profile("gpt-6-luna").pricing
    for arm in ARMS:
        selected = [row for row in rows if row.get("arm") == arm]
        if not selected:
            continue
        costs = []
        for row in selected:
            if row.get("event") != "response":
                continue
            if row["path"] == "/v1/responses":
                costs.append(pricing.estimate_response_cost(restore_response(row["payload"])))
            elif row["path"] == "/v1/responses/compact":
                costs.append(
                    pricing.estimate_compaction_cost(CompactedResponse.construct(**row["payload"]))
                )
        arm_path = run_dir / arm
        arms[arm] = {
            "trace": summarize_trace(selected),
            "native_audit": audit_chains(selected),
            "estimated_generation_and_compaction_usd": str(sum(c for c in costs if c is not None))
            if all(c is not None for c in costs)
            else None,
            "cost_scope": "provider usage estimate, not invoice; counting admin reserve excluded",
            "completed_events": len(list(arm_path.glob("exchange-*.json"))),
            "phase_usage": {
                phase: summarize_trace([r for r in selected if r["phase"] == phase])
                for phase in sorted({r["phase"] for r in selected})
            },
            "retrievals": retrievals(selected),
            "turn_start_contexts": first_turn_contexts(selected, scenario),
        }
    return {
        "status": "offline_observation",
        "source_issues": source_issues,
        "arms": arms,
        "semantic_grading": "manual grading not inferred from keywords or model claims",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Do not overwrite prior evidence")
    args.output.write_text(json.dumps(analyze(args.run_dir), ensure_ascii=False, indent=2), "utf-8")
