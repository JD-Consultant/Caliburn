"""A single bounded comparison of layered Memory and the same original sources."""

import argparse
import asyncio
import importlib.util
import sys
import time
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import httpx2
from admission import claim_run
from caliburn.adapters.openai_credentials import read_openai_api_key
from caliburn.adapters.openai_responses import (
    count_response_input,
    create_response,
    create_responses_client,
)
from layered_protocol import reading_context, run_history_episode

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
SOURCE = HERE.parent / "memory-structure-incremental-2026-10-05"
CONTRACT = HERE.parent / "memory-coherent-units-2026-10-05"
FUNDED_DIRECTORY = HERE / "live-01"
sys.path.insert(0, str(CONTRACT))
from completion_contract import completion_schema, structured_request
from episode import run_episode
from protocol import context
from workspace import SITUATION, Workspace, tool_definitions

spec = importlib.util.spec_from_file_location("layered_support", SOURCE / "study.py")
support = importlib.util.module_from_spec(spec)
spec.loader.exec_module(support)
dump, load, hash_file = support.dump, support.load, support.hash_file
PRIOR = Decimal("1.295271975")
MAX_USD = Decimal("0.10")
MAX_SECONDS = 1200


def budget_contract() -> dict:
    return {
        "prior_occupied_usd": str(PRIOR),
        "max_additional_usd": str(MAX_USD),
        "max_seconds": MAX_SECONDS,
        "cumulative_limit_usd": "2.00",
    }


def prepare(run_dir: Path) -> None:
    previous = support.load_previous()
    run_dir.mkdir(parents=True, exist_ok=False)
    values = {
        "materials.json": load(CONTRACT / "live-01/materials.json"),
        "grading.json": load(CONTRACT / "live-01/grading.json"),
        "instructions.json": {
            role: (HERE / f"{role}-method.md").read_text(encoding="utf-8")
            for role in ("b1", "b2", "reader")
        },
        "tools.json": tool_definitions("two_layer", "b1"),
        "tool-sets.json": {
            **{
                role: tool_definitions("two_layer", role)
                for role in ("b1", "b2", "reader")
            },
            "full_history": [],
        },
        "completion-schemas.json": {
            role: completion_schema("reader" if role == "reader" else "single")
            for role in ("b1", "b2", "reader")
        },
    }
    for name, value in values.items():
        dump(run_dir / name, value)
    old_manifest = load(SOURCE / "live-01/manifest.json")
    paths = [ROOT / path for path in old_manifest["source_sha256"]]
    paths.extend(
        [
            *HERE.glob("*.py"),
            *HERE.glob("*-method.md"),
            HERE / "README.md",
            CONTRACT / "completion_contract.py",
        ]
    )
    dump(
        run_dir / "manifest.json",
        {
            "prepared_at": datetime.now(UTC).isoformat(),
            "revision": support.subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
            ).strip(),
            "dirty_workspace": True,
            "implementation": "isolated two-layer maintenance; same reader with maps or complete visible source",
            "model": previous.public_model_settings(previous.study_model_settings()),
            "budget": budget_contract(),
            "authorization": "User approved US$0.10 / 20 minutes for this new batch",
            "source_sha256": {
                path.relative_to(ROOT).as_posix(): hash_file(path) for path in paths
            },
            "artifact_sha256": {name: hash_file(run_dir / name) for name in values},
            "schedule": "3 sequential B1/B2 pairs; 4 alternating independent layered/full-history reader pairs",
            "scope": "known-counterexample regression, one sample per arm, no compaction",
        },
    )
    print("Prepared; no network.", flush=True)


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
    if PRIOR + MAX_USD > Decimal("2.00") or manifest["budget"] != budget_contract():
        raise ValueError("Budget boundary changed")


async def run(run_dir: Path) -> None:
    if run_dir.resolve() != FUNDED_DIRECTORY:
        raise ValueError("Only the funded directory may execute paid requests")
    verify(run_dir)
    claim_run(run_dir, FUNDED_DIRECTORY)
    previous = support.load_previous()
    settings = previous.study_model_settings()
    material = load(run_dir / "materials.json")
    prompts = load(run_dir / "instructions.json")
    tools = load(run_dir / "tool-sets.json")
    recorder = previous.Recorder(run_dir)
    recorder.budget.max_usd, recorder.budget.max_seconds = MAX_USD, MAX_SECONDS
    workspace = Workspace("two_layer", material["messages"])
    snapshots, outcomes = {}, []
    failure, paid_started = None, False

    async def request_hook(request) -> None:
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
                cell: str,
                current: Workspace,
                role: str,
                reference: dict,
                *,
                history: bool = False,
            ) -> None:
                recorder.cell = cell
                recorder.tools = tools["full_history" if history else role]
                dump(run_dir / f"context-{cell}.json", reference)
                started = time.monotonic()

                async def send(request):
                    wrapped = structured_request(
                        request, "reader" if role == "reader" else "single"
                    )
                    await count_response_input(client, wrapped)
                    return await create_response(client, wrapped)

                print(f"START {cell}", flush=True)
                if history:
                    result = await run_history_episode(
                        current, prompts[role], reference, settings, send
                    )
                else:
                    result = await run_episode(
                        current,
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

            for batch in material["batches"]:
                before = workspace.views(SITUATION)
                workspace.read_through = batch["read_through_sequence"]
                for role in ("b1", "b2"):
                    cell = f"{batch['batch_id']}-{role}"
                    await episode(
                        cell, workspace, role, context(workspace, role, batch, before)
                    )
                    dump(run_dir / f"workspace-{cell}.json", workspace.snapshot())
                snapshots[batch["batch_id"]] = workspace.snapshot()
            for index, probe in enumerate(material["probes"]):
                arms = (
                    ("layered", "full_history")
                    if index % 2 == 0
                    else ("full_history", "layered")
                )
                for arm in arms:
                    current = Workspace.restore(
                        "two_layer",
                        material["messages"],
                        snapshots[probe["snapshot_batch_id"]],
                    )
                    if arm == "full_history":
                        current.objects.clear()
                    await episode(
                        f"read-{probe['probe_id']}-{arm}",
                        current,
                        "reader",
                        reading_context(current, probe["question"], arm=arm),
                        history=arm == "full_history",
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
        dump(run_dir / "partial-layered.json", workspace.snapshot())
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
    directory = args.run_directory.resolve()
    if directory.parent != HERE:
        raise ValueError("Run must be in this experiment package")
    if args.command == "prepare":
        prepare(directory)
    elif args.command == "verify":
        verify(directory)
        print("Frozen protocol verified; no network.")
    else:
        asyncio.run(run(directory))
