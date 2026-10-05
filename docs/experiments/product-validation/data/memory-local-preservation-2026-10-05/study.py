"""One bounded paired prompt verification; reuse the existing episode and guard."""

import argparse
import asyncio
import sys
import time
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import httpx2
from cases import PREVIOUS, build_cases
from prompt_changes import instructions

sys.path.insert(0, str(PREVIOUS))
import layered_study as baseline
from admission import claim_run
from caliburn.adapters.openai_credentials import read_openai_api_key
from caliburn.adapters.openai_responses import (
    count_response_input,
    create_response,
    create_responses_client,
)
from completion_contract import structured_request
from episode import run_episode
from workspace import Workspace, tool_definitions

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
FUNDED = HERE / "live-01"
PRIOR = Decimal("1.311735480")
LIMIT = Decimal("0.05")
SECONDS = 900
dump, load, hash_file = baseline.dump, baseline.load, baseline.hash_file


def prepare(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=False)
    cases = []
    for case in build_cases():
        cases.append(
            {
                "id": case["id"],
                "role": case["role"],
                "snapshot": case["workspace"].snapshot(),
                "messages": list(case["workspace"].messages.values()),
                "context": case["context"],
            }
        )
    frozen_tools = load(PREVIOUS / "live-01/tool-sets.json")
    current_tools = {
        role: tool_definitions("two_layer", role) for role in ("b2", "reader")
    }
    if any(current_tools[role] != frozen_tools[role] for role in current_tools):
        raise ValueError("Historical tool contract changed")
    artifacts = {
        "cases.json": cases,
        "instructions.json": instructions(PREVIOUS),
        "tool-sets.json": current_tools,
        "tools.json": current_tools["b2"],
    }
    for name, value in artifacts.items():
        dump(directory / name, value)
    # Freeze reused dependencies at the new batch's start, plus historical inputs.
    sources = {
        ROOT / name
        for name in load(PREVIOUS / "live-01/manifest.json")["source_sha256"]
    }
    sources.update(HERE.glob("*.py"))
    sources.add(HERE / "README.md")
    sources.update(PREVIOUS.glob("*-method.md"))
    sources.update(PREVIOUS.glob("live-01/workspace-*.json"))
    sources.add(PREVIOUS / "live-01/materials.json")
    provider = baseline.support.load_previous()
    dump(
        directory / "manifest.json",
        {
            "prepared_at": datetime.now(UTC).isoformat(),
            "model": provider.public_model_settings(provider.study_model_settings()),
            "budget": {
                "prior_occupied_usd": str(PRIOR),
                "max_additional_usd": str(LIMIT),
                "max_seconds": SECONDS,
                "cumulative_limit_usd": "2",
            },
            "authorization": "User approved US$0.05 / 15 minutes for this batch on 2026-10-05",
            "schedule": "five paired cases, one attempt per arm; alternating control/candidate order",
            "source_sha256": {
                path.relative_to(ROOT).as_posix(): hash_file(path)
                for path in sorted(sources)
            },
            "artifact_sha256": {
                name: hash_file(directory / name) for name in artifacts
            },
        },
    )


def verify(directory: Path) -> None:
    manifest = load(directory / "manifest.json")
    for name, expected in manifest["source_sha256"].items():
        if hash_file(ROOT / name) != expected:
            raise ValueError(f"Frozen source changed: {name}")
    for name, expected in manifest["artifact_sha256"].items():
        if hash_file(directory / name) != expected:
            raise ValueError(f"Frozen input changed: {name}")
    if PRIOR + LIMIT > Decimal(2):
        raise ValueError("Cumulative boundary exceeded")
    provider = baseline.support.load_previous()
    if manifest["model"] != provider.public_model_settings(
        provider.study_model_settings()
    ):
        raise ValueError("Model settings changed")


async def run(directory: Path) -> None:
    if directory.resolve() != FUNDED:
        raise ValueError("Only the funded directory may execute paid requests")
    verify(directory)
    claim_run(directory, FUNDED)
    provider = baseline.support.load_previous()
    settings = provider.study_model_settings()
    recorder = provider.Recorder(directory)
    recorder.budget.max_usd, recorder.budget.max_seconds = LIMIT, SECONDS
    prompts, tools = (
        load(directory / "instructions.json"),
        load(directory / "tool-sets.json"),
    )
    paid_started, failure, outcomes = False, None, []

    async def request_hook(request) -> None:
        nonlocal paid_started
        if not paid_started:
            recorder.budget.started = time.monotonic()
            paid_started = True
            recorder.event(
                {
                    "event": "paid_phase_started",
                    "max_usd": str(LIMIT),
                    "max_seconds": SECONDS,
                }
            )
        await recorder.request(request)

    try:
        async with (
            asyncio.timeout(SECONDS),
            httpx2.AsyncClient(
                follow_redirects=False,
                event_hooks={
                    "request": [request_hook],
                    "response": [recorder.response],
                },
            ) as transport,
            create_responses_client(
                api_key=read_openai_api_key(ROOT / "apps/api/.env"),
                timeout_seconds=settings.request_timeout_seconds,
                http_client=transport,
            ) as client,
        ):
            for index, case in enumerate(load(directory / "cases.json")):
                arms = (
                    ("control", "candidate")
                    if index % 2 == 0
                    else ("candidate", "control")
                )
                for arm in arms:
                    role, cell = case["role"], f"{case['id']}-{arm}"
                    current = Workspace.restore(
                        "two_layer", case["messages"], case["snapshot"]
                    )
                    recorder.cell, recorder.tools = cell, tools[role]
                    dump(directory / f"context-{cell}.json", case["context"])

                    async def send(request, role=role):
                        wrapped = structured_request(
                            request, "reader" if role == "reader" else "single"
                        )
                        await count_response_input(client, wrapped)
                        return await create_response(client, wrapped)

                    print(f"START {cell}", flush=True)
                    result = await run_episode(
                        current,
                        role,
                        prompts[role][arm],
                        case["context"],
                        settings,
                        send,
                        recorder.event,
                    )
                    dump(directory / f"result-{cell}.json", result)
                    dump(directory / f"workspace-{cell}.json", current.snapshot())
                    outcomes.append(
                        {"cell": cell, "steps": result["steps"], "status": "completed"}
                    )
                    dump(directory / "progress.json", outcomes)
                    print(
                        f"DONE {cell} steps={result['steps']} occupied={recorder.budget.occupied}",
                        flush=True,
                    )
    except (Exception, asyncio.CancelledError) as error:  # noqa: BLE001 -- preserve partial experiment and stop; never retry
        failure = {"type": type(error).__name__, "cell": recorder.cell}
        if isinstance(error, ValueError):
            failure["reason"] = str(error)
        dump(directory / "failure.json", failure)
        print(f"STOP {failure}", flush=True)
    finally:
        dump(
            directory / "run-summary.json",
            {
                "status": "stopped" if failure else "completed",
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
    if failure:
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("prepare", "verify", "run"))
    args = parser.parse_args()
    if args.command == "run":
        asyncio.run(run(FUNDED))
    else:
        {"prepare": prepare, "verify": verify}[args.command](FUNDED)
        print(f"{args.command}: complete; no network")
