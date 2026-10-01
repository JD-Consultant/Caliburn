"""Explicit, paid, synthetic-only interview simulation for measuring analysis quality.

Never invoked by tests or application startup. A persona-driven "employee" model answers the
real backend's consultant over HTTP, so the whole product path runs: A, background Memory,
PostgreSQL. Only the employee side is simulated. The output is one JSON file per run: the public
transcript, the final JD with its sources, and automatic checks that separate an elicitation
gap (a fact never came up) from a recording gap (it came up but is not in the JD).

The checks are coarse marker checks meant for comparing prompt versions on the same personas.
They do not replace reading the transcript and JD against the analysis and JD guides.
Personas: tests/fixtures/job_analysis_quality/personas.json. Authorization and limits: T17 evidence.

Typical run, from apps/api: start a backend on its own database schema and port
(`scripts/run_backend.py --key-file .env --port 8103`, database and PDF variables per the README),
then `python scripts/simulate_interview.py --persona warehouse --base-url http://127.0.0.1:8103
--key-file .env --output <new file>.json`. A fresh run creates a new job file; the output file must
not exist yet, and `<output>.progress.jsonl` gets one line per Turn so a crashed run keeps its
transcript. The journey options (--human-edit-at, --cancel-during, --kill-during with
--restart-command, --export-pdf, --think-seconds, --retry-failed) are meant for the long
persona, whose entry may also set `late_correction` (a correction of something said earlier)
and `min_turns`. To resume a diagnosed interruption, supply `--resume-job-file`,
`--resume-execution` and the original absolute `--deadline` (ISO8601 with timezone), retaining
the original output path and journey options. The explicit execution may already have completed
when the harness reconnects. Earlier operations are not replayed. Events append to a separate
`.events.jsonl`; these local files are evidence, not an alternative product recovery mechanism.
"""

import argparse
import asyncio
import json
import re
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx2
from openai import APIConnectionError, RateLimitError

from caliburn.adapters.openai_credentials import read_openai_api_key
from caliburn.adapters.openai_responses import (
    ResponseRequest,
    create_response,
    create_responses_client,
)

if __package__:
    from .interview_progress import (
        JourneyEvents,
        ResumePoint,
        append_record,
        read_records,
        seconds_until,
        validate_history,
    )
else:  # Also retain the documented `python scripts/simulate_interview.py` entry point.
    from interview_progress import (
        JourneyEvents,
        ResumePoint,
        append_record,
        read_records,
        seconds_until,
        validate_history,
    )

PERSONAS = Path(__file__).parents[1] / "tests/fixtures/job_analysis_quality/personas.json"
EMPLOYEE_MODEL = "gpt-6-luna"
TURN_TIMEOUT_SECONDS = 2_100
POLL_SECONDS = 2.0
EMPLOYEE_ATTEMPTS = 6
LEADING = re.compile(r"是不是|是否|對不對|對嗎|沒錯吧|應該是")
HISTORY_WORDS = re.compile(r"(以前|原本|過去|先前|舊)")
TRAILING_FLAG = re.compile(r"\s*\{[^{}]*\"nothing_more\"[^{}]*\}\s*$")

EMPLOYEE_RULES = "\n".join(
    [
        "你正在接受職務顧問的訪談。你是這份工作的員工，不是職務說明書專家；",
        "說話自然、口語，不用專業術語。",
        "",
        "回答規則：",
        "1. 只回答顧問剛問的內容，通常 1–4 句、約 120 字內；",
        "   不要把筆記一次講完，也不要替顧問總結。",
        "2. 標示（被問到才說）的內容，只有顧問問到相關面向才說——例如怎樣算做好或",
        "   被退回的情況、最容易出錯的地方、用什麼工具或系統、工作環境或體力、",
        "   上班時間、需要什麼資格；沒被問就不要提。",
        "3. 只用筆記內的事實。筆記沒有的細節，就說「這個我不太確定」或「沒有特別的」，",
        "   不要編造數字、流程或名稱。",
        "4. 顧問的問句若預設了與筆記不同的內容，禮貌更正；",
        "   顧問的整理若正確就簡短同意，不正確就指出。",
        "5. 若顧問問你還有沒有其他要補充，而你的筆記內容已被問完，就說沒有了。",
        "",
        '只輸出一個 JSON，不要其他文字：{"reply": "你的回答", "nothing_more": true 或 false}',
        "nothing_more 只在你已沒有任何要補充、顧問也在做整體確認或收尾時為 true。",
    ]
)


