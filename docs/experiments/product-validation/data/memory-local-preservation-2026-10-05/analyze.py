"""Offline trace projection; readable size is never called provider token usage."""

import argparse
import json
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path


def encoded_size(value: object) -> int:
    return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")))


def analyze(directory: Path, *, readers_only: bool = False) -> dict:
    groups = defaultdict(Counter)
    prior_output, counted, requests, responses = {}, {}, Counter(), Counter()
    preserved, costs, waits = Counter(), defaultdict(Decimal), 0.0
    for line in (directory / "trace.jsonl").open(encoding="utf-8"):
        row = json.loads(line)
        cell = row.get("cell", "")
        if readers_only and not cell.startswith("read-"):
            continue
        group = cell.rsplit("-", 1)[-1]
        totals = groups[group]
        event, path = row["event"], row.get("path", "")
        if event == "rate_wait":
            waits += row["seconds"]
        elif event == "request":
            payload = row["payload"]
            if path.endswith("/input_tokens"):
                counted[cell] = payload
                totals["count_requests"] += 1
                continue
            assert path.endswith("/responses")
            assert payload["model"] == "gpt-6-luna"
            assert payload["reasoning"]["effort"] == "high"
            assert all(
                payload.get(key) == value for key, value in counted.pop(cell).items()
            )
            requests[cell] += 1
            totals["model_requests"] += 1
            totals["instructions_chars"] += len(payload.get("instructions", ""))
            totals["tools_serialized_chars"] += encoded_size(payload.get("tools", []))
            totals["output_format_chars"] += encoded_size(payload.get("text", {}))
            items = payload["input"]
            assert sum(item.get("role") == "user" for item in items) == 1
            if cell not in prior_output:
                assert len(items) == 1
                preserved["fresh_episodes"] += 1
            else:
                preserved["continuations"] += 1
                for item in prior_output[cell]:
                    kind = item["type"]
                    if kind == "reasoning":
                        keys = ("id", "encrypted_length", "encrypted_sha256", "summary")
                    elif kind == "function_call":
                        keys = ("call_id", "name", "arguments")
                        assert any(
                            entry.get("type") == "function_call_output"
                            and entry["call_id"] == item["call_id"]
                            for entry in items
                        )
                    elif kind == "message":
                        keys = ("id", "phase", "content")
                    else:
                        raise ValueError(f"Unexpected item kind: {kind}")
                    assert any(
                        entry.get("type") == kind
                        and all(entry.get(key) == item.get(key) for key in keys)
                        for entry in items
                    )
                    preserved[kind] += 1
            for item in items:
                kind = item.get("type")
                if item.get("role") == "user":
                    data = json.loads(item["content"])
                    totals["maps_chars"] += sum(
                        encoded_size(value)
                        for key, value in data.items()
                        if key.endswith("_map") or key == "maps"
                    )
                    totals["question_chars"] += len(data.get("question", ""))
                    if "historical_interview" in data:
                        totals["history_chars"] += encoded_size(
                            data["historical_interview"]
                        )
                    if "situation_changes" in data:
                        totals["diff_chars"] += encoded_size(data["situation_changes"])
                elif kind == "function_call_output":
                    totals["tool_output_chars"] += len(item["output"])
                elif kind == "function_call":
                    totals["tool_argument_chars"] += len(item["arguments"])
                elif kind == "reasoning":
                    totals["opaque_reasoning_items"] += 1
        elif event == "response" and path.endswith("/responses"):
            prior_output[cell] = row["payload"]["output"]
            responses[cell] += 1
            usage = row["payload"]["usage"]
            for key in ("input_tokens", "output_tokens"):
                totals[key] += usage[key]
            totals["cached_input_tokens"] += usage.get("input_tokens_details", {}).get(
                "cached_tokens", 0
            )
            totals["reasoning_tokens"] += usage.get("output_tokens_details", {}).get(
                "reasoning_tokens", 0
            )
        elif event == "settled":
            costs[group] += Decimal(row["estimated_usd"])
        elif event == "tool":
            totals["tool_calls"] += 1
            totals["tool_errors"] += int("error" in row["result"])
            if row["name"].startswith("read_"):
                totals[row["name"]] += 1
    assert requests == responses, (
        "Unsettled generation request; inspect before concluding"
    )
    result = {
        "size_unit": "readable/serialized characters; NOT token attribution; encrypted content excluded",
        "groups": dict(groups),
        "native_continuity": dict(preserved),
        "generation_usd": {key: str(value) for key, value in costs.items()},
        "rate_wait_seconds": waits,
    }
    if not readers_only:
        summary = json.loads(
            (directory / "run-summary.json").read_text(encoding="utf-8")
        )
        budget = summary["budget"]
        pending = sum(
            (Decimal(value) for value in budget["pending"].values()), Decimal(0)
        )
        assert sum(costs.values()) + pending == Decimal(budget["occupied_usd"])
        assert Decimal(budget["occupied_usd"]) <= Decimal("0.05")
        assert Decimal(budget["cumulative_occupied_usd"]) <= Decimal(2)
        if summary["status"] == "completed":
            assert len(summary["outcomes"]) == 10
            assert preserved["fresh_episodes"] == 10
            assert budget["elapsed_seconds"] <= 900
        result.update(status=summary["status"], budget=budget)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    parser.add_argument("--readers-only", action="store_true")
    args = parser.parse_args()
    value = analyze(args.directory, readers_only=args.readers_only)
    print(json.dumps(value, ensure_ascii=False, indent=2))
