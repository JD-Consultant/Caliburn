"""New journey fork only where the 2026-10-08 protocol changes old driver behavior.

Product HTTP, source collection and per-Turn observation reuse the predecessor.
No employee SDK, alternate agent loop, direct Plan/Memory writes or keyword fallback.
"""

import asyncio
import copy
import json
import time
from pathlib import Path
from uuid import uuid4

from controls import accepted_source, checked_decision
from events import manual_command, manual_pending
from materials import CLOSURE, CONTINUE
from review_policy import reviewed_answer
from run_batch import collect_sources, save
from sqlalchemy import text

HERE = Path(__file__).resolve().parent
REVIEW_ROOT = HERE / "reviews"


async def file_review(pending):
    directory = REVIEW_ROOT / pending["question_id"]
    directory.mkdir(parents=True)
    save(directory / "pending.json", pending)
    print(
        json.dumps(
            {
                "review_pending": pending["question_id"],
                "kind": pending["review_kind"],
                "path": str(directory / "pending.json"),
            }
        ),
        flush=True,
    )
    started = time.monotonic()
    while not (directory / "decision.json").exists():
        if time.monotonic() - started >= 300:
            raise TimeoutError("Semantic review timed out")
        await asyncio.sleep(1)
    return checked_decision(
        directory / "decision.json", pending["question_id"], started, time.monotonic
    )


async def apply_manual_event(client, path, directory, profile, review):
    response = await client.get(path + "/jd/work")
    response.raise_for_status()
    before = response.json()
    pending = manual_pending(profile, before, uuid4().hex)
    save(
        directory / "manual-edit-review-binding.json",
        {"question_id": pending["question_id"]},
    )
    decision = await review(pending)
    command = manual_command(pending, decision)
    record = {
        "status": "no_op",
        "public_initial": pending["public_initial"],
        "required_text": pending["required_text"],
        "before": before,
        "decision": decision,
        "command": command,
    }
    if command is not None:
        save(directory / "manual-edit-command.json", command)
        response = await client.post(path + "/jd/tasks", json=command)
        response.raise_for_status()
        record["http_result"] = response.json()
        response = await client.get(path + "/jd/work")
        response.raise_for_status()
        record["after"] = response.json()
        if record["after"]["revision_id"] != record["http_result"]["revision_id"]:
            raise ValueError("Manual saved revision is not the formal HTTP revision")
        record["status"] = "saved"
        record["diff"] = {
            "before_revision": before["revision_id"],
            "after_revision": record["after"]["revision_id"],
            "task_before": next(
                (
                    task
                    for task in before["tasks"]
                    if task["task_id"] == decision.get("task_id")
                ),
                None,
            ),
            "tasks_after": record["http_result"]["tasks"],
        }
    save(directory / "manual-edit.json", record)


async def journey(client, directory, employee, turns, guard, app=None, review=None):
    review = review or file_review
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
            audit = prepared_employee.audit[-1]
            audit["actually_submitted"] = True
            audit["command_id"] = command["command_id"]
            audit["accepted_source_id"] = accepted["source_id"]
            save(directory / (stem + "-disclosure-accepted.json"), audit)
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
        if current["status"] == "completed":
            source = accepted_source(command, accepted, interviews["messages"])
            if prepared_employee is not None:
                employee = prepared_employee
                audit = employee.audit[-1]
                audit["formally_visible"] = True
                audit["formal_source_ids"] = [source["source_id"]]
                audit["formal_interview_sequence"] = source["interview_sequence"]
                prepared_employee = None
                save(directory / "conditional-audit.json", employee.state())
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
        if turn == 10:
            await apply_manual_event(
                client, path, directory, employee.profile_name, review
            )
        opaque_id = uuid4().hex
        recent = [
            item["interview_text"]
            for item in interviews["messages"]
            if item["speaker"] == "employee"
        ][-3:]
        pending = {
            "question_id": opaque_id,
            "review_kind": "employee_disclosure",
            "profile": employee.profile_name,
            "actual_question": question,
            "disclosed": sorted(employee.disclosed),
            "open_gaps": sorted(employee.gaps),
            "seen_topics": sorted(employee.seen_topics),
            "refused_topics": sorted(employee.refused_topics),
            "disclosure_order": employee.disclosure_order,
            "gap_opened_at": employee.gap_opened_at,
            "recent_employee_originals": recent,
            "private_facts": employee.profile["facts"],
        }
        save(directory / (stem + "-review-binding.json"), {"question_id": opaque_id})
        try:
            decision = await review(pending)
        except TimeoutError:
            guard.stop_reason = "semantic review timeout; no employee answer disclosed"
            break
        prepared_employee = copy.deepcopy(employee)
        message = reviewed_answer(prepared_employee, question, decision)
        if decision.get("mode") == "no_question" and (
            driver_reminders >= 2 or last_input_was_reminder
        ):
            message = CLOSURE
            prepared_employee = None
            missing_active_progress = True
        selected = {
            "employee_text": message,
            "audit": prepared_employee.audit[-1]
            if prepared_employee is not None
            else {"bounded_closure": True},
            "actually_submitted": False,
        }
        save(
            directory / (stem + "-selected.json"),
            {"question_id": opaque_id, **selected},
        )
        if review is file_review:
            save(REVIEW_ROOT / opaque_id / "selected.json", selected)
        save(directory / "conditional-audit.json", employee.state())
    if not (directory / "manual-edit.json").exists():
        save(
            directory / "manual-edit.json",
            {
                "status": "not_occurred",
                "reason": "No legal completed Turn 10 with a subsequent employee input",
            },
        )
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