def employee_prompt(persona: dict[str, Any], transcript: list[dict[str, Any]]) -> str:
    notes = []
    for fact in persona["facts"]:
        if fact["kind"] == "unknown":
            notes.append(f"- （你不清楚）{fact['text']}")
        elif fact["kind"] == "hidden":
            notes.append(f"- （被問到才說）{fact['text']}")
        else:
            notes.append(f"- {fact['text']}")
    lines = [
        ("顧問：" if message["speaker"] != "employee" else "我：") + message["interview_text"]
        for message in transcript
    ]
    return (
        f"【你的背景】\n{persona['background']}\n\n【你的私人筆記】\n"
        + "\n".join(notes)
        + "\n\n【訪談到目前為止】\n"
        + "\n".join(lines)
    )


async def employee_reply(
    sdk: Any, persona: dict[str, Any], transcript: list[dict[str, Any]]
) -> tuple[str, bool]:
    request = ResponseRequest(
        model=EMPLOYEE_MODEL,
        instructions=EMPLOYEE_RULES,
        input_items=[{"role": "user", "content": employee_prompt(persona, transcript)}],
        tools=[],
        reasoning_effort="low",
        max_output_tokens=2_000,
    )
    # The product's own requests can use up the account's tokens-per-minute; a person would just
    # wait a moment and answer, so the employee model is retried instead of ending the run.
    for attempt in range(1, EMPLOYEE_ATTEMPTS + 1):
        try:
            text = (await create_response(sdk, request)).output_text.strip()
            break
        except RateLimitError, APIConnectionError:
            if attempt == EMPLOYEE_ATTEMPTS:
                raise
            await asyncio.sleep(min(60, 5 * attempt))
    match = re.search(r"\{.*\}", text, re.DOTALL)
    try:
        parsed = json.loads(match.group(0)) if match else {}
        return str(parsed["reply"]).strip(), bool(parsed.get("nothing_more", False))
    except ValueError, KeyError:
        # The model sometimes answers in plain text and appends only the flag; the flag is not
        # something the employee said, so it must not reach the consultant.
        flag = TRAILING_FLAG.search(text)
        return TRAILING_FLAG.sub("", text).strip(), bool(flag and "true" in flag.group(0))


