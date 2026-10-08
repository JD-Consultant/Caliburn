"""Real HTTP journey coordinator. Production app owns all agents, tools and writes.

Each case gets a fresh PostgreSQL schema in the named isolated test database. The
batch guard spans all cases. Only diagnostics observe original checkpoint writes.
No key or environment dump is saved. --dry-run never reads the credential.
"""

import argparse
import asyncio
import copy
import functools
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import httpx2
import uvicorn
from conditional_answers import CLOSURE, CONTINUE, PROFILES, Employee
from evidence import collect_sources, write_blind_bundle
from guard import BatchGuard, GuardedTransport, digest, public, role
from manifest import HERE, LIMITS, ROOT, freeze, verify
from measurements import measure
from sqlalchemy import text

import caliburn.agent_execution.request_capacity as capacity
from caliburn import bootstrap
from caliburn.adapters.database_settings import DatabaseSettings
from caliburn.adapters.openai_credentials import read_openai_api_key
from caliburn.adapters.openai_responses import create_responses_client
from caliburn.adapters.response_serialization import compaction_input_items
from caliburn.agent_execution import tool_steps
from caliburn.settings import ModelSettings, Settings

DSN = (
    "postgresql://intplan_test:intplan-local-test@127.0.0.1:55447/caliburn_intplan_test"
)
BASE = "http://127.0.0.1:8177"
REAL_RUNNER = bootstrap.ConsultantRunner
REAL_SAVER = bootstrap.JobFilePostgresSaver
REAL_CAPACITY = capacity.require_request_capacity


def save(path, value):
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )


class ObservedSaver(REAL_SAVER):
    """Record only after the real official saver has acknowledged its write."""

    journal = None

    async def aput(self, config, checkpoint, metadata, new_versions):
        result = await super().aput(config, checkpoint, metadata, new_versions)
        values = checkpoint["channel_values"]
        compact = values.get("compaction_snapshot")
        request = values.get("request_snapshot")
        if (
            compact is not None
            or "projection" in values
            or (isinstance(request, dict) and role(request) == "A")
        ):
            record = {
                "saved_at": datetime.now(timezone.utc).isoformat(),
                "thread_id": config.get("configurable", {}).get("thread_id"),
                "checkpoint_id": checkpoint["id"],
                "adopted": values.get("adopted"),
                "preparation_policy": values.get("preparation_policy"),
                "input_count": values.get("input_count"),
            }
            if compact is not None:
                items = compaction_input_items(compact)
                record["compaction_item_sha256"] = [digest(item) for item in items]
                record["compaction_public"] = public(items)
            if isinstance(request, dict):
                record["request_input_item_sha256"] = [
                    digest(item) for item in request.get("input", [])
                ]
                record["request_input_public"] = public(request.get("input", []))
            for key in [
                "interview_plan_projection",
                "interview_plan_position",
                "request_admission",
                "projection",
                "input_binding",
            ]:
                if key in values:
                    record[key] = public(values[key])
            with self.journal.open("a", encoding="utf-8") as output:
                output.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
        return result


async def migrate(schema):
    # No shell, no dotenv, no environment dump. URL is the fixed isolated database.
    code = "from alembic import command; from caliburn.adapters.database import migration_config; command.upgrade(migration_config(), 'head')"
    import os

    env = {
        key: value
        for key, value in os.environ.items()
        if key
        not in {
            "OPENAI_API_KEY",
            "CALIBURN_OCCUPATION_REFERENCE_URL",
            "CALIBURN_DATABASE_URL",
            "CALIBURN_DATABASE_SCHEMA",
        }
    }
    env.update(CALIBURN_DATABASE_URL=DSN, CALIBURN_DATABASE_SCHEMA=schema)
    process = await asyncio.to_thread(
        subprocess.run,
        [sys.executable, "-c", code],
        env=env,
        capture_output=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        check=False,
    )
    stderr = process.stderr
    if process.returncode:
        raise RuntimeError(
            "Isolated schema migration failed: "
            + stderr.decode(errors="replace")[-1500:]
        )


