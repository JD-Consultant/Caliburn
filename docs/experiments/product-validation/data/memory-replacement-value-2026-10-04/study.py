"""Bounded replacement-value probe, reusing the existing review execution loop."""

import argparse
import asyncio
import hashlib
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / "memory-added-value-2026-10-04"
sys.path.insert(0, str(BASE))

import experiment as shared
from contexts import replacement_context

INSTRUCTIONS = shared.INSTRUCTIONS.replace(
    "App 已提供完整歷史訪談和\nJD文字，直接使用資料中的精確 target_ref；不需要再找 read_jd。",
    "App 已提供 JD 文字與可用的歷史訪談材料，完整原文可用 read_interview 按需回查。\n直接使用資料中的精確 target_ref；不需要再找 read_jd。",
)


def prepare(run_dir):
    material, cases, manifest = shared.materials_and_manifest(run_dir)
    manifest.update(
        max_estimated_usd="0.10",
        max_seconds=1200,
        prior_occupied_usd="1.024756355",
        kind="full-originals-vs-recent-originals-memory-review-proposals",
        arm_labels={"raw": "full_originals", "raw_memory": "recent_originals_memory"},
        recent_boundary={"covered_through_sequence": 104, "through_sequence": 105},
        instructions_sha256=shared.fingerprint(INSTRUCTIONS),
    )
    for path in (
        HERE / "study.py",
        HERE / "contexts.py",
        HERE / "README.md",
        shared.ROOT / "apps/api/src/caliburn/features/interviews/queries.py",
    ):
        manifest["source_sha256"][str(path.relative_to(shared.ROOT))] = hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
    shared.dump(run_dir / "instructions.json", {"instructions": INSTRUCTIONS})
    (run_dir / "executed-protocol.md").write_bytes((HERE / "README.md").read_bytes())
    for case in cases:
        for arm in ("raw", "raw_memory"):
            shared.dump(
                run_dir / f"initial-{case['case_id']}-{arm}.json",
                replacement_context(material, arm, case["prompt"]),
            )
    shared.dump(run_dir / "manifest.json", manifest)
    shared.dump(
        run_dir / "offline-check.json",
        {
            "formal_messages": len(material["messages"]),
            "recent_sequences": [105],
            "work_situations": len(material["maps"]["work_situation"]["items"]),
            "work_understandings": len(material["maps"]["work_understanding"]["items"]),
            "schedule_cells": len(manifest["schedule"]),
            "provider_calls": 0,
        },
    )
    return material, cases, manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", required=True)
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    if Path(args.run).name != args.run or args.run in (".", ".."):
        parser.error("A new plain run name is required")
    directory = HERE / args.run
    directory.mkdir(exist_ok=False)
    prepared = prepare(directory)
    if not args.live:
        print("Prepared full vs recent+Memory inputs; zero provider calls.")
        return
    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        runner.run(
            asyncio.wait_for(
                shared.run(
                    directory,
                    prepared=prepared,
                    context_builder=replacement_context,
                    instructions=INSTRUCTIONS,
                ),
                timeout=1200,
            )
        )


if __name__ == "__main__":
    main()