class Backend:
    def __init__(self, http: httpx2.AsyncClient) -> None:
        self.http = http
        self.file_id = ""
        self.restart_deadline = 0.0

    def expect_restart(self, seconds: float = 90.0) -> None:
        self.restart_deadline = time.monotonic() + seconds

    async def read_turn(self, execution_id: str) -> dict[str, Any]:
        while True:
            remaining = self.restart_deadline - time.monotonic() if self.restart_deadline else None
            if remaining is not None and remaining <= 0:
                raise TimeoutError("The original execution did not become readable within 90s")
            try:
                async with asyncio.timeout(remaining):
                    result = await self.get(
                        f"/api/job-files/{self.file_id}/consultant-turns/{execution_id}"
                    )
                self.restart_deadline = 0.0
                return dict(result.get("turn", result))
            except httpx2.TransportError:
                if time.monotonic() >= self.restart_deadline:
                    raise
                print("restart wait: transport unavailable", flush=True)
            except httpx2.HTTPStatusError as error:
                code = error.response.status_code
                if code not in (500, 502, 503, 504) or time.monotonic() >= self.restart_deadline:
                    raise
                print(f"restart wait: HTTP {code}", flush=True)
            await asyncio.sleep(min(POLL_SECONDS, max(0, self.restart_deadline - time.monotonic())))

    async def get(self, path: str) -> Any:
        response = await self.http.get(path)
        response.raise_for_status()
        return response.json()

    async def create_file(self, name: str) -> None:
        response = await self.http.post(
            "/api/job-files",
            json={"command_id": str(uuid4()), "display_name": name, "employee_name": "模擬員工"},
        )
        response.raise_for_status()
        self.file_id = response.json()["job_file_id"]

    async def interviews(self) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = (
            await self.get(f"/api/job-files/{self.file_id}/interviews")
        )["messages"]
        return messages

    async def send(self, text: str) -> str:
        response = await self.http.post(
            f"/api/job-files/{self.file_id}/inputs", json={"command_id": str(uuid4()), "text": text}
        )
        response.raise_for_status()
        return str(response.json()["execution_id"])

    async def wait_for_turn(self, execution_id: str) -> str:
        deadline = time.monotonic() + TURN_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            turn = await self.read_turn(execution_id)
            status = str(turn["status"])
            if status in ("completed", "failed", "cancelled"):
                return status
            await asyncio.sleep(POLL_SECONDS)
        return "timeout"

    async def cancel(self, execution_id: str) -> None:
        response = await self.http.post(
            f"/api/job-files/{self.file_id}/consultant-turns/{execution_id}/cancel",
            headers={"Origin": "http://127.0.0.1:8100"},
        )
        response.raise_for_status()

    async def human_edit(self, purpose: str, task_title: str) -> dict[str, Any]:
        """One person edits the formal JD by hand: the purpose, and one added task."""
        profile = await self.get(f"/api/job-files/{self.file_id}/jd/profile")
        edited = await self.http.post(
            f"/api/job-files/{self.file_id}/jd/profile",
            json={
                "command_id": str(uuid4()),
                "expected_revision_id": profile["revision_id"],
                "changes": [{"action": "set_field", "field": "purpose", "value": purpose}],
            },
        )
        edited.raise_for_status()
        tasks = await self.get(f"/api/job-files/{self.file_id}/jd/tasks")
        added = await self.http.post(
            f"/api/job-files/{self.file_id}/jd/tasks",
            json={
                "command_id": str(uuid4()),
                "expected_revision_id": tasks["revision_id"],
                "change": {
                    "action": "create_task",
                    "area_id": None,
                    "title": task_title,
                    "description": "由人工補充的任務，用來檢查後續的 AI 訪談不會悄悄覆寫它。",
                    "outcomes": [],
                    "requirements": [],
                },
            },
        )
        added.raise_for_status()
        return {"purpose": purpose, "task_title": task_title}

    async def export_pdf(self) -> bytes:
        response = await self.http.get(f"/api/job-files/{self.file_id}/jd/export.pdf")
        response.raise_for_status()
        return response.content


HUMAN_PURPOSE = "（人工撰寫）確保原物料與包材及時、足量且成本合理地供應生產。"
HUMAN_TASK = "（人工補充）彙整供應商年度績效資料"


async def prepare_resume(backend: Backend, output: Path, execution_id: str) -> ResumePoint:
    turns = read_records(output.with_suffix(".progress.jsonl"))
    turn = await backend.read_turn(execution_id)
    if turn["job_file_id"] != backend.file_id or turn["execution_id"] != execution_id:
        raise ValueError("Resume execution identity does not match")
    messages = await backend.interviews()
    validate_history(turns, messages)
    employees = [m["interview_text"] for m in messages if m["speaker"] == "employee"]
    # At most the one pending Turn may have completed since the last harness checkpoint.
    if len(employees) > len(turns) + 1 or (
        len(employees) > len(turns) and employees[-1] != turn["input_text"]
    ):
        raise ValueError("Resume history has advanced beyond the selected execution")
    if turn.get("status") == "completed" and len(employees) != len(turns) + 1:
        raise ValueError("Completed execution is not the next entry in the resume history")
    return ResumePoint(turns, execution_id, turn["input_text"])


