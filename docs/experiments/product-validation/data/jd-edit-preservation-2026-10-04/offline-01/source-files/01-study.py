"""A paired prompt experiment reusing the established bounded provider loop."""

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

from fixtures import context_for_case

HERE = Path(__file__).resolve().parent
SHARED = HERE.parent / "memory-added-value-2026-10-04"
BASELINE = HERE.parent / "memory-reading-boundaries-2026-10-04/live-01"
sys.path.insert(0, str(SHARED))

import analyze as analysis
import experiment as shared

PRESERVATION_RULE = """- 修改 JD 時，保留仍有效且會影響工作理解的數值、期限、適用條件、狀態與責任界線。
  可改寫、合併或去重，但相關資訊須在適用的任務與子項中清楚保留，不因精簡而泛化。
  已被可靠新資訊推翻的舊內容應更正或移除；JD 既有文字及人工修改不自動視為事實。
  提交前，核對受影響內容是否修正一致，且未遺失其他有效條件。
"""


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def prepare(run_dir):
    prior_manifest = read_json(BASELINE / "manifest.json")
    frozen = read_json(BASELINE / "instructions.json")["instructions"]
    if shared.fingerprint(frozen) != prior_manifest["instructions_sha256"]:
        raise ValueError("Frozen baseline prompt changed")
    common = (
        frozen
        + "\n本次參考資料另已提供工作理解的完整正文，可直接核對與引用；不需要再讀已提供正文。\n"
    )
    anchor = "撰寫與修改 JD\n"
    if common.count(anchor) != 1:
        raise ValueError("Expected one JD-writing section")
    instructions = {
        "baseline": common,
        "candidate": common.replace(anchor, anchor + PRESERVATION_RULE, 1),
    }
    tools = [
        *shared.memory_read_definitions(names=shared.READ_NAMES),
        shared.submit_tool(),
    ]
    if shared.fingerprint(tools) != prior_manifest["tools_sha256"]["raw_memory"]:
        raise ValueError("Frozen tools changed")
    prior = read_json(BASELINE / "result.json")["cumulative_occupied_usd"]
    if Decimal(prior) != Decimal("1.104918450"):
        raise ValueError("Prior occupancy changed; recheck authorization")
    if (shared.MODEL, "high", version("openai")) != (
        prior_manifest["model"],
        prior_manifest["effort"],
        prior_manifest["sdk_version"],
    ):
        raise ValueError("Frozen model or SDK changed")
    material = read_json(BASELINE / "materials.json")
    cases = read_json(HERE / "cases.json")["cases"]
    windows = {case["prompt"]: context_for_case(material, case) for case in cases}
    schedule = [
        {
            "arm": "raw_memory",
            "prompt_variant": variant,
            "repeat": repeat,
            "case_id": case["case_id"],
            "cell_id": f"{case['case_id']}-{variant}-{repeat}",
        }
        for repeat in (1, 2)
        for case in (cases if repeat == 1 else list(reversed(cases)))
        for variant in (
            ("baseline", "candidate") if repeat == 1 else ("candidate", "baseline")
        )
    ]
    sources = (
        [
            HERE / name
            for name in (
                "README.md",
                "study.py",
                "fixtures.py",
                "test_fixtures.py",
                "cases.json",
            )
        ]
        + [SHARED / name for name in ("experiment.py", "support.py", "analyze.py")]
        + [
            SHARED.parent / "design-comparisons-2026-10-04/provider_observations.py",
            BASELINE / "manifest.json",
            BASELINE / "instructions.json",
            BASELINE / "materials.json",
            BASELINE / "result.json",
            shared.ROOT / "apps/api/src/caliburn/adapters/openai_models.py",
            shared.ROOT / "apps/api/src/caliburn/adapters/openai_responses.py",
        ]
    )
    manifest = {
        "prepared_at": datetime.now(UTC).isoformat(),
        "kind": "paired-jd-edit-preservation-not-product-writes",
        "model": shared.MODEL,
        "effort": "high",
        "sdk_version": version("openai"),
        "max_output_tokens": shared.MAX_OUTPUT,
        "max_estimated_usd": "0.05",
        "max_seconds": 900,
        "authorization": "User approved US$0.05/15 minutes for this batch, within cumulative US$2",
        "prior_occupied_usd": prior,
        "cumulative_limit_usd": "2.00",
        "schedule": schedule,
        "head": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=shared.ROOT, text=True
        ).strip(),
        "instructions_sha256": {
            key: shared.fingerprint(value) for key, value in instructions.items()
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
        "pricing_basis": prior_manifest["pricing_basis"],
    }
    for name, value in (
        ("manifest.json", manifest),
        ("materials.json", material),
        ("instructions.json", instructions),
        ("cases.json", {"cases": cases}),
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
            "same_paired_initial_context": True,
            "same_tools": True,
            "original_messages_and_memory_unchanged": True,
            "grading_not_preloaded": True,
            "candidate_added_characters": len(instructions["candidate"])
            - len(instructions["baseline"]),
        },
    )
    return (material, cases, manifest), instructions, windows


def analyze_run(run_dir):
    metrics = analysis.analyze(run_dir)
    scheduled = {
        row["cell_id"]: row for row in read_json(run_dir / "manifest.json")["schedule"]
    }
    for row in metrics["cells"]:
        row["prompt_variant"] = scheduled[row["cell_id"]]["prompt_variant"]
        initial = read_json(run_dir / f"initial-{row['case_id']}.json")
        task = json.loads(initial[0]["content"])["jd_draft"]["work_tasks"][0]
        before = {field["target_ref"]: field["text"] for field in task["fields"]}
        cell = read_json(run_dir / f"result-{row['cell_id']}.json")
        changes = cell["proposal"]["changes"] if cell["proposal"] else []
        row["out_of_scope_targets"] = [
            change["target_ref"]
            for change in changes
            if change["target_ref"] not in before
        ]
        after = dict(before)
        after.update({change["target_ref"]: change["value"] for change in changes})
        shared.dump(run_dir / f"after-{row['cell_id']}.json", after)
    shared.dump(run_dir / "metrics.json", metrics)


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
        print("Paired editing inputs frozen; zero provider calls.")
        return

    def context_builder(_, arm, question):
        if arm != "raw_memory":
            raise ValueError("Only frozen Memory condition allowed")
        return json.loads(json.dumps(windows[question], ensure_ascii=False))

    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        runner.run(
            asyncio.wait_for(
                shared.run(
                    run_dir,
                    prepared=prepared,
                    context_builder=context_builder,
                    instructions=lambda cell: instructions[cell["prompt_variant"]],
                ),
                timeout=900,
            )
        )
    analyze_run(run_dir)


if __name__ == "__main__":
    main()
