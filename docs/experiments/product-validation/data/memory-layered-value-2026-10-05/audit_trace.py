"""Check actual serialized request continuity and cost reconciliation offline."""

import argparse
import json
from collections import Counter
from decimal import Decimal
from pathlib import Path


def audit(directory: Path) -> dict:
    previous, counted = {}, {}
    statistics = Counter()
    cost = Decimal(0)
    with (directory / "trace.jsonl").open(encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            cell = row["cell"]
            if row["event"] == "request":
                payload = row["payload"]
                if row["path"].endswith("/input_tokens"):
                    counted[cell] = payload
                    statistics["count_requests"] += 1
                    continue
                assert row["path"].endswith("/responses")
                assert all(
                    payload.get(key) == value
                    for key, value in counted.pop(cell).items()
                )
                statistics["model_requests"] += 1
                items = payload["input"]
                assert sum(item.get("role") == "user" for item in items) == 1
                assert payload["model"] == "gpt-6-luna"
                assert payload["reasoning"]["effort"] == "high"
                if cell not in previous:
                    assert len(items) == 1
                    statistics["fresh_episodes"] += 1
                    continue
                statistics["continuation_requests"] += 1
                for item in previous[cell]:
                    if item["type"] == "reasoning":
                        keys = ("id", "encrypted_length", "encrypted_sha256", "summary")
                    elif item["type"] == "function_call":
                        keys = ("call_id", "name", "arguments")
                        assert any(
                            entry.get("type") == "function_call_output"
                            and entry["call_id"] == item["call_id"]
                            for entry in items
                        )
                    elif item["type"] == "message":
                        keys = ("id", "phase", "content")
                    else:
                        raise AssertionError(f"Unexpected output type: {item['type']}")
                    assert any(
                        entry.get("type") == item["type"]
                        and all(entry.get(key) == item.get(key) for key in keys)
                        for entry in items
                    )
                    statistics[f"preserved_{item['type']}"] += 1
            elif row["event"] == "response" and row["path"].endswith("/responses"):
                previous[cell] = row["payload"]["output"]
                statistics["model_responses"] += 1
            elif row["event"] == "settled":
                cost += Decimal(row["estimated_usd"])
            elif row["event"] == "provider_error":
                statistics["provider_errors"] += 1
    summary = json.loads((directory / "run-summary.json").read_text(encoding="utf-8"))
    budget = summary["budget"]
    pending = sum(
        (Decimal(amount) for amount in budget["pending"].values()), Decimal(0)
    )
    assert cost + pending == Decimal(budget["occupied_usd"])
    assert Decimal(budget["occupied_usd"]) <= Decimal("0.10")
    assert Decimal(budget["cumulative_occupied_usd"]) <= Decimal(2)
    if summary["status"] == "completed":
        assert statistics["fresh_episodes"] == 14
        assert statistics["model_requests"] == statistics["model_responses"]
        assert len(summary["outcomes"]) == 14
        assert budget["elapsed_seconds"] <= 1200
    return {
        **statistics,
        "estimated_generation_usd": str(cost),
        "pending_allowance_usd": str(pending),
        "status": summary["status"],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    value = audit(args.directory)
    (args.directory / "continuation-audit.json").write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(value, ensure_ascii=False, indent=2))
