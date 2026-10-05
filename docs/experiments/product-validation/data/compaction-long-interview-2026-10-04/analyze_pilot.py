"""Offline pilot evidence only; no model, database or hypothesis-changing operations."""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from caliburn.adapters.openai_models import model_profile
from caliburn.adapters.response_serialization import restore_response


def audit_native_chains(rows: list[dict[str, Any]]) -> dict[str, Any]:
    prefixes: dict[tuple[str, str], list[dict[str, Any]]] = {}
    pending_calls: dict[tuple[str, str], list[str]] = {}
    key: tuple[str, str] | None = None
    issues = []
    requests = 0
    continuations = 0
    checked_calls = 0
    for row in rows:
        if row.get("path") != "/v1/responses":
            continue
        payload = row["payload"]
        if row["event"] == "request":
            requests += 1
            key = (row["phase"], payload["instructions"])
            items = payload["input"]
            if key in prefixes:
                continuations += 1
                prefix = prefixes[key]
                if items[: len(prefix)] != prefix:
                    issues.append({"request_index": requests, "kind": "native_prefix_changed"})
                call_ids = [
                    item["call_id"]
                    for item in items[len(prefix) :]
                    if item.get("type") == "function_call_output"
                ]
                if call_ids != pending_calls[key]:
                    issues.append({"request_index": requests, "kind": "tool_call_pairing_changed"})
                checked_calls += len(pending_calls[key])
            prefixes[key] = items
        elif row["event"] == "response":
            if key is None:
                raise ValueError("Generation response without its request")
            output = payload["output"]
            prefixes[key] = prefixes[key] + [
                {field: value for field, value in item.items() if field != "status"}
                for item in output
            ]
            pending_calls[key] = [
                item["call_id"] for item in output if item["type"] == "function_call"
            ]
    return {
        "chain_count": len(prefixes),
        "continuations_checked": continuations,
        "tool_results_checked": checked_calls,
        "pending_tool_results": sum(len(calls) for calls in pending_calls.values()),
        "issues": issues,
    }


