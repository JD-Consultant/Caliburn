"""Project observed usage and reads only; semantic grading remains separate."""

import argparse
import json
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path


def analyze(run_dir: Path) -> dict:
    cells = defaultdict(Counter)
    costs = defaultdict(lambda: Decimal(0))
    for line in (run_dir / "trace.jsonl").read_text(encoding="utf-8").splitlines():
        event = json.loads(line)
        cell = event.get("cell", "")
        stats = cells[cell]
        if event["event"] == "response" and event["path"].endswith("/responses"):
            usage = event["payload"].get("usage") or {}
            stats["model_responses"] += 1
            stats["input_tokens"] += usage.get("input_tokens", 0)
            stats["cached_input_tokens"] += (
                usage.get("input_tokens_details") or {}
            ).get("cached_tokens", 0)
            stats["output_tokens"] += usage.get("output_tokens", 0)
            stats["reasoning_tokens"] += (usage.get("output_tokens_details") or {}).get(
                "reasoning_tokens", 0
            )
            stats["max_input_tokens"] = max(
                stats["max_input_tokens"], usage.get("input_tokens", 0)
            )
        elif event["event"] == "settled":
            costs[cell] += Decimal(event["estimated_usd"])
        elif event["event"] == "rate_wait":
            stats["rate_wait_seconds"] += event["seconds"]
        elif event["event"] == "tool":
            stats["tool_calls"] += 1
            stats[f"tool:{event['name']}"] += 1
            stats["tool_errors"] += int("error" in event["result"])
            if event["name"].startswith("read_"):
                stats["read_characters"] += len(
                    json.dumps(event["result"], ensure_ascii=False)
                )
            if event["name"] == "read_interview":
                stats["interview_messages_returned"] += len(
                    event["result"].get("messages", [])
                )
    projected = {
        cell: {**stats, "estimated_generation_usd": str(costs[cell])}
        for cell, stats in cells.items()
        if cell
    }
    totals = {}
    for arm in ("two_layer", "one_collection"):
        for phase in ("maintenance", "reading"):
            selected = [
                name
                for name in projected
                if arm in name and name.startswith("read-") == (phase == "reading")
            ]
            stats = Counter()
            for name in selected:
                stats.update(cells[name])
            stats["max_input_tokens"] = max(
                (cells[name]["max_input_tokens"] for name in selected), default=0
            )
            totals[f"{arm}/{phase}"] = {
                **stats,
                "estimated_generation_usd": str(
                    sum((costs[name] for name in selected), Decimal(0))
                ),
            }
    snapshots = {}
    for path in sorted(run_dir.glob("workspace-*.json")):
        value = json.loads(path.read_text(encoding="utf-8"))
        stats = {}
        for layer in ("work_situation", "work_understanding"):
            objects = [
                item for item in value["objects"].values() if item["layer"] == layer
            ]
            stats[layer] = {
                "objects": len(objects),
                "body_characters": sum(len(item["body"]) for item in objects),
                "reference_edges": sum(len(item["references"]) for item in objects),
                "map_characters": len(
                    json.dumps(
                        [
                            {
                                "target_title": item["title"],
                                "description": item["description"],
                            }
                            for item in objects
                        ],
                        ensure_ascii=False,
                    )
                ),
            }
        snapshots[path.name] = stats
    return {
        "method": "response usage once per HTTP response; tools once per actual invoke, not repeated native history; characters are not tokens",
        "cells": projected,
        "totals": totals,
        "snapshots": snapshots,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("run_directory", type=Path)
    args = parser.parse_args()
    result = analyze(args.run_directory)
    (args.run_directory / "analysis.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result["totals"], ensure_ascii=False, indent=2))
