"""One paired experiment, reusing the frozen workspace, episode, and budget."""

import argparse
import asyncio
import importlib.util
import sys
import time
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx2
from caliburn.adapters.openai_credentials import read_openai_api_key
from caliburn.adapters.openai_responses import (
    count_response_input,
    create_response,
    create_responses_client,
)
from completion_contract import completion_schema, structured_request

HERE = Path(__file__).resolve().parent
FUNDED_DIRECTORY = HERE / "live-01"
SOURCE = HERE.parent / "memory-structure-incremental-2026-10-05"
ROOT = HERE.parents[4]
sys.path.insert(0, str(SOURCE))
from episode import (
    run_episode,
)
from protocol import context, instructions, reader_context
from workspace import Workspace, tool_definitions

spec = importlib.util.spec_from_file_location("structure_support", SOURCE / "study.py")
support = importlib.util.module_from_spec(spec)
spec.loader.exec_module(support)
dump, load, hash_file = support.dump, support.load, support.hash_file
PRIOR = Decimal("1.270089235")
MAX_USD = Decimal("0.10")
MAX_SECONDS = 1200
ARMS = ("baseline", "coherent")


def prepared_material() -> tuple[dict, dict]:
    material, grading = load(SOURCE / "materials.json"), load(SOURCE / "grading.json")
    material["probes"].append(
        {
            "probe_id": "resolved_approval",
            "snapshot_batch_id": "extension",
            "question": "請依目前資訊重新整理預約乙的維護與變更處理工作，交代週期、員工行動、核准範圍與誰決定；仍未確認的部分才另列。附上本次採用的來源定位。",
        }
    )
    grading["probe_checks"].append(
        {
            "probe_id": "resolved_approval",
            "checks": [
                "maintenance_periods",
                "maintenance_scope",
                "approver_resolved",
                "approval_scope",
                "shared_authority",
            ],
        }
    )
    return material, grading


def prepare(run_dir: Path) -> None:
    previous = support.load_previous()
    run_dir.mkdir(parents=True, exist_ok=False)
    material, grading = prepared_material()
    base_prompts = instructions()
    prompts = {
        "baseline": base_prompts["single"],
        "coherent": base_prompts["single"]
        + "\n\n"
        + (HERE / "candidate-method.md").read_text(encoding="utf-8"),
        "reader": base_prompts["reader"],
    }
    values = {
        "materials.json": material,
        "grading.json": grading,
        "instructions.json": prompts,
        "tools.json": tool_definitions("one_collection", "single"),
        "tool-sets.json": {
            role: tool_definitions("one_collection", role)
            for role in ("single", "reader")
        },
        "completion-schemas.json": {
            role: completion_schema(role) for role in ("single", "reader")
        },
    }
    for name, value in values.items():
        dump(run_dir / name, value)
    # Inherit the actual dependency closure of the previous experiment, not its budget or results.
    old_manifest = load(SOURCE / "live-01/manifest.json")
    paths = [ROOT / path for path in old_manifest["source_sha256"]]
    paths.extend([*HERE.glob("*.py"), HERE / "candidate-method.md"])
    dump(
        run_dir / "manifest.json",
        {
            "prepared_at": datetime.now(UTC).isoformat(),
            "revision": support.subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
            ).strip(),
            "dirty_workspace": True,
            "implementation": "isolated one-collection workspaces; only maintainer instructions differ",
            "model": previous.public_model_settings(previous.study_model_settings()),
            "budget": {
                "prior_occupied_usd": str(PRIOR),
                "max_additional_usd": str(MAX_USD),
                "max_seconds": MAX_SECONDS,
                "cumulative_limit_usd": "2.00",
            },
            "authorization": "User approved US$0.10 / 20 minutes for this new experiment",
            "source_sha256": {
                path.relative_to(ROOT).as_posix(): hash_file(path) for path in paths
            },
            "artifact_sha256": {name: hash_file(run_dir / name) for name in values},
            "schedule": "3 alternating maintenance pairs from empty; 4 alternating independent reader pairs",
            "scope": "known-counterexample regression, one sample per arm, no compaction",
        },
    )
    print("Prepared frozen paired protocol; no network.", flush=True)


def verify(run_dir: Path) -> None:
    manifest = load(run_dir / "manifest.json")
    for name, expected in manifest["source_sha256"].items():
        if hash_file(ROOT / name) != expected:
            raise ValueError(f"Frozen source changed: {name}")
    for name, expected in manifest["artifact_sha256"].items():
        if hash_file(run_dir / name) != expected:
            raise ValueError(f"Frozen artifact changed: {name}")
    previous = support.load_previous()
    if manifest["model"] != previous.public_model_settings(
        previous.study_model_settings()
    ):
        raise ValueError("Model settings changed")
    if PRIOR + MAX_USD > Decimal("2.00") or manifest["budget"] != {
        "prior_occupied_usd": str(PRIOR),
        "max_additional_usd": str(MAX_USD),
        "max_seconds": MAX_SECONDS,
        "cumulative_limit_usd": "2.00",
    }:
        raise ValueError("Budget boundary changed")


