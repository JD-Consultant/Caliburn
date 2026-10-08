"""Compose the predecessor runner with new frozen materials and an accumulated guard.

--dry-run is strictly zero-key, zero-database and zero-provider. Pilot and formal
share one research directory and one ledger; no old-case reuse or automatic replay.
"""

import argparse
import asyncio
import json
import os
import re
import sys
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).resolve().parent
OLD = HERE.with_name("interview-plan-comparison-2026-10-07")
sys.path.insert(0, str(OLD))
import guard as legacy_guard
import run_batch as legacy
from append_stream import OwnedObservedStream

sys.path.insert(0, str(HERE))
import journey as new_journey
from carry import load_carry, seed_guard
from controls import BatchGuard
from frozen_manifest import (
    FORMAL,
    LIMITS,
    PILOT,
    PLAN_GATE,
    arm_templates,
    database_locator,
    freeze,
    sha,
    verify,
)
from materials import PROFILES, Employee
from observers import bind_case_observers


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def guard_from_ledger(directory, frozen):
    limits = frozen["limits"]
    guard = BatchGuard(
        limit=Decimal(limits["limit_usd"]),
        **{
            key: limits[key]
            for key in [
                "max_generations",
                "max_compacts",
                "max_outbound",
                "max_counted_input",
            ]
        },
        verify_frozen=lambda: verify(frozen),
    )
    path = directory / "ledger.json"
    if not path.exists() and (
        any(directory.glob("*/*/provider-trace.jsonl"))
        or any(directory.glob("*/*/case.json"))
    ):
        raise RuntimeError(
            "Accumulated ledger is missing despite prior case originals; no reset to zero"
        )
    if not path.exists() and frozen.get("carry"):
        seed_guard(guard, frozen["carry"]["final_guard"])
    if path.exists():
        ledger = read(path)
        state = ledger["guard"]
        if state["stop_reason"] or state["retained_reservations"]:
            raise RuntimeError("Prior stopped or unknown accounting cannot be reset")
        if ledger.get("manifest_sha256") != sha(directory / "manifest.json"):
            raise RuntimeError(
                "Prior ledger belongs to a different frozen research manifest"
            )
        for relative, expected in ledger.get("artifact_sha256", {}).items():
            original = directory / relative
            if (
                not original.resolve().is_relative_to(directory.resolve())
                or sha(original) != expected
            ):
                raise RuntimeError("Prior accounting original changed")
        traces = sorted(
            directory.glob("*/*/provider-trace.jsonl"),
            key=lambda item: item.stat().st_mtime_ns,
        )
        if not traces or not ledger.get("artifact_sha256"):
            raise RuntimeError("Prior ledger has no provider accounting originals")
        last = json.loads(traces[-1].read_text(encoding="utf-8").splitlines()[-1])
        for key in [
            "spent_usd",
            "occupied_usd",
            "generations",
            "compacts",
            "outbound",
            "counted_input",
        ]:
            if last.get(key) != state[key]:
                raise RuntimeError(
                    "Prior ledger does not match its last accounting witness"
                )
        guard.spent = Decimal(state["spent_usd"])
        guard.attempts = {
            key: Decimal(value) for key, value in state["retained_reservations"].items()
        }
        if guard.occupied != Decimal(state["occupied_usd"]):
            raise RuntimeError("Prior accounting occupancy does not match")
        for key in ["generations", "compacts", "outbound", "counted_input"]:
            setattr(guard, key, state[key])
    guard.templates = frozen["arm_templates"]
    return guard


def save_ledger(directory, phase, processed, guard, schedule):
    originals = [
        *directory.glob("*/*/provider-trace.jsonl"),
        *directory.glob("*/*/result.json"),
        *directory.glob("*/*/failure.json"),
    ]
    legacy.save(
        directory / "ledger.json",
        {
            "phase": phase,
            "processed": processed,
            "scheduled": schedule,
            "guard": guard.state(),
            "manifest_sha256": sha(directory / "manifest.json"),
            "artifact_sha256": {
                path.relative_to(directory).as_posix(): sha(path) for path in originals
            },
        },
    )


