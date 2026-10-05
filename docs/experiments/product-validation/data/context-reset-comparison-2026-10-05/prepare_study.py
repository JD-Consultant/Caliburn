"""Freeze all inputs offline. This command does not open a database or provider client."""

import argparse
import json
import platform
import subprocess
from collections.abc import Iterable, Mapping
from importlib.metadata import version
from pathlib import Path
from typing import Any

from baseline_store import HERE, ROOT
from study_batch import ARMS, schedule
from study_manifest import file_hash, freeze_files, save_new, verify_files
from study_prompt import instructions_for
from study_tools import study_tool_definitions


def verify_code_inventory(
    records: Mapping[str, str],
    selected: Iterable[Path],
    *,
    root: Path,
) -> None:
    names = {path.resolve().relative_to(root.resolve()).as_posix() for path in selected}
    if set(records) != names:
        raise ValueError("source_inventory_changed")


def dependencies() -> dict[str, str]:
    return {
        "python": platform.python_version(),
        **{
            name: version(name)
            for name in (
                "openai",
                "httpx2",
                "langgraph",
                "langgraph-checkpoint-postgres",
                "psycopg",
                "SQLAlchemy",
                "pydantic",
                "alembic",
            )
        },
    }


def selected_files(baseline: dict[str, Any]) -> list[Path]:
    return [
        *HERE.glob("*.py"),
        *HERE.glob("*.json"),
        *HERE.glob("prompts/*.md"),
        ROOT / "apps/api/pyproject.toml",
        ROOT / "apps/api/uv.lock",
        ROOT / "docs/experiments/product-validation/2026-10-05-context-reset-comparison-design.md",
        *[
            ROOT / item["path"]
            for item in baseline["source_files"]
            if item["role"] != "historical_context_observation_only"
        ],
        *(ROOT / "apps/api/src/caliburn").rglob("*.py"),
        *(ROOT / "apps/api/src/caliburn").rglob("*.json"),
    ]


def prepare(output: Path) -> dict[str, Any]:
    baseline = json.loads((HERE / "baseline.json").read_text(encoding="utf-8"))
    sources = {item["path"]: item["sha256"] for item in baseline["source_files"]}
    verify_files(sources, root=ROOT)
    cases = json.loads((HERE / "continuation.json").read_text(encoding="utf-8"))["cases"]
    files = freeze_files(selected_files(baseline), root=ROOT, output=output)
    manifest = {
        "status": "prepared_not_authorized",
        "model": "gpt-6-luna",
        "effort": "high",
        "max_output_tokens": 16384,
        "initial_input_budget": 128000,
        "within_turn_compaction_threshold": 160000,
        "max_model_steps": 64,
        "max_tool_calls_per_step": 32,
        "repeats": 1,
        "prior_cumulative_occupied_usd": "1.322929315",
        "cumulative_limit_usd": "2.00",
        "git_head": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "files": files,
        "source_files": sources,
        "dependencies": dependencies(),
        "source_bundle_sha256": file_hash(output / "sources.zip"),
        "instructions": {arm: instructions_for(arm) for arm in ARMS},
        "tools": {arm: study_tool_definitions(arm) for arm in ARMS},
        "schedule": [{"arm": arm, "case_id": case["case_id"]} for arm, case in schedule(cases)],
    }
    save_new(output / "manifest.json", manifest)
    return manifest


def verify_prepared(output: Path) -> dict[str, Any]:
    manifest: dict[str, Any] = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    verify_files(manifest["files"], root=ROOT)
    verify_inventory(manifest)
    verify_files(manifest["source_files"], root=ROOT)
    if file_hash(output / "sources.zip") != manifest["source_bundle_sha256"]:
        raise ValueError("Frozen source bundle changed")
    if dependencies() != manifest["dependencies"]:
        raise ValueError("Frozen dependencies changed")
    for arm in ARMS:
        if (
            instructions_for(arm) != manifest["instructions"][arm]
            or study_tool_definitions(arm) != manifest["tools"][arm]
        ):
            raise ValueError("Frozen prompt or tools changed")
    return manifest


def verify_inventory(manifest: dict[str, Any]) -> None:
    baseline = json.loads((HERE / "baseline.json").read_text(encoding="utf-8"))
    verify_code_inventory(manifest["files"], selected_files(baseline), root=ROOT)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    prepared = prepare(args.output)
    print(json.dumps({"status": prepared["status"], "files": len(prepared["files"]), "calls": 0}))