async def run_interview(
    backend: Backend,
    sdk: Any,
    persona: dict[str, Any],
    max_turns: int,
    options: argparse.Namespace,
    events: list[dict[str, Any]],
    *,
    resume: ResumePoint | None = None,
) -> list[dict[str, Any]]:
    turns: list[dict[str, Any]] = list(resume.turns) if resume else []
    text = resume.input_text if resume else persona["opening"]
    correction = persona["correction"]
    late = persona.get("late_correction")
    late_done = bool(late and any(late["text"] in t["employee"] for t in turns))
    for number in range(len(turns) + 1, max_turns + 1):
        started = time.monotonic()
        resuming = resume is not None
        if not resuming and options.human_edit_at == number:
            events.append(
                {
                    "turn": number,
                    "event": "human_edit",
                    **await backend.human_edit(HUMAN_PURPOSE, HUMAN_TASK),
                }
            )
        execution_id = resume.execution_id if resume else await backend.send(text)
        events.append(
            {
                "turn": number,
                "event": "execution_resumed" if resuming else "input_accepted",
                "execution_id": execution_id,
                "input_text": text,
            }
        )
        resume = None
        if not resuming and options.cancel_during == number:
            await asyncio.sleep(8)
            await backend.cancel(execution_id)
            cancelled = await backend.wait_for_turn(execution_id)
            if cancelled not in ("cancelled", "failed"):
                raise RuntimeError(f"Cancellation did not end safely: {cancelled}; not resending")
            events.append(
                {
                    "turn": number,
                    "event": "cancelled_then_resent",
                    "first": cancelled,
                    "execution_id": execution_id,
                }
            )
            execution_id = await backend.send(text)
            events.append(
                {
                    "turn": number,
                    "event": "input_accepted",
                    "execution_id": execution_id,
                    "input_text": text,
                }
            )
        elif not resuming and options.kill_during == number:
            await asyncio.sleep(12)
            await asyncio.to_thread(subprocess.run, options.restart_command, shell=True, check=True)
            backend.expect_restart()
            events.append({"turn": number, "event": "backend_killed_mid_turn_and_restarted"})
        status = await backend.wait_for_turn(execution_id)
        # A Turn that ends in an error is shown to the employee, who sends the same sentence again
        # as a person would. The restart of the kill Turn may end it safely, so it gets one more.
        resends_left = options.retry_failed + (1 if options.kill_during == number else 0)
        while resends_left and (
            status == "failed" or (options.kill_during == number and status == "cancelled")
        ):
            resends_left -= 1
            events.append({"turn": number, "event": "turn_ended_then_resent", "first": status})
            execution_id = await backend.send(text)
            events.append(
                {
                    "turn": number,
                    "event": "input_accepted",
                    "execution_id": execution_id,
                    "input_text": text,
                }
            )
            status = await backend.wait_for_turn(execution_id)
        messages = await backend.interviews()
        reply = next((m for m in reversed(messages) if m["speaker"] == "consultant"), None)
        turns.append(
            {
                "turn": number,
                "status": status,
                "seconds": round(time.monotonic() - started, 1),
                "employee": text,
                "consultant": reply["interview_text"] if reply and status == "completed" else None,
                "execution_id": execution_id,
                **({"resumed": True} if resuming else {}),
            }
        )
        print(f"turn {number}: {status} in {turns[-1]['seconds']}s", flush=True)
        append_record(options.output.with_suffix(".progress.jsonl"), turns[-1])
        if status != "completed" or number == max_turns:
            break
        text, done = await employee_reply(sdk, persona, messages)
        await asyncio.sleep(options.think_seconds)  # a person takes time to type the answer
        if number + 1 == correction["turn"] and correction["text"] not in text:
            text = f"{text} {correction['text']}"
        said = " ".join(m["interview_text"] for m in messages if m["speaker"] == "employee")
        if (
            late
            and not late_done
            and number + 1 >= late["turn"]
            and any(key in said for key in late["requires"])
        ):
            # The employee only corrects something that was actually said earlier.
            text = f"{text} {late['text']}"
            late_done = True
            events.append({"turn": number + 1, "event": "late_correction_sent"})
        if done and number + 1 > correction["turn"] and number + 1 >= persona.get("min_turns", 0):
            turns.append({"turn": number + 1, "employee": text, "consultant": None, "final": True})
            execution_id = await backend.send(text)
            events.append(
                {
                    "turn": number + 1,
                    "event": "input_accepted",
                    "execution_id": execution_id,
                    "input_text": text,
                }
            )
            turns[-1]["execution_id"] = execution_id
            status = await backend.wait_for_turn(execution_id)
            messages = await backend.interviews()
            turns[-1]["status"] = status
            turns[-1]["consultant"] = next(
                (m["interview_text"] for m in reversed(messages) if m["speaker"] == "consultant"),
                None,
            )
            append_record(options.output.with_suffix(".progress.jsonl"), turns[-1])
            break
    return turns


