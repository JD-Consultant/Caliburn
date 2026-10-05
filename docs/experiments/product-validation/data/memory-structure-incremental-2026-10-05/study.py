"""Bounded scheme comparison; no database, production mutation, or automatic reruns."""

import argparse
import asyncio
import hashlib
import importlib.util
import json
import subprocess
import time
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import httpx2
from caliburn.adapters.openai_credentials import read_openai_api_key
from caliburn.adapters.openai_responses import (
    count_response_input,
    create_response,
    create_responses_client,
)
from episode import run_episode
from protocol import context, instructions, reader_context
from workspace import SITUATION, Workspace, tool_definitions

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
PREVIOUS = HERE.parent / "memory-organization-2026-10-05/study.py"
PRIOR = Decimal("1.253991040")
MAX_USD = Decimal("0.10")
MAX_SECONDS = 1200
ARMS = ("two_layer", "one_collection")
ROLES = {"two_layer": ("b1", "b2", "reader"), "one_collection": ("single", "reader")}


def load_previous():
    spec = importlib.util.spec_from_file_location("structure_previous", PREVIOUS)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def dump(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def frozen_tools() -> dict:
    return {
        f"{arm}/{role}": tool_definitions(arm, role)
        for arm in ARMS
        for role in ROLES[arm]
    }


def prepare(run_dir: Path) -> None:
    previous = load_previous()
    run_dir.mkdir(parents=True, exist_ok=False)
    for name in ("materials.json", "grading.json"):
        dump(run_dir / name, load(HERE / name))
    dump(run_dir / "instructions.json", instructions())
    dump(run_dir / "tool-sets.json", frozen_tools())
    # Recorder's initial value; each episode switches to its already-frozen role contract.
    dump(run_dir / "tools.json", tool_definitions("two_layer", "b1"))
    dependencies = [
        PREVIOUS,
        HERE.parent / "memory-compaction-publish-2026-10-04/experiment.py",
        HERE.parent / "design-comparisons-2026-10-04/provider_observations.py",
    ]
    for folder in ("adapters", "features/work_memory", "transport/model_tools"):
        dependencies.extend((ROOT / "apps/api/src/caliburn" / folder).glob("*.py"))
    dependencies.append(ROOT / "apps/api/src/caliburn/settings.py")
    dependencies.extend((ROOT / "apps/api/contracts/tools").glob("*.json"))
    sources = [
        *HERE.glob("*.py"),
        HERE / "maintenance-method.md",
        HERE / "reader-method.md",
        *dependencies,
    ]
    hashes = {
        str(path.relative_to(ROOT)).replace("\\", "/"): hash_file(path)
        for path in sources
    }
    artifacts = {path.name: hash_file(path) for path in run_dir.glob("*.json")}
    dump(
        run_dir / "manifest.json",
        {
            "status": "prepared",
            "prepared_at": datetime.now(UTC).isoformat(),
            "revision": subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
            ).strip(),
            "dirty_workspace": True,
            "implementation": "isolated local workspace, production wire schemas/body editor/Responses adapter",
            "model": previous.public_model_settings(previous.study_model_settings()),
            "budget": {
                "prior_occupied_usd": str(PRIOR),
                "max_additional_usd": str(MAX_USD),
                "max_seconds": MAX_SECONDS,
                "cumulative_limit_usd": "2.00",
                "authorization": "User approved US$0.10 / 20 minutes in this chat",
            },
            "schedule": [
                "initial:two_layer,one_collection",
                "corrections:one_collection,two_layer",
                "extension:two_layer,one_collection",
                "read:post_delivery,maintenance,infrequent_work",
            ],
            "source_sha256": hashes,
            "artifact_sha256": artifacts,
        },
    )
    print(
        "Prepared frozen materials, instructions, tool sets and code hashes; no network.",
        flush=True,
    )


