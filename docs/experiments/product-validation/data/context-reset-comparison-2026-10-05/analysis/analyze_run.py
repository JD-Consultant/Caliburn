"""Project immutable study traces into auditable metrics; no provider or DB calls."""

import hashlib
import json
from collections import Counter
from decimal import Decimal
from pathlib import Path

PACKET = Path(__file__).resolve().parents[1]
RUN = PACKET / "prepared-01"


def analyze(rows):
    arms = {}
    previous_costs = {
        key: Decimal(0)
        for key in ("actual_estimated_usd", "count_estimated_usd", "pending_reserved_usd")
    }
    for row in rows:
        arm = row.get("arm")
        if arm not in ("raw", "summary", "memory"):
            continue
        group = arms.setdefault(arm, {"cases": {}})
        case = group["cases"].setdefault(
            row["case_id"],
            {
                "input_tokens": 0,
                "output_tokens": 0,
                "cached_input_tokens": 0,
                "cache_write_input_tokens": 0,
                "reasoning_tokens": 0,
                "count_calls": 0,
                "generation_calls": 0,
                "compaction_calls": 0,
                "estimated_usd": "0",
                "actual_estimated_usd": "0",
                "count_estimated_usd": "0",
                "pending_reserved_usd": "0",
                "tools": [],
                "request_input_counts": [],
                "tool_results": {},
                "provider_seconds": 0,
            },
        )
        path = row.get("path", "")
        payload = row.get("payload", {})
        if row["event"] == "request":
            if path.endswith("input_tokens"):
                case["count_calls"] += 1
            elif path.endswith("compact"):
                case["compaction_calls"] += 1
            else:
                case["generation_calls"] += 1
                case["request_input_counts"].append(row["counted_input_tokens"])
                for item in payload.get("input", []):
                    if item.get("type") == "function_call_output":
                        case["tool_results"][item["call_id"]] = item["output"]
        elif row["event"] == "response":
            case["provider_seconds"] += row["duration_seconds"]
            if not path.endswith("input_tokens") and row["http_status"] == 200:
                usage = payload.get("usage") or {}
                case["input_tokens"] += usage.get("input_tokens", 0)
                case["output_tokens"] += usage.get("output_tokens", 0)
                case["cached_input_tokens"] += (usage.get("input_tokens_details") or {}).get(
                    "cached_tokens", 0
                )
                case["cache_write_input_tokens"] += (usage.get("input_tokens_details") or {}).get(
                    "cache_write_tokens", 0
                )
                case["reasoning_tokens"] += (usage.get("output_tokens_details") or {}).get(
                    "reasoning_tokens", 0
                )
                for item in payload.get("output", []):
                    if path == "/v1/responses" and item.get("type") == "function_call":
                        case["tools"].append({k: item[k] for k in ("call_id", "name", "arguments")})
        for key, previous in previous_costs.items():
            now = Decimal(row["accounting"][key])
            case[key] = str(Decimal(case[key]) + now - previous)
            previous_costs[key] = now
        case["estimated_usd"] = str(sum((Decimal(case[k]) for k in previous_costs), Decimal(0)))
    for group in arms.values():
        cases = group["cases"].values()
        group["totals"] = {
            key: sum(c[key] for c in cases)
            for key in (
                "input_tokens",
                "output_tokens",
                "cached_input_tokens",
                "cache_write_input_tokens",
                "reasoning_tokens",
                "count_calls",
                "generation_calls",
                "compaction_calls",
                "provider_seconds",
            )
        }
        for key in (*previous_costs, "estimated_usd"):
            group["totals"][key] = str(sum((Decimal(c[key]) for c in cases), Decimal(0)))
        group["totals"]["tool_calls"] = dict(Counter(t["name"] for c in cases for t in c["tools"]))
        for case in cases:
            ids = {t["call_id"] for t in case["tools"]}
            case["tool_results"] = {k: v for k, v in case["tool_results"].items() if k in ids}
    return arms


def verify_continuation(rows):
    """Audit this run's non-compacted native prefixes using the product projection."""
    assert not any(r.get("path", "").endswith("compact") for r in rows)
    counts = {}
    for arm in ("raw", "summary", "memory"):
        requests = [
            r
            for r in rows
            if r.get("arm") == arm and r["event"] == "request" and r["path"] == "/v1/responses"
        ]
        replies = {
            r["request_id"]: r
            for r in rows
            if r.get("arm") == arm and r["event"] == "response" and r["path"] == "/v1/responses"
        }
        for previous, following in zip(requests, requests[1:], strict=False):
            # Same projection as response_serialization.response_input_items:
            # omit output-only top-level status, retain phase and opaque hashes.
            output = [
                {k: v for k, v in item.items() if k != "status"}
                for item in replies[previous["request_id"]]["payload"]["output"]
            ]
            prefix = previous["payload"]["input"] + output
            assert following["payload"]["input"][: len(prefix)] == prefix
        counts[arm] = len(requests) - 1
    return counts


if __name__ == "__main__":
    final = json.loads((RUN / "result.json").read_text(encoding="utf-8"))
    data = (RUN / "trace.jsonl").read_bytes()
    rows = [json.loads(line) for line in data.decode("utf-8").splitlines()]
    result = analyze(rows)
    native_transitions = verify_continuation(rows)
    for arm, group in result.items():
        group["completed"] = final["completed"][arm]
        assert group["completed"] == [
            p.stem.split("-")[-1] for p in sorted(RUN.glob(f"exchange-{arm}-*.json"))
        ]
    for key in (
        "input_tokens",
        "output_tokens",
        "cached_input_tokens",
        "cache_write_input_tokens",
        "reasoning_tokens",
        "count_calls",
        "generation_calls",
        "compaction_calls",
    ):
        assert sum(g["totals"][key] for g in result.values()) == final["usage"][key], key
    for key in ("actual_estimated_usd", "count_estimated_usd", "pending_reserved_usd"):
        assert sum((Decimal(g["totals"][key]) for g in result.values()), Decimal(0)) == Decimal(
            final["usage"][key]
        ), key
    assert data == (RUN / "trace.jsonl").read_bytes(), "trace still changing"
    target = PACKET / "analysis/metrics.json"
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (PACKET / "analysis/provenance.json").write_text(
        json.dumps(
            {
                "status": final["status"],
                "trace_records": len(rows),
                "trace_bytes": len(data),
                "trace_sha256": hashlib.sha256(data).hexdigest(),
                "result_sha256": hashlib.sha256((RUN / "result.json").read_bytes()).hexdigest(),
                "analysis_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "accounting_reconciled": True,
                "native_prefix_transitions_verified": native_transitions,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {arm: {"completed": x["completed"], **x["totals"]} for arm, x in result.items()},
            ensure_ascii=False,
            indent=2,
        )
    )
