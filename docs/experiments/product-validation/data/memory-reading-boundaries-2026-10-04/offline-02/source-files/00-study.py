"""Freeze controlled gaps, then reuse the established single-budget model loop."""

import argparse
import asyncio
import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from decimal import Decimal
from importlib.metadata import version
from pathlib import Path

from fixtures import build_material, context_for_case

HERE = Path(__file__).resolve().parent
SHARED = HERE.parent / "memory-added-value-2026-10-04"
BASELINE = HERE.parent / "memory-reading-policy-2026-10-04/live-01"
sys.path.insert(0, str(SHARED))

import analyze as analysis
import experiment as shared


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def prepare(run_dir):
    baseline_manifest = read_json(BASELINE / "manifest.json")
    material, changes = build_material(read_json(BASELINE / "materials.json"))
    instructions = read_json(BASELINE / "instructions.json")["candidate"]
    if (
        shared.fingerprint(instructions)
        != baseline_manifest["instructions_sha256"]["candidate"]
    ):
        raise ValueError("Frozen current prompt changed")
    tools = [
        *shared.memory_read_definitions(names=shared.READ_NAMES),
        shared.submit_tool(),
    ]
    if shared.fingerprint(tools) != baseline_manifest["tools_sha256"]["raw_memory"]:
        raise ValueError("Frozen tools changed")
    prior = read_json(BASELINE / "result.json")["cumulative_occupied_usd"]
    if Decimal(prior) != Decimal("1.089763360"):
        raise ValueError("Prior budget ledger changed")
    if (shared.MODEL, "high", version("openai")) != (
        baseline_manifest["model"],
        baseline_manifest["effort"],
        baseline_manifest["sdk_version"],
    ):
        raise ValueError("Frozen model or SDK changed")
    cases = read_json(HERE / "cases.json")["cases"]
    template = read_json(BASELINE / "initial-corrections.json")
    windows = {
        case["prompt"]: context_for_case(material, template, case) for case in cases
    }
    schedule = [
        {
            "arm": "raw_memory",
            "repeat": repeat,
            "case_id": case["case_id"],
            "cell_id": f"{case['case_id']}-{repeat}",
        }
        for repeat in (1, 2)
        for case in (cases if repeat == 1 else list(reversed(cases)))
    ]
    sources = [
        HERE / "study.py",
        HERE / "fixtures.py",
        HERE / "test_fixtures.py",
        HERE / "cases.json",
        HERE / "README.md",
        SHARED / "experiment.py",
        SHARED / "support.py",
        SHARED / "analyze.py",
        SHARED.parent / "design-comparisons-2026-10-04/provider_observations.py",
        BASELINE / "manifest.json",
        BASELINE / "instructions.json",
        BASELINE / "materials.json",
        BASELINE / "initial-corrections.json",
        BASELINE / "result.json",
    ]
    manifest = {
        "prepared_at": datetime.now(UTC).isoformat(),
        "kind": "controlled-information-gaps-and-task-field-consistency",
        "model": shared.MODEL,
        "effort": "high",
        "sdk_version": version("openai"),
        "max_output_tokens": shared.MAX_OUTPUT,
        "max_estimated_usd": "0.05",
        "max_seconds": 900,
        "prior_occupied_usd": prior,
        "cumulative_limit_usd": "2.00",
        "schedule": schedule,
        "head": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=shared.ROOT, text=True
        ).strip(),
        "instructions_sha256": shared.fingerprint(instructions),
        "tools_sha256": {"raw_memory": shared.fingerprint(tools)},
        "initial_sha256": {
            case["case_id"]: shared.fingerprint(windows[case["prompt"]])
            for case in cases
        },
        "source_sha256": {
            str(path.relative_to(shared.ROOT)): hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
            for path in sources
        },
        "pricing_basis": baseline_manifest["pricing_basis"],
    }
    for name, value in (
        ("manifest.json", manifest),
        ("materials.json", material),
        ("instructions.json", {"instructions": instructions}),
        ("cases.json", {"cases": cases}),
        ("fixture-changes.json", changes),
        ("tools-raw_memory.json", tools),
    ):
        shared.dump(run_dir / name, value)
    for case in cases:
        shared.dump(
            run_dir / f"initial-{case['case_id']}.json", windows[case["prompt"]]
        )
    (run_dir / "executed-protocol.md").write_bytes((HERE / "README.md").read_bytes())
    source_dir = run_dir / "source-files"
    source_dir.mkdir()
    for index, source in enumerate(sources):
        (source_dir / f"{index:02d}-{source.name}").write_bytes(source.read_bytes())
    shared.dump(
        run_dir / "offline-check.json",
        {
            "provider_calls": 0,
            "schedule_cells": len(schedule),
            "unchanged_original_messages": material["messages"]
            == read_json(BASELINE / "materials.json")["messages"],
            "same_candidate_prompt": True,
            "same_tools": True,
            "preloaded_sequences": [105],
            "grading_not_preloaded": True,
        },
    )
    return (material, cases, manifest), instructions, windows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", required=True)
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    if Path(args.run).name != args.run or args.run in (".", ".."):
        parser.error("A new plain run name is required")
    run_dir = HERE / args.run
    run_dir.mkdir(exist_ok=False)
    prepared, instructions, windows = prepare(run_dir)
    if not args.live:
        print("Frozen boundaries; zero provider calls.")
        return

    def context_builder(_, arm, question):
        if arm != "raw_memory":
            raise ValueError("Only the frozen Memory condition is allowed")
        return json.loads(json.dumps(windows[question], ensure_ascii=False))

    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        runner.run(
            asyncio.wait_for(
                shared.run(
                    run_dir,
                    prepared=prepared,
                    context_builder=context_builder,
                    instructions=instructions,
                ),
                timeout=900,
            )
        )
    shared.dump(run_dir / "metrics.json", analysis.analyze(run_dir))


if __name__ == "__main__":
    main()