def strings_of(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [s for item in value.values() for s in strings_of(item)]
    if isinstance(value, list):
        return [s for item in value for s in strings_of(item)]
    return []


async def collect(backend: Backend) -> dict[str, Any]:
    profile = await backend.get(f"/api/job-files/{backend.file_id}/jd/profile")
    work = await backend.get(f"/api/job-files/{backend.file_id}/jd/work")
    sources = await backend.get(f"/api/job-files/{backend.file_id}/jd/sources")
    contents = {}
    for reference in sources["references"]:
        detail = await backend.get(
            f"/api/job-files/{backend.file_id}/jd/sources/{reference['citation_id']}"
            f"?revision_id={sources['revision_id']}"
        )
        contents[reference["citation_id"]] = detail["content"]
    return {
        "profile": profile["profile"],
        "work": work,
        "references": sources["references"],
        "source_contents": contents,
        "interviews": await backend.interviews(),
    }


def citation_audit(persona: dict[str, Any], collected: dict[str, Any]) -> dict[str, Any]:
    """For each JD item that states a persona fact, does one of ITS cited sources say it?

    Coarse marker check, like the rest: it finds the omission where a fact moved into an item but
    the item cites only the turn that restated something else. A fact the employee never said is
    not counted; Memory-sourced citations are not read (the harness only sees interview text).
    """
    work, profile = collected["work"], collected["profile"]
    items: dict[tuple[str, str], str] = {}
    for area in work["areas"]:
        items["area", area["area_id"]] = f"{area['title']} {area.get('scope_text') or ''}"
    for task in work["tasks"]:
        items["task", task["task_id"]] = f"{task['title']} {task['description']}"
        for detail in task["outcomes"] + task["requirements"]:
            items["detail", detail["detail_id"]] = detail["text"]
    for person in work["collaborators"]:
        items["collaborator", person["collaborator_id"]] = (
            f"{person.get('name') or ''} {person.get('scope_text') or ''}"
        )
    for condition in work["conditions"]:
        items["condition", condition["condition_id"]] = condition["text"]
    for field, value in profile.items():
        if isinstance(value, str):
            items["profile_field", field] = value
    cited: dict[tuple[str, str], list[str]] = {}
    for reference in collected["references"]:
        target = reference["target"]
        key = (target["kind"], target["field"] or target["item_id"])
        content = collected["source_contents"].get(reference["citation_id"], {})
        cited.setdefault(key, []).append(content.get("interview_text", ""))
    employee_text = "\n".join(
        m["interview_text"] for m in collected["interviews"] if m["speaker"] == "employee"
    )
    checked, unsupported = 0, []
    for fact in persona["facts"]:
        keys = fact["keys"]
        if not keys or not any(key in employee_text for key in keys):
            continue
        for item, text in items.items():
            if not any(key in text for key in keys):
                continue
            checked += 1
            if not any(any(key in source for key in keys) for source in cited.get(item, [])):
                unsupported.append({"fact": fact["id"], "item": f"{item[0]}:{text[:30]}"})
    return {
        "checked": checked,
        "unsupported": unsupported,
        "support_rate": round(1 - len(unsupported) / checked, 2) if checked else None,
    }


def evaluate(persona: dict[str, Any], collected: dict[str, Any]) -> dict[str, Any]:
    jd_text = "\n".join(
        strings_of(collected["profile"])
        + strings_of({k: v for k, v in collected["work"].items() if k != "revision_id"})
    )
    employee_text = "\n".join(
        m["interview_text"] for m in collected["interviews"] if m["speaker"] == "employee"
    )
    facts = {}
    for fact in persona["facts"]:
        if fact["keys"]:
            facts[fact["id"]] = {
                "kind": fact["kind"],
                "surfaced": any(key in employee_text for key in fact["keys"]),
                "in_jd": any(key in jd_text for key in fact["keys"]),
            }
    correction = persona["correction"]
    old_left = [
        m.start()
        for word in correction["old"]
        for m in re.finditer(re.escape(word), jd_text)
        if not HISTORY_WORDS.search(jd_text[max(0, m.start() - 12) : m.start()])
    ]
    late = persona.get("late_correction")
    late_check = None
    if late:
        late_old = [
            m.start()
            for word in late["old"]
            for m in re.finditer(re.escape(word), jd_text)
            if not HISTORY_WORDS.search(jd_text[max(0, m.start() - 12) : m.start()])
        ]
        late_check = {
            "sent": any(
                late["text"] in m["interview_text"]
                for m in collected["interviews"]
                if m["speaker"] == "employee"
            ),
            "new_present": any(word in jd_text for word in late["new"]),
            "old_left_as_current": len(late_old),
        }
    contents = collected["source_contents"]
    profile_sources = {}
    for field, expected in persona["checks"]["source_expect"].items():
        cited = [
            contents[r["citation_id"]].get("interview_text", "")
            for r in collected["references"]
            if r["target"]["kind"] == "profile_field" and r["target"]["field"] == field
        ]
        profile_sources[field] = {
            "value": collected["profile"].get(field),
            "cited": len(cited),
            "supported": any(any(k in text for k in expected) for text in cited),
        }
    work = collected["work"]
    consultant = [
        m["interview_text"] for m in collected["interviews"] if m["speaker"] == "consultant"
    ]
    questions = sum(text.count("？") + text.count("?") for text in consultant)
    return {
        "facts": facts,
        "recording_gaps": sorted(k for k, v in facts.items() if v["surfaced"] and not v["in_jd"]),
        "elicitation_gaps": sorted(k for k, v in facts.items() if not v["surfaced"]),
        "correction": {
            "new_present": any(word in jd_text for word in correction["new"]),
            "old_left_as_current": len(old_left),
            "unchanged_kept": [
                any(word in jd_text for word in group) for group in correction["unchanged"]
            ],
        },
        "late_correction": late_check,
        "profile_sources": profile_sources,
        "citations": citation_audit(persona, collected),
        "collaborators_in_text": [
            any(k in jd_text for k in group) for group in persona["checks"]["collaborators"]
        ],
        "shape": {
            "areas": len(work["areas"]),
            "tasks": len(work["tasks"]),
            "outcomes": sum(len(t["outcomes"]) for t in work["tasks"]),
            "requirements": sum(len(t["requirements"]) for t in work["tasks"]),
            "capabilities": len(work["capabilities"]),
            "collaborator_items": len(work["collaborators"]),
            "condition_items": len(work["conditions"]),
            "references": len(collected["references"]),
        },
        "style": {
            "consultant_turns": len(consultant),
            "mean_consultant_chars": round(sum(map(len, consultant)) / max(1, len(consultant))),
            "questions_per_turn": round(questions / max(1, len(consultant)), 2),
            "leading_phrases": sum(len(LEADING.findall(text)) for text in consultant),
        },
    }


async def execute_journey(arguments: argparse.Namespace, events: JourneyEvents) -> int:
    persona = json.loads(PERSONAS.read_text(encoding="utf-8"))[arguments.persona]
    max_turns = arguments.max_turns or persona["max_turns"]
    key = read_openai_api_key(arguments.key_file)
    started = datetime.now(UTC).isoformat()
    async with (
        create_responses_client(api_key=key, timeout_seconds=120) as sdk,
        httpx2.AsyncClient(base_url=arguments.base_url, timeout=60) as http,
    ):
        backend = Backend(http)
        resume = None
        if arguments.resume_job_file:
            backend.file_id = arguments.resume_job_file
            backend.expect_restart()
            resume = await prepare_resume(backend, arguments.output, arguments.resume_execution)
        else:
            await backend.create_file(f"模擬訪談 {arguments.persona} {arguments.label}")
        # The result file is written only at the end; the id lets a crashed run be re-collected.
        print(f"job file {backend.file_id}", flush=True)
        events.append(
            {
                "event": "harness_started",
                "job_file_id": backend.file_id,
                "resume_execution": arguments.resume_execution,
                "deadline": arguments.deadline.isoformat() if arguments.deadline else None,
            }
        )
        turns = await run_interview(
            backend, sdk, persona, max_turns, arguments, events, resume=resume
        )
        collected = await collect(backend)
        if arguments.export_pdf:
            pdf = await backend.export_pdf()
            arguments.output.with_suffix(".pdf").write_bytes(pdf)
            events.append(
                {"event": "pdf_exported", "bytes": len(pdf), "is_pdf": pdf[:4] == b"%PDF"}
            )
    result = {
        "persona": arguments.persona,
        "label": arguments.label,
        "started": started,
        "job_file_id": backend.file_id,
        "turns": turns,
        "events": events,
        "jd": {"profile": collected["profile"], "work": collected["work"]},
        "references": collected["references"],
        "source_contents": collected["source_contents"],
        "checks": evaluate(persona, collected),
    }
    with arguments.output.open("x", encoding="utf-8") as report:
        json.dump(result, report, ensure_ascii=False, indent=1)
    print(json.dumps(result["checks"], ensure_ascii=False, indent=1))
    return 0


async def execute(arguments: argparse.Namespace) -> int:
    if bool(arguments.resume_job_file) != bool(arguments.resume_execution):
        raise ValueError("Resume requires both the job file and original execution")
    if arguments.resume_job_file and arguments.deadline is None:
        raise ValueError("Resume must retain the original absolute deadline")
    if arguments.output.exists():
        raise FileExistsError(arguments.output)
    if not arguments.resume_job_file and any(
        arguments.output.with_suffix(suffix).exists()
        for suffix in (".progress.jsonl", ".events.jsonl")
    ):
        raise ValueError("Existing progress requires explicit resume, not a new job file")
    remaining = seconds_until(arguments.deadline)
    events = JourneyEvents(arguments.output)
    try:
        async with asyncio.timeout(remaining):
            return await execute_journey(arguments, events)
    except (Exception, asyncio.CancelledError) as error:
        # Do not persist credentials/HTTP bodies from arbitrary exception text.
        events.append({"event": "harness_stopped", "error_type": type(error).__name__})
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--persona", required=True, choices=sorted(json.loads(PERSONAS.read_text("utf-8")))
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:8102")
    parser.add_argument("--key-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--label", default="run")
    parser.add_argument("--max-turns", type=int, default=0)
    parser.add_argument("--resume-job-file", default="", help="continue this existing job file")
    parser.add_argument("--resume-execution", default="", help="wait for this original execution")
    parser.add_argument(
        "--deadline", type=datetime.fromisoformat, help="original absolute deadline"
    )
    # Journey operations for a long run; each is off by default.
    parser.add_argument(
        "--cancel-during", type=int, default=0, help="cancel this turn, then resend"
    )
    parser.add_argument("--kill-during", type=int, default=0, help="restart the backend mid-turn")
    parser.add_argument("--restart-command", default="", help="shell command that restarts it")
    parser.add_argument("--human-edit-at", type=int, default=0, help="hand-edit the JD before it")
    parser.add_argument("--export-pdf", action="store_true", help="save the formal PDF at the end")
    parser.add_argument(
        "--think-seconds", type=float, default=0.0, help="pause before each next employee message"
    )
    parser.add_argument(
        "--retry-failed", type=int, default=0, help="resend the sentence of a Turn that failed"
    )
    raise SystemExit(asyncio.run(execute(parser.parse_args())))