async def wait_memory(app, seconds=180):
    """Read-only observation avoids closing during pending background Memory work."""
    started = time.monotonic()
    while time.monotonic() - started < seconds:
        async with app.state.database.sessions() as session:
            rows = (
                await session.execute(
                    text("SELECT status, count(*) FROM executions GROUP BY status")
                )
            ).all()
        active = sum(count for status, count in rows if status == "active")
        if not active:
            return {str(status): count for status, count in rows}
        await asyncio.sleep(2)
    return {"observation_timeout": seconds}


async def journey(client, directory, employee, turns, guard, app=None):
    response = await client.post(
        "/api/job-files",
        json={
            "command_id": str(uuid4()),
            "display_name": employee.profile["display_name"],
            "employee_name": "條件回答者",
        },
    )
    response.raise_for_status()
    created = response.json()
    save(directory / "created.json", created)
    path = "/api/job-files/" + created["job_file_id"]
    if app is not None:
        async with app.state.database.sessions() as session:
            baseline = {}
            for table in [
                "memory_snapshots",
                "memory_object_revisions",
                "interview_plan_candidates",
            ]:
                baseline[table] = (
                    await session.execute(
                        text(
                            "SELECT count(*) FROM " + table + " WHERE job_file_id=:id"
                        ),
                        {"id": created["job_file_id"]},
                    )
                ).scalar_one()
        save(directory / "initial-database.json", baseline)

    async def get(suffix):
        response = await client.get(path + suffix)
        response.raise_for_status()
        return response.json()

    async def formal():
        return {
            section: await get("/jd/" + section)
            for section in ["profile", "work", "sources"]
        }

    save(directory / "initial-formal-jd.json", await formal())
    save(directory / "initial-interviews.json", await get("/interviews"))
    save(directory / "initial-plan.json", await get("/interview-plan"))
    message = employee.initial()
    prepared_employee = None
    closure_submitted = False
    driver_reminders = 0
    last_input_was_reminder = False
    missing_active_progress = False
    results = []
    for turn in range(1, turns + 1):
        if guard.stop_reason:
            break
        stem = f"turn-{turn:02}"
        if turn == turns:
            message = CLOSURE  # Common bounded closure, no oracle facts.
            prepared_employee = None  # No selected fact may masquerade as closure.
        command = {"command_id": str(uuid4()), "text": message}
        save(directory / (stem + "-input.json"), command)
        started = time.monotonic()
        response = await client.post(path + "/inputs", json=command)
        response.raise_for_status()
        accepted = response.json()
        last_input_was_reminder = message == CONTINUE
        if last_input_was_reminder:
            driver_reminders += 1
        if message == CLOSURE:
            closure_submitted = True
        if prepared_employee is not None:
            employee = prepared_employee
            employee.audit[-1]["actually_submitted"] = True
            employee.audit[-1]["command_id"] = command["command_id"]
            prepared_employee = None
            save(directory / "conditional-audit.json", employee.state())
        save(directory / (stem + "-accepted.json"), accepted)
        execution = "/consultant-turns/" + accepted["execution_id"]
        captured = False
        while time.monotonic() - started < 700:
            current = await get(execution)
            if (
                current.get("candidate") or current.get("plan_preview")
            ) and not captured:
                save(directory / (stem + "-preview.json"), current)
                captured = True
            if current["status"] in {"completed", "failed", "cancelled", "paused"}:
                break
            await asyncio.sleep(2)
        else:
            current = {"status": "observation_timeout"}
        interviews = await get("/interviews")
        if (
            employee.audit
            and employee.audit[-1].get("command_id") == command["command_id"]
        ):
            originals = [
                item
                for item in interviews["messages"]
                if item["speaker"] == "employee" and item["interview_text"] == message
            ]
            employee.audit[-1]["formally_visible"] = bool(originals)
            employee.audit[-1]["formal_source_ids"] = [
                item.get("source_id") for item in originals
            ]
        result = {
            "status": current,
            "elapsed_seconds": time.monotonic() - started,
            "interviews": interviews,
            "formal_jd": await formal(),
            "plan": await get("/interview-plan"),
            "guard": guard.state(),
        }
        save(directory / (stem + "-result.json"), result)
        results.append(
            {
                "turn": turn,
                "status": current["status"],
                "elapsed_seconds": result["elapsed_seconds"],
            }
        )
        print(
            json.dumps(
                {
                    "case": guard.case,
                    "turn": turn,
                    "status": current["status"],
                    "seconds": round(result["elapsed_seconds"], 1),
                    "spent_usd": str(guard.spent),
                }
            ),
            flush=True,
        )
        if current["status"] != "completed":
            break  # No automatic replay or manufacture of completion.
        if message == CLOSURE:
            break
        if turn == turns:
            break  # No private disclosure after the last public input.
        if turn == turns - 1:
            message = CLOSURE
            continue  # No unused selected disclosure immediately before closure.
        consultant = [
            item for item in interviews["messages"] if item["speaker"] == "consultant"
        ]
        question = consultant[-1]["interview_text"] if consultant else ""
        if app is None:  # Offline HTTP driver seam; paid runs always use review.
            prepared_employee = copy.deepcopy(employee)
            message = prepared_employee.answer(question)
        else:
            opaque_id = uuid4().hex
            review_directory = HERE / "reviews" / opaque_id
            review_directory.mkdir(parents=True)
            candidate = copy.deepcopy(employee)
            candidate.answer(question)
            recent = [
                item["interview_text"]
                for item in interviews["messages"]
                if item["speaker"] == "employee"
            ][-3:]
            pending = {
                "question_id": opaque_id,
                "profile": employee.profile_name,
                "actual_question": question,
                "disclosed": sorted(employee.disclosed),
                "open_gaps": sorted(employee.gaps),
                "seen_topics": sorted(employee.seen_topics),
                "refused_topics": sorted(employee.refused_topics),
                "disclosure_order": employee.disclosure_order,
                "gap_opened_at": employee.gap_opened_at,
                "recent_employee_originals": recent,
                "candidate": candidate.audit[-1],
            }
            save(review_directory / "pending.json", pending)
            save(
                directory / (stem + "-review-binding.json"), {"question_id": opaque_id}
            )
            print(
                json.dumps(
                    {
                        "review_pending": opaque_id,
                        "path": str(review_directory / "pending.json"),
                    }
                ),
                flush=True,
            )
            review_started = time.monotonic()
            while not (review_directory / "decision.json").exists():
                if time.monotonic() - review_started >= 120:
                    guard.stop_reason = (
                        "semantic review timeout; no employee answer disclosed"
                    )
                    break
                await asyncio.sleep(1)
            if not (review_directory / "decision.json").exists():
                break
            decision = json.loads(
                (review_directory / "decision.json").read_text(encoding="utf-8")
            )
            if decision.get("question_id") != opaque_id:
                raise ValueError("Semantic review belongs to another question")
            prepared_employee = copy.deepcopy(employee)
            message = prepared_employee.reviewed_answer(question, decision)
            if decision.get("mode") == "no_question" and (
                driver_reminders >= 2 or last_input_was_reminder
            ):
                message = CLOSURE
                prepared_employee = None
                missing_active_progress = True
            save(
                review_directory / "selected.json",
                {
                    "employee_text": message,
                    "audit": prepared_employee.audit[-1]
                    if prepared_employee is not None
                    else {"bounded_closure": True},
                    "actually_submitted": False,
                },
            )
        save(directory / "conditional-audit.json", employee.state())
    final = await formal()
    save(directory / "formal-jd.json", final)
    save(directory / "formal-interviews.json", await get("/interviews"))
    save(directory / "formal-plan.json", await get("/interview-plan"))
    if app is not None:
        source_contents = await collect_sources(client, path, final["sources"])
        save(directory / "fixed-source-contents.json", source_contents)
    save(directory / "conditional-audit.json", employee.state())
    return {
        "file_id": created["job_file_id"],
        "turns": results,
        "stop": "batch_resource_stop"
        if guard.stop_reason
        else (
            "terminal_" + results[-1]["status"]
            if results and results[-1]["status"] != "completed"
            else "closure_after_missing_active_progress"
            if closure_submitted and missing_active_progress
            else "common_bounded_closure"
            if closure_submitted
            else "incomplete_without_closure"
        ),
        "closure_submitted": closure_submitted,
        "driver_reminders": driver_reminders,
        "missing_active_progress": missing_active_progress,
        "natural_completion_verified": False,
        "guard": guard.state(),
    }