async def run(run_dir: Path) -> None:
    if run_dir.resolve() != FUNDED_DIRECTORY:
        raise ValueError("Only the funded directory may execute paid requests")
    verify(run_dir)
    # Exclusive create prevents accidental concurrent runs or replay of a stopped batch.
    with (run_dir / "started.json").open("x", encoding="utf-8") as marker:
        marker.write('{"status":"started"}\n')
    previous = support.load_previous()
    settings = previous.study_model_settings()
    material, prompts = (
        load(run_dir / "materials.json"),
        load(run_dir / "instructions.json"),
    )
    tools = load(run_dir / "tool-sets.json")
    recorder = previous.Recorder(run_dir)
    recorder.budget.max_usd, recorder.budget.max_seconds = MAX_USD, MAX_SECONDS
    workspaces = {
        arm: Workspace("one_collection", material["messages"]) for arm in ARMS
    }
    snapshots, outcomes = {}, []
    failure, paid_started = None, False

    async def request_hook(request: Any) -> None:
        nonlocal paid_started
        if not paid_started:
            recorder.budget.started = time.monotonic()
            paid_started = True
            recorder.event(
                {
                    "event": "paid_phase_started",
                    "max_usd": str(MAX_USD),
                    "max_seconds": MAX_SECONDS,
                }
            )
        await recorder.request(request)

    try:
        api_key = read_openai_api_key(ROOT / "apps/api/.env")
        async with (
            asyncio.timeout(MAX_SECONDS),
            httpx2.AsyncClient(
                follow_redirects=False,
                event_hooks={
                    "request": [request_hook],
                    "response": [recorder.response],
                },
            ) as transport,
            create_responses_client(
                api_key=api_key,
                timeout_seconds=settings.request_timeout_seconds,
                http_client=transport,
            ) as client,
        ):

            async def episode(
                cell: str, workspace: Workspace, role: str, prompt: str, reference: dict
            ) -> None:
                recorder.cell, recorder.tools = cell, tools[role]
                dump(run_dir / f"context-{cell}.json", reference)
                started = time.monotonic()

                async def send(request: Any) -> Any:
                    wrapped = structured_request(request, role)
                    await count_response_input(client, wrapped)
                    return await create_response(client, wrapped)

                print(f"START {cell}", flush=True)
                result = await run_episode(
                    workspace, role, prompt, reference, settings, send, recorder.event
                )
                result.update(cell=cell, seconds=time.monotonic() - started)
                dump(run_dir / f"result-{cell}.json", result)
                outcomes.append(
                    {
                        "cell": cell,
                        "status": "completed",
                        "steps": result["steps"],
                        "seconds": result["seconds"],
                    }
                )
                dump(run_dir / "progress.json", outcomes)
                print(
                    f"DONE {cell} steps={result['steps']} occupied={recorder.budget.occupied}",
                    flush=True,
                )

            for index, batch in enumerate(material["batches"]):
                for arm in ARMS if index % 2 == 0 else ARMS[::-1]:
                    workspace = workspaces[arm]
                    workspace.read_through = batch["read_through_sequence"]
                    cell = f"{batch['batch_id']}-{arm}"
                    await episode(
                        cell,
                        workspace,
                        "single",
                        prompts[arm],
                        context(workspace, "single", batch),
                    )
                    snapshot = workspace.snapshot()
                    snapshots[arm, batch["batch_id"]] = snapshot
                    dump(run_dir / f"workspace-{cell}.json", snapshot)
            for index, probe in enumerate(material["probes"]):
                for arm in ARMS if index % 2 == 0 else ARMS[::-1]:
                    workspace = Workspace.restore(
                        "one_collection",
                        material["messages"],
                        snapshots[arm, probe["snapshot_batch_id"]],
                    )
                    await episode(
                        f"read-{probe['probe_id']}-{arm}",
                        workspace,
                        "reader",
                        prompts["reader"],
                        reader_context(workspace, probe["question"]),
                    )
    except (Exception, asyncio.CancelledError) as error:  # noqa: BLE001 -- bounded experiment saves and stops, never retries
        failure = {
            "type": type(error).__name__,
            "reason": str(error)
            if isinstance(error, (ValueError, asyncio.CancelledError))
            else "inspect sanitized trace",
            "cell": recorder.cell,
        }
        dump(run_dir / "failure.json", failure)
        print(f"STOP {failure['type']} cell={recorder.cell}", flush=True)
    finally:
        for arm, workspace in workspaces.items():
            dump(run_dir / f"partial-{arm}.json", workspace.snapshot())
        dump(
            run_dir / "run-summary.json",
            {
                "status": "completed" if failure is None else "stopped",
                "outcomes": outcomes,
                "failure": failure,
                "budget": {
                    "occupied_usd": str(recorder.budget.occupied),
                    "prior_occupied_usd": str(PRIOR),
                    "cumulative_occupied_usd": str(PRIOR + recorder.budget.occupied),
                    "pending": recorder.budget.pending,
                    "outbound_calls": recorder.budget.outbound_calls,
                    "elapsed_seconds": time.monotonic() - recorder.budget.started
                    if paid_started
                    else 0,
                },
            },
        )
    if failure is not None:
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("prepare", "verify", "run"))
    parser.add_argument("run_directory", type=Path)
    args = parser.parse_args()
    run_directory = args.run_directory.resolve()
    if run_directory.parent != HERE:
        raise ValueError("Run must be in this experiment package")
    if args.command == "prepare":
        prepare(run_directory)
    elif args.command == "verify":
        verify(run_directory)
        print("Frozen protocol verified; no network.")
    else:
        asyncio.run(run(run_directory))
