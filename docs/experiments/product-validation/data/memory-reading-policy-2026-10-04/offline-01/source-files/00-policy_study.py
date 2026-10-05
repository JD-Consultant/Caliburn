"""Paired prompt policy review over the previous frozen inputs and shared budget."""

import argparse
import asyncio
import hashlib
import json
import subprocess
import sys
from copy import deepcopy
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path

HERE = Path(__file__).resolve().parent
SHARED = HERE.parent / "memory-added-value-2026-10-04"
BASELINE = HERE.parent / "memory-replacement-value-2026-10-04/live-01"
sys.path.insert(0, str(SHARED))

import experiment as shared


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def prepare(run_dir):
    baseline_manifest = read_json(BASELINE / "manifest.json")
    material = read_json(BASELINE / "materials.json")
    cases = read_json(BASELINE / "source-files/cases.json")["cases"]
    original = read_json(BASELINE / "instructions.json")["instructions"]
    marker = "\n\n本次是隔離研究中的 JD 核對提案"
    _, separator, supplement = original.partition(marker)
    if not separator:
        raise ValueError("Missing frozen research supplement")
    instructions = {
        "original": original,
        "candidate": shared.CONSULTANT_INSTRUCTIONS + separator + supplement,
    }
    if instructions["original"] == instructions["candidate"]:
        raise ValueError("Prompt policy has not changed")
    tools = [
        *shared.memory_read_definitions(names=shared.READ_NAMES),
        shared.submit_tool(),
    ]
    if shared.fingerprint(tools) != baseline_manifest["tools_sha256"]["raw_memory"]:
        raise ValueError("Tools changed from the frozen comparison")
    windows = {}
    for case in cases:
        windows[case["prompt"]] = read_json(
            BASELINE / f"initial-{case['case_id']}-raw_memory.json"
        )
        if windows[case["prompt"]][-1] != {"role": "user", "content": case["prompt"]}:
            raise ValueError("Frozen question mismatch")
        shared.dump(
            run_dir / f"initial-{case['case_id']}.json", windows[case["prompt"]]
        )
    schedule = []
    for repeat in (1, 2):
        variants = (
            ("original", "candidate") if repeat == 1 else ("candidate", "original")
        )
        for case in cases:
            for variant in variants:
                schedule.append(
                    {
                        "arm": "raw_memory",
                        "repeat": repeat,
                        "case_id": case["case_id"],
                        "prompt_variant": variant,
                        "cell_id": f"{case['case_id']}-{variant}-{repeat}",
                    }
                )
    sources = [
        HERE / "policy_study.py",
        HERE / "README.md",
        SHARED / "experiment.py",
        SHARED / "support.py",
        SHARED / "test_runner.py",
        HERE.parent / "design-comparisons-2026-10-04/provider_observations.py",
        shared.ROOT / "apps/api/src/caliburn/agents/job_consultant/instructions.py",
        BASELINE / "instructions.json",
        BASELINE / "materials.json",
        BASELINE / "source-files/cases.json",
    ]
    manifest = {
        "prepared_at": datetime.now(UTC).isoformat(),
        "kind": "frozen-memory-context-original-vs-reading-stop-policy",
        "model": shared.MODEL,
        "effort": "high",
        "sdk_version": version("openai"),
        "max_output_tokens": shared.MAX_OUTPUT,
        "max_estimated_usd": "0.10",
        "max_seconds": 1200,
        "prior_occupied_usd": read_json(BASELINE / "result.json")[
            "cumulative_occupied_usd"
        ],
        "cumulative_limit_usd": "2.00",
        "schedule": schedule,
        "head": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=shared.ROOT, text=True
        ).strip(),
        "instructions_sha256": {
            k: shared.fingerprint(v) for k, v in instructions.items()
        },
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
        "pricing_basis": shared.model_profile(shared.MODEL).pricing.cost_basis,
    }
    if (manifest["model"], manifest["effort"], manifest["sdk_version"]) != (
        baseline_manifest["model"],
        baseline_manifest["effort"],
        baseline_manifest["sdk_version"],
    ):
        raise ValueError("Frozen model, effort or SDK has changed")
    shared.dump(run_dir / "manifest.json", manifest)
    shared.dump(run_dir / "instructions.json", instructions)
    shared.dump(run_dir / "materials.json", material)
    shared.dump(run_dir / "cases.json", {"cases": cases})
    shared.dump(run_dir / "tools-raw_memory.json", tools)
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
            "unique_cell_ids": len({cell["cell_id"] for cell in schedule}),
            "core_criteria": sum(len(case["criteria"]) for case in cases),
            "same_tools_as_baseline": True,
            "same_inputs_for_both_prompts": True,
            "research_supplement_unchanged": True,
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
        print("Frozen paired prompt comparison; zero provider calls.")
        return

    def context_for_cell(_, arm, question):
        if arm != "raw_memory":
            raise ValueError("Only frozen Memory context is allowed")
        return deepcopy(windows[question])

    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        runner.run(
            asyncio.wait_for(
                shared.run(
                    run_dir,
                    prepared=prepared,
                    context_builder=context_for_cell,
                    instructions=lambda cell: instructions[cell["prompt_variant"]],
                ),
                timeout=1200,
            )
        )


if __name__ == "__main__":
    main()