def plan_tool_audit(case):
    trace = [
        json.loads(line)
        for line in (case / "provider-trace.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    calls = {}
    for row in trace:
        for item in [*row.get("input", []), *row.get("output", [])]:
            if item.get("type") == "function_call":
                calls[item.get("call_id")] = item.get("name")
    result = {"updated": {}, "rejected": {}}
    for row in trace:
        if row.get("event") != "admitted" or row.get("role") != "A":
            continue
        for item in row.get("input", []):
            name = calls.get(item.get("call_id"))
            if item.get("type") != "function_call_output" or name not in {
                "read_interview_plan",
                "edit_interview_plan",
            }:
                continue
            output = item.get("output")
            try:
                output = json.loads(output) if isinstance(output, str) else output
            except ValueError:
                continue
            if not isinstance(output, dict):
                continue
            status = output.get("status")
            if (
                status == "rejected"
                or name == "edit_interview_plan"
                and status == "updated"
            ):
                result[status][item["call_id"]] = {"tool": name, "output": output}
    # Classify only explicit production-contract input corrections. All originals
    # remain in rejected; a later update does not erase or semantically repair them.
    result["recoverable_rejected"] = {
        call_id: item
        for call_id, item in result["rejected"].items()
        if item["output"].get("code") in PLAN_GATE["recoverable_codes"][item["tool"]]
    }
    result["fatal_rejected"] = {
        call_id: item
        for call_id, item in result["rejected"].items()
        if call_id not in result["recoverable_rejected"]
    }
    return result


def pilot_gate(directory):
    """Require real mechanism originals, never infer usability from a process exit."""
    root = directory / "pilot"
    for profile, group, repeat in PILOT:
        case = root / f"{profile}-r{repeat}-{group}"
        result = read(case / "result.json")
        if result["guard"]["stop_reason"] or any(
            turn["status"] != "completed" for turn in result["turns"]
        ):
            raise RuntimeError("Pilot did not complete cleanly")
        if result["memory_settlement"].get("observation_timeout") or any(
            result["memory_settlement"].get(status, 0)
            for status in ["failed", "cancelled", "paused"]
        ):
            raise RuntimeError("Pilot Memory settlement is incomplete")
        if group == "P2":
            plan = read(case / "formal-plan.json")
            if not isinstance(plan.get("plan"), str) or not plan["plan"].strip():
                raise RuntimeError("Pilot P2 did not create a formal nonempty Plan")
            tool_audit = plan_tool_audit(case)
            successful, failures = tool_audit["updated"], tool_audit["fatal_rejected"]
            if failures or len(successful) < 2:
                raise RuntimeError(
                    "Pilot lacks successful Plan read/edit and subsequent-use originals"
                )
            # A semantic mechanism reviewer must lock the actual creation and local patch evidence.
            receipt = read(root / "mechanism-review.json")
            if (
                receipt.get("passed") is not True
                or not receipt.get("plan_created_verified")
                or not receipt.get("plan_formal_readback_verified")
                or not receipt.get("plan_local_patch_verified")
                or not receipt.get("plan_next_turn_use_verified")
            ):
                raise RuntimeError(
                    "Pilot mechanism review did not verify Plan patch and next-turn use"
                )
            for relative, expected in receipt.get("artifact_sha256", {}).items():
                path = root / relative
                if (
                    not path.resolve().is_relative_to(root.resolve())
                    or sha(path) != expected
                ):
                    raise RuntimeError("Pilot reviewed originals changed")
            if not receipt.get("artifact_sha256"):
                raise RuntimeError("Pilot semantic review has no fixed originals")


def write_blind_bundle(case, destination, mapping):
    opaque = legacy.write_blind_bundle(case, destination, mapping)
    path = destination / (opaque + ".json")
    bundle = read(path)
    event = read(case / "manual-edit.json")
    bundle["public_manual_edit"] = {
        key: event[key]
        for key in ["status", "public_initial", "required_text", "diff"]
        if key in event
    }
    legacy.save(path, bundle)


async def run_case(phase, profile, group, repeat, case, guard, frozen):
    """Keep original official HTTP/PG/client construction and restore all seams."""
    original = {
        key: getattr(legacy, key)
        for key in [
            "HERE",
            "Employee",
            "PROFILES",
            "journey",
            "verify",
            "GuardedTransport",
            "ObservedSaver",
        ]
    }
    stream = legacy_guard.ObservedStream
    legacy.HERE = HERE
    legacy.Employee, legacy.PROFILES = Employee, PROFILES
    legacy.journey, legacy.verify = new_journey.journey, verify
    legacy_guard.ObservedStream = OwnedObservedStream
    guard.group = group
    bind_case_observers(legacy, guard, case)
    try:
        # The phase prefix creates a fresh distinct intplan_jdwork_* schema; it
        # also prevents predecessor formal code from writing its old blind paths.
        await legacy.run_case(
            "jdwork_" + phase,
            profile,
            group,
            repeat,
            case,
            guard,
            frozen,
            frozen["turn_limits"][phase],
        )
        result = read(case / "result.json")
        if (
            any(turn["status"] != "completed" for turn in result["turns"])
            or result["memory_settlement"].get("observation_timeout")
            or any(
                result["memory_settlement"].get(status, 0)
                for status in ["failed", "cancelled", "paused"]
            )
        ):
            guard.stop_reason = (
                "Incomplete Turn or Memory settlement; diagnose before another case"
            )
        tool_audit = plan_tool_audit(case)
        legacy.save(case / "plan-tool-audit.json", tool_audit)
        if tool_audit["fatal_rejected"]:
            guard.stop_reason = "Plan tool rejection; diagnose before another paid case"
        if group == "P2" and not any(
            isinstance(read(path)["plan"].get("plan"), str)
            and read(path)["plan"]["plan"].strip()
            for path in case.glob("turn-*-result.json")
        ):
            guard.stop_reason = "P2 has no formally adopted nonempty Plan; diagnose mechanism before comparison"
        if phase == "formal":
            write_blind_bundle(
                case,
                case.parent.parent / "blind-input",
                case.parent.parent / "blind-map.json",
            )
    finally:
        for key, value in original.items():
            setattr(legacy, key, value)
        legacy_guard.ObservedStream = stream


async def database_preflight(database_url):
    """Root-run zero-key official HTTP/PG preflight in a fresh isolated schema."""
    from uuid import uuid4

    import httpx2
    from caliburn.adapters.database_settings import DatabaseSettings
    from caliburn.settings import Settings
    from events import manual_command, manual_pending

    legacy.DSN = database_url
    schema = "intplan_jdwork_preflight_" + uuid4().hex[:8]
    await legacy.migrate(schema)
    app = legacy.bootstrap.create_app(
        Settings(
            database=DatabaseSettings(url=database_url, schema=schema),
            dev_origin=legacy.BASE,
        )
    )
    async with (
        app.router.lifespan_context(app),
        httpx2.AsyncClient(
            transport=httpx2.ASGITransport(app=app),
            base_url=legacy.BASE,
            headers={"Origin": legacy.BASE},
            trust_env=False,
        ) as client,
    ):
        response = await client.post(
            "/api/job-files",
            json={
                "command_id": str(uuid4()),
                "display_name": "合成工作計畫預檢",
                "employee_name": "合成預檢",
            },
        )
        response.raise_for_status()
        path = "/api/job-files/" + response.json()["job_file_id"]
        for suffix in [
            "/jd/profile",
            "/jd/work",
            "/jd/sources",
            "/interviews",
            "/interview-plan",
        ]:
            (await client.get(path + suffix)).raise_for_status()
        before = (await client.get(path + "/jd/work")).json()
        pending = manual_pending("warehouse", before, uuid4().hex)
        command = manual_command(
            pending,
            {
                "question_id": pending["question_id"],
                "action": "create_task",
                "title": "收貨差異處理",
                "description": pending["required_text"],
                "reason": "只按凍結的初始公開文字做零key預檢",
            },
        )
        response = await client.post(path + "/jd/tasks", json=command)
        response.raise_for_status()
        after = (await client.get(path + "/jd/work")).json()
        if (
            after["revision_id"] != response.json()["revision_id"]
            or len(after["tasks"]) != 1
        ):
            raise RuntimeError("Official manual-write/read-back preflight failed")
    receipt = {
        "schema": schema,
        "database": database_locator(database_url),
        "credential_read": False,
        "provider_calls": 0,
        "manual_official_http_saved_and_read_back": True,
    }
    legacy.save(HERE / "database-preflight.json", receipt)
    print(json.dumps(receipt))


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["pilot", "formal"])
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--batch-name", default="comparison-v1")
    parser.add_argument("--freeze-only", action="store_true")
    parser.add_argument("--database-dry-run", action="store_true")
    parser.add_argument("--limit-usd")
    parser.add_argument("--authorization-reference")
    parser.add_argument("--carry-from")
    parser.add_argument(
        "--database-url", default=os.environ.get("CALIBURN_JDWORK_TEST_DSN")
    )
    args = parser.parse_args()
    if re.fullmatch(r"[a-z][a-z0-9_-]{0,60}", args.batch_name) is None:
        raise ValueError("Invalid new batch name")
    if args.dry_run:
        arm_templates()
        for profile in PROFILES:
            assert Employee(profile).initial()
        print(
            json.dumps(
                {
                    "dry_run": "passed",
                    "credential_read": False,
                    "provider_calls": 0,
                    "database_calls": 0,
                    "limits_proposal": LIMITS,
                    "pilot": PILOT,
                    "formal": FORMAL,
                    "review_seconds": 300,
                    "absolute_deadline": None,
                }
            )
        )
        return
    if not args.database_url:
        raise ValueError(
            "Provide the self-owned isolated loopback database through CALIBURN_JDWORK_TEST_DSN or --database-url"
        )
    locator = database_locator(args.database_url)
    if args.database_dry_run:
        await database_preflight(args.database_url)
        return
    directory = HERE / "runs" / args.batch_name
    manifest = directory / "manifest.json"
    if not manifest.exists():
        if (
            args.phase != "pilot"
            or not args.limit_usd
            or not args.authorization_reference
        ):
            raise ValueError(
                "Freeze a new pilot research manifest with explicit effective limits and authorization"
            )
        carry = None
        if args.carry_from:
            if (
                re.fullmatch(r"[a-z][a-z0-9_-]{0,60}", args.carry_from) is None
                or args.carry_from == args.batch_name
            ):
                raise ValueError(
                    "Carry must identify a different preserved research revision"
                )
            carry = load_carry(HERE / "runs" / args.carry_from)
        directory.mkdir(parents=True)
        frozen = freeze(
            manifest,
            limit_usd=args.limit_usd,
            authorization_reference=args.authorization_reference,
            database_url=args.database_url,
            carry=carry,
        )
    else:
        frozen = read(manifest)
        if args.limit_usd or args.authorization_reference or args.carry_from:
            raise ValueError("An existing frozen research manifest cannot be changed")
    verify(frozen)
    if frozen["database"] != locator:
        raise ValueError("Execution database differs from frozen public locator")
    if args.freeze_only:
        print(
            json.dumps(
                {
                    "manifest": str(manifest),
                    "sha256": sha(manifest),
                    "provider_calls": 0,
                    "credential_read": False,
                }
            )
        )
        return
    legacy.DSN = args.database_url
    if args.phase == "formal":
        pilot_gate(directory)
    phase_root = directory / args.phase
    phase_root.mkdir()  # Existing phase is never reset or overwritten.
    guard = guard_from_ledger(directory, frozen)
    guard.phase = args.phase
    # The failed v1 mechanism pilot remains part of the same 160-generation,
    # two-compact pilot allowance; an explicit fresh revision does not reset it.
    guard.phase_start = {"generations": 0, "compacts": 0}
    schedule = PILOT if args.phase == "pilot" else FORMAL
    processed = []
    try:
        for profile, group, repeat in schedule:
            if guard.stop_reason:
                break
            name = f"{profile}-r{repeat}-{group}"
            await run_case(
                args.phase, profile, group, repeat, phase_root / name, guard, frozen
            )
            processed.append(name)
            save_ledger(directory, args.phase, processed, guard, schedule)
    finally:
        save_ledger(directory, args.phase, processed, guard, schedule)


if __name__ == "__main__":
    asyncio.run(main(), loop_factory=asyncio.SelectorEventLoop)