async def run_case(phase, profile, group, repeat, directory, guard, frozen, turns):
    case = f"{profile}-r{repeat}-{group}"
    directory.mkdir()
    guard.case = case
    schema = (
        "intplan_"
        + phase
        + "_"
        + profile
        + "_r"
        + str(repeat)
        + "_"
        + group.lower()
        + "_"
        + uuid4().hex[:6]
    )
    save(
        directory / "case.json",
        {
            "case": case,
            "schema": schema,
            "profile": profile,
            "group": group,
            "repeat": repeat,
            "turn_limit": turns,
            "controlled_mid_work": repeat == 2,
            "initial_public": PROFILES[profile]["initial"],
        },
    )
    await migrate(schema)
    pending_control = repeat == 2

    def restore_control():
        nonlocal pending_control
        pending_control = False

    guard.on_a_compact = restore_control

    def bounded_capacity(request, count, limits, *, completed_steps):
        previous = capacity.MID_WORK_COMPACTION_THRESHOLD_TOKENS
        if pending_control and role(request.create_payload()) == "A":
            capacity.MID_WORK_COMPACTION_THRESHOLD_TOKENS = 45000
        try:
            return REAL_CAPACITY(
                request, count, limits, completed_steps=completed_steps
            )
        finally:
            capacity.MID_WORK_COMPACTION_THRESHOLD_TOKENS = previous

    tool_steps.require_request_capacity = bounded_capacity
    bootstrap.ConsultantRunner = functools.partial(
        REAL_RUNNER, interview_plans_enabled=group == "P2"
    )
    ObservedSaver.journal = directory / "checkpoint-witness.jsonl"
    bootstrap.JobFilePostgresSaver = ObservedSaver

    def guarded_client(*, api_key, timeout_seconds):
        transport = GuardedTransport(
            guard,
            httpx2.AsyncHTTPTransport(retries=0),
            directory / "provider-trace.jsonl",
        )
        client = httpx2.AsyncClient(
            transport=transport,
            timeout=timeout_seconds,
            trust_env=False,
            follow_redirects=False,
        )
        return create_responses_client(
            api_key=api_key, timeout_seconds=timeout_seconds, http_client=client
        )

    bootstrap.create_responses_client = guarded_client
    verify(frozen)
    key = read_openai_api_key(ROOT / "apps/api/.env")
    app = bootstrap.create_app(
        Settings(
            database=DatabaseSettings(url=DSN, schema=schema),
            model=ModelSettings(api_key=key),
            dev_origin=BASE,
        )
    )
    del key
    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=8177, log_level="warning")
    )
    task = asyncio.create_task(server.serve())
    try:
        for _ in range(100):
            if server.started:
                break
            if task.done():
                await task
                raise RuntimeError("App did not start")
            await asyncio.sleep(0.2)
        async with httpx2.AsyncClient(
            base_url=BASE, timeout=120, trust_env=False, headers={"Origin": BASE}
        ) as client:
            result = await journey(
                client, directory, Employee(profile), turns, guard, app
            )
        result["memory_settlement"] = await wait_memory(app)
        result["measurements"] = measure(directory)
        save(directory / "result.json", result)
        if phase == "formal":
            write_blind_bundle(
                directory, HERE / "blind-input", directory.parent / "blind-map.json"
            )
    except Exception as error:
        # Error messages can include arbitrary library text; save safe type only.
        save(
            directory / "failure.json",
            {"error_type": type(error).__name__, "guard": guard.state()},
        )
        raise
    finally:
        server.should_exit = True
        await task
        bootstrap.ConsultantRunner = REAL_RUNNER
        bootstrap.JobFilePostgresSaver = REAL_SAVER
        tool_steps.require_request_capacity = REAL_CAPACITY


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["pilot", "formal"])
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--database-dry-run", action="store_true")
    parser.add_argument("--batch-name")
    args = parser.parse_args()
    if args.dry_run:
        for profile in PROFILES:
            employee = Employee(profile)
            assert employee.initial()
            assert not employee.disclosed
        print(
            json.dumps(
                {
                    "dry_run": "passed",
                    "credential_read": False,
                    "provider_calls": 0,
                    "profiles": list(PROFILES),
                    "limits": LIMITS[args.phase],
                }
            )
        )
        return
    if args.database_dry_run:
        schema = "intplan_preflight_" + uuid4().hex[:8]
        await migrate(schema)
        app = bootstrap.create_app(
            Settings(database=DatabaseSettings(url=DSN, schema=schema), dev_origin=BASE)
        )
        server = uvicorn.Server(
            uvicorn.Config(app, host="127.0.0.1", port=8177, log_level="warning")
        )
        task = asyncio.create_task(server.serve())
        try:
            for _ in range(100):
                if server.started:
                    break
                if task.done():
                    await task
                await asyncio.sleep(0.2)
            async with httpx2.AsyncClient(
                base_url=BASE, timeout=30, trust_env=False, headers={"Origin": BASE}
            ) as client:
                response = await client.post(
                    "/api/job-files",
                    json={
                        "command_id": str(uuid4()),
                        "display_name": "preflight",
                        "employee_name": "offline",
                    },
                )
                response.raise_for_status()
                file_id = response.json()["job_file_id"]
                for suffix in [
                    "/jd/profile",
                    "/jd/work",
                    "/jd/sources",
                    "/interviews",
                    "/interview-plan",
                ]:
                    (
                        await client.get("/api/job-files/" + file_id + suffix)
                    ).raise_for_status()
            save(
                HERE / "database-preflight.json",
                {
                    "schema": schema,
                    "passed": True,
                    "credential_read": False,
                    "provider_calls": 0,
                },
            )
            print("Database and product HTTP preflight passed; no key/provider")
        finally:
            server.should_exit = True
            await task
        return
    batch_name = args.batch_name or args.phase
    if re.fullmatch(r"[a-z][a-z0-9_-]{0,60}", batch_name) is None:
        raise ValueError("Invalid experiment batch name")
    directory = HERE / batch_name
    directory.mkdir()  # Existing phase evidence is never reset or overwritten.
    frozen = freeze(args.phase, directory / "manifest.json")
    limits = LIMITS[args.phase]
    guard = BatchGuard(
        limit=Decimal(limits["limit_usd"]),
        seconds=limits["seconds"],
        max_generations=limits["max_generations"],
        max_compacts=limits["max_compacts"],
        max_outbound=limits["max_outbound"],
        max_counted_input=limits["max_counted_input"],
        verify_frozen=lambda: verify(frozen),
    )
    cases = (
        [("warehouse", group, 1) for group in ["P1", "P2"]]
        if args.phase == "pilot"
        else [
            (profile, group, repeat)
            for repeat in [1, 2]
            for profile in PROFILES
            for group in (["P1", "P2"] if repeat == 1 else ["P2", "P1"])
        ]
    )
    completed = []
    try:
        for profile, group, repeat in cases:
            if guard.stop_reason:
                break
            case_directory = directory / f"{profile}-r{repeat}-{group}"
            await run_case(
                args.phase,
                profile,
                group,
                repeat,
                case_directory,
                guard,
                frozen,
                limits["turns"],
            )
            completed.append(case_directory.name)
            save(
                directory / "batch-state.json",
                {"completed_cases": completed, "guard": guard.state()},
            )
    finally:
        save(
            directory / "batch-state.json",
            {
                "completed_cases": completed,
                "guard": guard.state(),
                "all_scheduled_cases": [f"{p}-r{r}-{g}" for p, g, r in cases],
            },
        )


if __name__ == "__main__":
    asyncio.run(main(), loop_factory=asyncio.SelectorEventLoop)
