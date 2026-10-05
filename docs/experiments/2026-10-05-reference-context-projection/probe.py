"""Measure tool projections from one saved API result; no services or model calls."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


def encode(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def measure(value: object) -> dict[str, int]:
    encoded = encode(value)
    return {"characters": len(encoded), "utf8_bytes": len(encoded.encode("utf-8"))}


def main() -> None:
    root = Path(__file__).resolve().parents[3]
    source = root / (
        "docs/plans/evidence/2026-10-05-occupation-reference-api/"
        "live-search-result.json"
    )
    source_bytes = source.read_bytes()
    saved = json.loads(source_bytes)
    references = [hit["reference"] for hit in saved["response"]["references"]]
    baseline = measure({"references": references})
    candidate_projection = {
        "view": "candidate_overviews",
        "references": [
            {
                "reference_id": reference["reference_id"],
                "title": reference["title"],
                "overview": reference["overview"],
                "work_area_names": [unit["name"] for unit in reference["units"]],
            }
            for reference in references
        ],
    }
    candidate_size = measure(candidate_projection)
    catalogs = [
        {
            "reference_id": reference["reference_id"],
            "title": reference["title"],
            "source_sha256": reference["source_sha256"],
            "unit_count": len(reference["units"]),
            "task_group_count": sum(len(unit["tasks"]) for unit in reference["units"]),
            **measure(reference),
        }
        for reference in references
    ]
    scenarios = []
    for count in sorted({1, min(2, len(references)), len(references)}):
        selected = catalogs[:count]
        total = {
            key: candidate_size[key] + sum(catalog[key] for catalog in selected)
            for key in baseline
        }
        scenarios.append(
            {
                "catalog_selection": "ranked_prefix_for_size_sensitivity_only",
                "catalog_count": count,
                "reference_ids": [catalog["reference_id"] for catalog in selected],
                "tool_result_count": 1 + count,
                "aggregate_size": total,
                "character_reduction_percent": round(
                    (1 - total["characters"] / baseline["characters"]) * 100, 2
                ),
            }
        )
    result = {
        "scope": "offline_tool_payload_character_measurement",
        "source": source.relative_to(root).as_posix(),
        "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
        "probe_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "case_id": saved["case_id"],
        "serialization": "json.ensure_ascii_false.compact_separators",
        "baseline_search_result": baseline,
        "candidate_projection": candidate_projection,
        "candidate_projection_size": candidate_size,
        "catalog_sizes": catalogs,
        "scenarios": scenarios,
        "limits": [
            "One previously observed F01 result; no new retrieval or holdout.",
            "Ranked prefixes are size sensitivity scenarios, not model selections.",
            "No token counts, time, cost, selection quality or JD quality measured.",
            "Aggregate size excludes prompts, call arguments, state and task details.",
            "Candidate projection is a proposal, not the current tool contract.",
        ],
    }
    output = Path(__file__).with_name("projection-results.json")
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "case_id": result["case_id"],
                "baseline": baseline,
                "candidate": candidate_size,
                "scenarios": scenarios,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
