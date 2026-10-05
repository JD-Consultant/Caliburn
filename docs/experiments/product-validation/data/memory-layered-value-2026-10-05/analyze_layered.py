"""Offline usage and retrieval projection; no semantic scores are inferred."""

import argparse
import importlib.util
import json
from collections import Counter
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "memory-structure-incremental-2026-10-05"
spec = importlib.util.spec_from_file_location("existing_metrics", SOURCE / "analyze.py")
existing = importlib.util.module_from_spec(spec)
spec.loader.exec_module(existing)


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def source_sequences(objects: dict, references: list[dict]) -> list[int]:
    """Project existing edges only; this is not a semantic support verdict."""
    sequences = set()
    for reference in references:
        if reference["kind"] == "interview":
            sequences.update(reference["sequences"])
            continue
        item = next(
            value
            for value in objects.values()
            if value["layer"] == reference["kind"]
            and value["title"] == reference["target_title"]
        )
        if item["layer"] == "work_situation":
            sequences.update(item["references"])
        else:
            for identity in item["references"]:
                sequences.update(objects[identity]["references"])
    return sorted(sequences)


def analyze(directory: Path) -> dict:
    result = existing.analyze(directory)
    groups = {
        "layered/maintenance": [],
        "layered/reading": [],
        "full_history/reading": [],
    }
    for name, value in result["cells"].items():
        group = (
            "layered/maintenance"
            if not name.startswith("read-")
            else (
                "full_history/reading"
                if name.endswith("-full_history")
                else "layered/reading"
            )
        )
        groups[group].append(value)
    result["totals"] = {}
    for group, values in groups.items():
        stats = Counter()
        cost = Decimal(0)
        for value in values:
            stats.update(
                {
                    key: count
                    for key, count in value.items()
                    if key != "estimated_generation_usd"
                }
            )
            cost += Decimal(value["estimated_generation_usd"])
        stats["max_input_tokens"] = max(
            (value.get("max_input_tokens", 0) for value in values), default=0
        )
        result["totals"][group] = {**stats, "estimated_generation_usd": str(cost)}
    result["reader_selection"] = {}
    material = load(directory / "materials.json")
    result["transitions"] = {}
    before = {}
    for batch in material["batches"]:
        path = directory / f"workspace-{batch['batch_id']}-b2.json"
        if not path.exists():
            continue
        after = load(path)["objects"]
        result["transitions"][batch["batch_id"]] = {
            "added": sorted(after.keys() - before.keys()),
            "removed": sorted(before.keys() - after.keys()),
            "changed": sorted(
                key for key in before.keys() & after.keys() if before[key] != after[key]
            ),
            "unchanged": sorted(
                key for key in before.keys() & after.keys() if before[key] == after[key]
            ),
        }
        before = after
    for probe in material["probes"]:
        snapshot_path = directory / f"workspace-{probe['snapshot_batch_id']}-b2.json"
        if not snapshot_path.exists():
            continue
        objects = load(snapshot_path)["objects"]
        for arm in ("layered", "full_history"):
            cell = f"read-{probe['probe_id']}-{arm}"
            path = directory / f"result-{cell}.json"
            if not path.exists():
                continue
            outcome = load(path)
            reference = load(directory / f"context-{cell}.json")
            counts = Counter()
            body_titles = set()
            for call in outcome["tool_calls"]:
                if "error" in call["result"]:
                    continue
                response = call["result"]
                if call["name"] in ("read_work_understanding", "read_work_situation"):
                    counts["body_characters"] += len(response["body"])
                    body_titles.add(
                        (
                            call["name"].removeprefix("read_"),
                            call["arguments"]["target_title"],
                        )
                    )
                elif call["name"] == "read_interview":
                    counts["raw_text_characters"] += sum(
                        len(message["text"]) for message in response["messages"]
                    )
                elif call["name"].endswith("_map"):
                    counts["extra_map_json_characters"] += len(
                        json.dumps(response, ensure_ascii=False)
                    )
            raw = reference.get("historical_interview", [])
            counts["raw_text_characters"] += sum(len(item["text"]) for item in raw)
            counts["initial_context_json_characters"] = len(
                json.dumps(reference, ensure_ascii=False)
            )
            counts["initial_map_json_characters"] = sum(
                len(json.dumps(value, ensure_ascii=False))
                for key, value in reference.items()
                if key.endswith("_map")
            )
            result["reader_selection"][cell] = {
                **counts,
                "seconds": outcome["seconds"],
                "available_understandings": sum(
                    item["layer"] == "work_understanding" and arm == "layered"
                    for item in objects.values()
                ),
                "available_situations": sum(
                    item["layer"] == "work_situation" and arm == "layered"
                    for item in objects.values()
                ),
                "read_bodies": sorted(body_titles),
                "raw_sequences": [
                    read[1] for read in outcome["reads"] if read[0] == "interview"
                ],
                "preloaded_raw_messages": len(raw),
                "references": outcome["final"]["references"],
                "reachable_interview_sequences": source_sequences(
                    objects, outcome["final"]["references"]
                ),
            }
    summary = directory / "run-summary.json"
    result["run_summary"] = load(summary) if summary.exists() else {"status": "running"}
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    arguments = parser.parse_args()
    result = analyze(arguments.directory)
    (arguments.directory / "analysis.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result["totals"], ensure_ascii=False, indent=2))