def verify(run_dir: Path, previous) -> dict:
    manifest = load(run_dir / "manifest.json")
    for name, expected in manifest["source_sha256"].items():
        if hash_file(ROOT / name) != expected:
            raise ValueError(f"Frozen source changed: {name}")
    for name, expected in manifest["artifact_sha256"].items():
        if hash_file(run_dir / name) != expected:
            raise ValueError(f"Frozen artifact changed: {name}")
    if manifest["model"] != previous.public_model_settings(
        previous.study_model_settings()
    ):
        raise ValueError("Model configuration changed")
    if load(run_dir / "tool-sets.json") != frozen_tools():
        raise ValueError("Tool contract changed")
    if PRIOR + MAX_USD > Decimal(2):
        raise ValueError("Cumulative authorization exceeded")
    return manifest


async def run(run_dir: Path) -> None:
    previous = load_previous()
    verify(run_dir, previous)
    if (run_dir / "started.json").exists():
        raise ValueError("Run already started; do not rerun")
    material, prompts = (
        load(run_dir / "materials.json"),
        load(run_dir / "instructions.json"),
    )
    tools = load(run_dir / "tool-sets.json")
    settings = previous.study_model_settings()
    api_key = read_openai_api_key(ROOT / "apps/api/.env")
    recorder = previous.Recorder(run_dir)
    recorder.budget.max_usd = MAX_USD
    recorder.budget.max_seconds = MAX_SECONDS
    workspaces = {arm: Workspace(arm, material["messages"]) for arm in ARMS}
    snapshots = {}
    outcomes = []
    failure = None
    paid_started = False

    async def request_hook(request):
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

    dump(
        run_dir / "started.json",
        {
            "at": datetime.now(UTC).isoformat(),
            "note": "exclusive run marker, not a completion",
        },
    )
    try:
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

            async def send(request):
                await count_response_input(client, request)
                return await create_response(client, request)

            async def episode(
                cell: str, workspace: Workspace, role: str, reference: dict
            ) -> None:
                recorder.cell = cell
                recorder.tools = tools[f"{workspace.arm}/{role}"]
                dump(run_dir / f"context-{cell}.json", reference)
                started = time.monotonic()
                print(f"START {cell}", flush=True)
                result = await run_episode(
                    workspace,
                    role,
                    prompts[role],
                    reference,
                    settings,
                    send,
                    recorder.event,
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
                order = ARMS if index % 2 == 0 else ARMS[::-1]
                for arm in order:
                    workspace = workspaces[arm]
                    workspace.read_through = batch["read_through_sequence"]
                    before = workspace.views(SITUATION)
                    roles = ("b1", "b2") if arm == "two_layer" else ("single",)
                    for role in roles:
                        cell = f"{batch['batch_id']}-{arm}-{role}"
                        await episode(
                            cell,
                            workspace,
                            role,
                            context(workspace, role, batch, before),
                        )
                        dump(run_dir / f"workspace-{cell}.json", workspace.snapshot())
                    snapshots[arm, batch["batch_id"]] = workspace.snapshot()
            for index, probe in enumerate(material["probes"]):
                for arm in ARMS if index % 2 == 0 else ARMS[::-1]:
                    workspace = Workspace.restore(
                        arm,
                        material["messages"],
                        snapshots[arm, probe["snapshot_batch_id"]],
                    )
                    cell = f"read-{probe['probe_id']}-{arm}"
                    await episode(
                        cell,
                        workspace,
                        "reader",
                        reader_context(workspace, probe["question"]),
                    )
    except (Exception, asyncio.CancelledError) as error:  # noqa: BLE001 -- outer experiment boundary saves failure and stops
        # Unknown provider failures keep reservations; do not retry or print secrets.
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
        raise ValueError("Run directory must be inside this experiment package")
    if args.command == "prepare":
        prepare(run_directory)
    elif args.command == "verify":
        verify(run_directory, load_previous())
        print("Frozen contract verified; no network.")
    else:
        asyncio.run(run(run_directory))
