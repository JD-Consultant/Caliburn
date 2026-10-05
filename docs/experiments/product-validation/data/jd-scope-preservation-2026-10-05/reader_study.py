"""Fixed-Memory paired reader experiment; no production writes or maintenance."""

import argparse
import asyncio
import sys
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

HERE = Path(__file__).resolve().parent
FUNDED_DIRECTORY = HERE / "live-01"
COHERENT = HERE.parent / "memory-coherent-units-2026-10-05"
sys.path.insert(0, str(COHERENT))
import coherent_study as reused

ROOT = reused.ROOT
load, dump, hash_file = reused.load, reused.dump, reused.hash_file
PRIOR = Decimal("1.285104650")
MAX_USD, MAX_SECONDS = Decimal("0.05"), 900
ARMS = ("baseline", "scoped")


def schedule(cases: list[dict]) -> list[tuple[str, dict, str]]:
    pairs = [(case, 1) for case in cases]
    pairs.extend(
        (case, 2)
        for case in cases
        if case["probe_id"] in ("post_delivery", "maintenance")
    )
    return [
        (f"read-{case['probe_id']}-r{repeat}-{arm}", case, arm)
        for index, (case, repeat) in enumerate(pairs)
        for arm in (ARMS if index % 2 == 0 else ARMS[::-1])
    ]


def prepare(run_dir: Path) -> None:
    old_run = COHERENT / "live-01"
    reused.verify(old_run)
    run_dir.mkdir(parents=True, exist_ok=False)
    previous = reused.support.load_previous()
    material = load(old_run / "materials.json")
    narrow = load(HERE / "narrow-cases.json")
    cases = material["probes"] + [
        {key: case[key] for key in ("probe_id", "snapshot_batch_id", "question")}
        for case in narrow["probes"]
    ]
    baseline = load(old_run / "instructions.json")["reader"]
    values = {
        "materials.json": material,
        "cases.json": cases,
        "grading.json": {
            "regression": load(old_run / "grading.json"),
            "narrow": narrow,
        },
        "instructions.json": {
            "baseline": baseline,
            "scoped": baseline
            + "\n\n"
            + (HERE / "scope-method.md").read_text(encoding="utf-8"),
        },
        "tools.json": reused.tool_definitions("one_collection", "reader"),
        "completion-schema.json": reused.completion_schema("reader"),
        **{
            f"workspace-{batch}.json": load(
                old_run / f"workspace-{batch}-coherent.json"
            )
            for batch in ("corrections", "extension")
        },
    }
    for name, value in values.items():
        dump(run_dir / name, value)
    paths = [ROOT / name for name in load(old_run / "manifest.json")["source_sha256"]]
    paths.extend(
        [*HERE.glob("*.py"), HERE / "scope-method.md", HERE / "narrow-cases.json"]
    )
    paths.extend(
        old_run / name
        for name in (
            "materials.json",
            "grading.json",
            "instructions.json",
            "workspace-corrections-coherent.json",
            "workspace-extension-coherent.json",
        )
    )
    dump(
        run_dir / "manifest.json",
        {
            "prepared_at": datetime.now(UTC).isoformat(),
            "revision": reused.support.subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
            ).strip(),
            "dirty_workspace": True,
            "model": previous.public_model_settings(previous.study_model_settings()),
            "budget": {
                "prior_occupied_usd": str(PRIOR),
                "max_additional_usd": str(MAX_USD),
                "max_seconds": MAX_SECONDS,
                "cumulative_limit_usd": "2.00",
            },
            "authorization": "User approved US$0.05 / 15 minutes for this fixed-Memory reader experiment",
            "source_sha256": {
                path.relative_to(ROOT).as_posix(): hash_file(path) for path in paths
            },
            "artifact_sha256": {name: hash_file(run_dir / name) for name in values},
            "schedule": [cell for cell, _, _ in schedule(cases)],
            "scope": "reader prompt only; same model-generated Memory; known-case regression; no compaction, no production changes",
        },
    )
    print("Prepared fixed-Memory reader comparison; no network.", flush=True)


def verify(run_dir: Path) -> None:
    manifest = load(run_dir / "manifest.json")
    for field, base in (("source_sha256", ROOT), ("artifact_sha256", run_dir)):
        for name, expected in manifest[field].items():
            if hash_file(base / name) != expected:
                raise ValueError(
                    f"Frozen {'source' if base == ROOT else 'artifact'} changed: {name}"
                )
    previous = reused.support.load_previous()
    if manifest["model"] != previous.public_model_settings(
        previous.study_model_settings()
    ):
        raise ValueError("Model settings changed")
    if manifest["budget"] != {
        "prior_occupied_usd": str(PRIOR),
        "max_additional_usd": str(MAX_USD),
        "max_seconds": MAX_SECONDS,
        "cumulative_limit_usd": "2.00",
    } or PRIOR + MAX_USD > Decimal("2.00"):
        raise ValueError("Budget boundary changed")
    if manifest["schedule"] != [
        cell for cell, _, _ in schedule(load(run_dir / "cases.json"))
    ]:
        raise ValueError("Schedule changed")


def reader_input(run_dir: Path, probe: dict) -> tuple[reused.Workspace, dict]:
    material = load(run_dir / "materials.json")
    snapshot = load(run_dir / f"workspace-{probe['snapshot_batch_id']}.json")
    workspace = reused.Workspace.restore(
        "one_collection", material["messages"], snapshot
    )
    return workspace, reused.reader_context(workspace, probe["question"])


async def run(run_dir: Path) -> None:
    if run_dir.resolve() != FUNDED_DIRECTORY:
        raise ValueError("Only the funded directory may execute paid requests")
    verify(run_dir)
    with (run_dir / "started.json").open("x", encoding="utf-8") as marker:
        marker.write('{"status":"started"}\n')
    previous = reused.support.load_previous()
    settings = previous.study_model_settings()
    prompts = load(run_dir / "instructions.json")
    recorder = previous.Recorder(run_dir)
    recorder.budget.max_usd, recorder.budget.max_seconds = MAX_USD, MAX_SECONDS
    outcomes, failure, paid_started = [], None, False

    async def request_hook(request):
        nonlocal paid_started
        if not paid_started:
            recorder.budget.started, paid_started = time.monotonic(), True
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

            async def send(request):
                wrapped = reused.structured_request(request, "reader")
                await count_response_input(client, wrapped)
                return await create_response(client, wrapped)

            for cell, probe, arm in schedule(load(run_dir / "cases.json")):
                recorder.cell = cell
                workspace, context = reader_input(run_dir, probe)
                before = workspace.snapshot()
                dump(run_dir / f"context-{cell}.json", context)
                started = time.monotonic()
                print(f"START {cell}", flush=True)
                result = await reused.run_episode(
                    workspace,
                    "reader",
                    prompts[arm],
                    context,
                    settings,
                    send,
                    recorder.event,
                )
                if workspace.snapshot() != before:
                    raise ValueError("Reader changed fixed Memory")
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
    except (Exception, asyncio.CancelledError) as error:  # noqa: BLE001 -- record bounded failure, never retry
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
    args = parser.parse_args()
    if args.command == "prepare":
        prepare(FUNDED_DIRECTORY)
    elif args.command == "verify":
        verify(FUNDED_DIRECTORY)
        print("Frozen protocol verified; no network.")
    else:
        asyncio.run(run(FUNDED_DIRECTORY))