def inspect_context(run_dir: Path) -> dict[str, Any]:
    rows = [
        json.loads(line)
        for line in (run_dir / "trace.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    requests = [row for row in rows if row["event"] == "request" and row["path"] == "/v1/responses"]
    turns = []
    for turn in range(1, 6):
        first = next(row for row in requests if row.get("turn") == turn)
        items = first["payload"]["input"]
        reference = json.loads(items[-2]["content"])
        exchange = json.loads((run_dir / f"exchange-{turn}.json").read_text(encoding="utf-8"))
        turns.append(
            {
                "turn": turn,
                "event_id": exchange["event_id"],
                "current_input_unmodified_user_message": items[-1]
                == {"role": "user", "content": exchange["employee_input"]["interview_text"]},
                "app_reference_role": items[-2]["role"],
                "reference_fields": list(reference),
                "memory_map_titles": {
                    layer: [entry["target_title"] for entry in reference[layer]["items"]]
                    for layer in ("work_situation_map", "work_understanding_map")
                },
                "recent_interview_sequences": [
                    message["interview_sequence"]
                    for message in reference["historical_interview"]["messages"]
                ],
                "interview_read_boundary": reference["interview_read_boundary"],
            }
        )
    role_inputs = []
    seen_instructions = set()
    for row in requests:
        payload = row["payload"]
        if row["phase"] != "memory" or payload["instructions"] in seen_instructions:
            continue
        seen_instructions.add(payload["instructions"])
        reference = json.loads(payload["input"][-1]["content"])
        role_inputs.append(
            {
                "instructions_sha256": hashlib.sha256(payload["instructions"].encode()).hexdigest(),
                "app_reference_role": payload["input"][-1]["role"],
                "reference_fields": list(reference),
                "required_interview_range": reference.get("required_interview_range"),
                "historical_interview_sequences": [
                    message["interview_sequence"]
                    for message in reference.get("historical_interview", {}).get("messages", [])
                ],
                "situation_changes": [
                    {"change": change["change"], "target_title": change["target_title"]}
                    for change in reference.get("work_situation_changes", [])
                ],
            }
        )
    return {
        "native_chain_audit": audit_native_chains(rows),
        "store_false_on_all_generations": all(row["payload"]["store"] is False for row in requests),
        "truncation_disabled_on_all_generations": all(
            row["payload"]["truncation"] == "disabled" for row in requests
        ),
        "encrypted_state_requested_on_all_generations": all(
            "reasoning.encrypted_content" in row["payload"]["include"] for row in requests
        ),
        "turn_start_inputs": turns,
        "memory_role_inputs": role_inputs,
    }


def summarize_trace(rows: list[dict[str, Any]]) -> dict[str, Any]:
    requests = [r for r in rows if r["event"] == "request"]
    generations = [r for r in rows if r["event"] == "response" and r.get("path") == "/v1/responses"]
    sent = sum(r.get("path") == "/v1/responses" for r in requests)
    usages = [r["payload"].get("usage") for r in generations]
    missing = sum(not isinstance(usage, dict) for usage in usages)
    valid = [usage for usage in usages if isinstance(usage, dict)]
    tools = Counter(
        item["name"]
        for row in generations
        for item in row["payload"].get("output", [])
        if item["type"] == "function_call"
    )
    return {
        "all_outbound_sends": len(requests),
        "generation_sends": sent,
        "generation_responses": len(generations),
        "unanswered_sends": sent - len(generations),
        "count_sends": sum(r.get("path") == "/v1/responses/input_tokens" for r in requests),
        "compaction_sends": sum(r.get("path") == "/v1/responses/compact" for r in requests),
        "missing_usage_responses": missing,
        "input_tokens": sum(u["input_tokens"] for u in valid) if not missing else None,
        "output_tokens": sum(u["output_tokens"] for u in valid) if not missing else None,
        "cached_input_tokens": sum(u["input_tokens_details"]["cached_tokens"] for u in valid)
        if not missing
        else None,
        "reasoning_tokens": sum(u["output_tokens_details"]["reasoning_tokens"] for u in valid)
        if not missing
        else None,
        "peak_generation_input_tokens": max((u["input_tokens"] for u in valid), default=None),
        "tools": dict(tools),
    }


def executed_script(run_dir: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    """Restore only the two observed review changes, and require the pre-outbound hash.

    This snapshot is reconstructed after start, not claimed to have been frozen earlier.
    No guessed source is saved: a mismatch stops reconstruction.
    """
    key = next(path for path in manifest["sha256"] if path.replace("\\", "/").endswith("/pilot.py"))
    expected = manifest["sha256"][key]
    preserved = run_dir / "executed-script.json"
    if preserved.exists():
        recovered: dict[str, Any] = json.loads(preserved.read_text(encoding="utf-8"))
        if (
            recovered["sha256"] != expected
            or hashlib.sha256(recovered["text"].encode()).hexdigest() != expected
        ):
            raise ValueError("Preserved executed script differs from the pre-outbound manifest")
        return recovered
    source = (Path(__file__).parent / "pilot.py").read_text(encoding="utf-8")
    if hashlib.sha256(source.encode()).hexdigest() != expected:
        start = source.index("\n\ndef validate_database_url(")
        end = source.index('\n\nif __name__ == "__main__":', start)
        source = source[:start] + source[end:]
        source = source.replace(
            "                tokens <= 0\n",
            "                tokens <= 0\n                or tokens >= 128_000\n",
        )
        source = source.replace(
            "    url = validate_database_url(test_database_url())\n",
            """    url = test_database_url()
    info = conninfo_to_dict(url)
    if (
        info.get("host") != "127.0.0.1"
        or info.get("port") != "55441"
        or info.get("dbname") != "caliburn_docker_test"
    ):
        parser.error("Only the fixed isolated research database is allowed")
""",
        )
    actual = hashlib.sha256(source.encode()).hexdigest()
    if actual != expected:
        raise ValueError("Cannot recover the exact executed script; do not substitute current code")
    return {
        "sha256": actual,
        "source_path": key,
        "reconstructed_after_start": True,
        "text": source,
    }


def analyze(run_dir: Path) -> dict[str, Any]:
    rows = [
        json.loads(line)
        for line in (run_dir / "trace.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    result = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    generations = [r for r in rows if r["event"] == "response" and r.get("path") == "/v1/responses"]
    prices = [
        model_profile("gpt-6-luna").pricing.estimate_response_cost(restore_response(row["payload"]))
        for row in generations
    ]
    known_prices = [price for price in prices if price is not None]
    source = executed_script(run_dir, manifest)
    (run_dir / "executed-script.json").write_text(
        json.dumps(source, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    summary = summarize_trace(rows)
    output: dict[str, Any] = {
        **summary,
        "result": result,
        "observed_generation_cost_estimate_usd": str(sum(known_prices))
        if len(known_prices) == len(prices)
        else None,
        "cost_scope": "生成 usage 的本機估算，非帳單；計數服務未有公開計費核對，本批沒有 compact。",
        "by_phase": {
            phase: summarize_trace([r for r in rows if r.get("phase") == phase])
            for phase in sorted({r["phase"] for r in rows if "phase" in r})
        },
        "artifact_sha256": {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(run_dir.iterdir())
            if path.is_file()
        },
    }
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--context-only", action="store_true")
    args = parser.parse_args()
    output = args.run_dir / ("context-audit.json" if args.context_only else "analysis.json")
    if output.exists():
        parser.error("Existing analysis must not be overwritten")
    output.write_text(
        json.dumps(
            inspect_context(args.run_dir) if args.context_only else analyze(args.run_dir),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print("Pilot analysis saved; raw observations unchanged")
