"""Bounded prompt comparison through the real A runner and isolated PostgreSQL.

prepare: create synthetic fixtures and freeze evidence without model calls.
execute: claim exactly one approved run; retain the schema and all outcomes.
The public reference HTTP fixture freezes content, not retrieval quality.
"""

import argparse
import ast
import asyncio
import json
import subprocess
import sys
import traceback
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import httpx2
import psycopg
from alembic import command
from caliburn.adapters.database import migration_config
from caliburn.adapters.graph_checkpointer import create_graph_serializer
from caliburn.adapters.occupation_references import OccupationReferenceClient
from caliburn.adapters.openai_credentials import read_openai_api_key
from caliburn.adapters.openai_responses import create_responses_client
from caliburn.agents.job_consultant import runner as runner_module
from caliburn.agents.job_consultant.tools import consultant_tool_definitions
from caliburn.bootstrap import create_app
from caliburn.features.executions import service as executions
from caliburn.features.executions.models import (
    ExecutionKind,
    ExecutionScope,
    ExecutionStatus,
)
from caliburn.features.interviews.models import SubmitInterviewInput
from caliburn.features.job_description import source_service
from caliburn.features.job_description.sources import (
    AddJdSource,
    InterviewSource,
    JdSourceTarget,
    ReviseJdSources,
    SourceTargetKind,
)
from caliburn.features.job_files.service import lock_job_file
from caliburn.settings import DatabaseSettings, ModelSettings, Settings
from caliburn.transport.http.interview_inputs import get_consultant_dispatch
from caliburn.workflows.interview_completion import record_formal_interview
from caliburn.workflows.interview_inputs import InterviewInputWorkflow
from fastapi.testclient import TestClient
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg import sql
from psycopg.conninfo import make_conninfo
from sqlalchemy import URL, create_engine

HERE = Path(__file__).resolve().parent
ROOT = next(path for path in HERE.parents if (path / "AGENTS.md").is_file())
SHARED = HERE.parent / "early-interview-recall-2026-10-05"
sys.path.insert(0, str(SHARED))
sys.path.insert(0, str(ROOT / "apps/api"))
from study_guard import ResearchStop, StudyGuard
from study_manifest import claim_run, freeze_files, save_new, verify_files

BASELINE = "6ec52822ee475876ed20e57d818c8db298c42928"
CONTAINER = "caliburn-jd-docker-test-postgres-1"
DATABASE = "caliburn_docker_test"
OUTPUT = HERE / "live-01"
PROMPT_PATH = "apps/api/src/caliburn/agents/job_consultant/instructions.py"
REFERENCE_PATH = "apps/api/src/caliburn/agents/job_consultant/reference_instructions.py"


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def old_constant(path, name):
    source = subprocess.run(
        ["git", "show", f"{BASELINE}:{path}"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        encoding="utf-8",
    ).stdout
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == name
            for target in node.targets
        ):
            if (
                isinstance(node.value, ast.Call)
                and not node.value.args
                and not node.value.keywords
                and isinstance(node.value.func, ast.Attribute)
                and node.value.func.attr == "strip"
                and isinstance(node.value.func.value, ast.Constant)
                and isinstance(node.value.func.value.value, str)
            ):
                return node.value.func.value.value.strip()
            return ast.literal_eval(node.value)
    raise ValueError("Baseline constant not found")


def database_settings(schema):
    # Capture privately: Docker environment/password are never printed or saved.
    inspected = subprocess.run(
        ["docker", "inspect", CONTAINER],
        check=True,
        capture_output=True,
        encoding="utf-8",
    )
    config = json.loads(inspected.stdout)[0]
    environment = dict(item.split("=", 1) for item in config["Config"]["Env"])
    if config["Name"] != f"/{CONTAINER}" or not DATABASE.endswith("_test"):
        raise ValueError("Wrong isolated database target")
    ports = config["NetworkSettings"]["Ports"]["5432/tcp"]
    if {(p["HostIp"], p["HostPort"]) for p in ports} != {("127.0.0.1", "55441")}:
        raise ValueError("Unexpected database binding")
    url = URL.create(
        "postgresql",
        username="caliburn",
        password=environment["POSTGRES_PASSWORD"],
        host="127.0.0.1",
        port=55441,
        database=DATABASE,
    ).render_as_string(hide_password=False)
    return DatabaseSettings(url=url, schema=schema)


def test_client(settings):
    app = create_app(Settings(database=settings))
    # Explicit runner drives A; no supervisor or background paid requests.
    app.dependency_overrides[get_consultant_dispatch] = lambda: lambda scope: None
    return TestClient(
        app,
        base_url="http://127.0.0.1:8100",
        headers={"Origin": "http://127.0.0.1:8100"},
        backend_options={"loop_factory": asyncio.SelectorEventLoop},
    )


def checked(response):
    response.raise_for_status()
    return response.json()


def document(client, file_id):
    return {
        "profile": checked(client.get(f"/api/job-files/{file_id}/jd/profile")),
        "work": checked(client.get(f"/api/job-files/{file_id}/jd/work")),
        "sources": checked(client.get(f"/api/job-files/{file_id}/jd/sources")),
    }


async def seed_interview(sessions, file_id, text):
    accepted = (
        await InterviewInputWorkflow(sessions).accept(
            SubmitInterviewInput(file_id, uuid4(), text)
        )
    ).accepted
    scope = ExecutionScope(
        file_id, accepted.execution_id, ExecutionKind.CONSULTANT_TURN
    )
    async with sessions.begin() as session:
        writer = await executions.claim_writer(session, scope, writer_id=uuid4())
        exchange = await record_formal_interview(
            session, writer, reply_text="已記錄這段工作說明。"
        )
        await executions.finish_execution(session, writer, ExecutionStatus.COMPLETED)
    return exchange.employee_input.source_id


async def seed_sources(sessions, file_id, revision, task_sources):
    async with sessions.begin() as session:
        await lock_job_file(session, file_id)
        for task_id, source_id in task_sources:
            revision = await source_service.revise_sources(
                session,
                file_id,
                ReviseJdSources(
                    uuid4(),
                    revision,
                    JdSourceTarget(SourceTargetKind.TASK, item_id=task_id),
                    (AddJdSource(InterviewSource(source_id)),),
                ),
            )


def seed_case(client, case, arm):
    file_id = UUID(
        checked(
            client.post(
                "/api/job-files",
                json={
                    "command_id": str(uuid4()),
                    "display_name": f"{case['case_id']} {arm}",
                    "employee_name": "合成受訪者",
                },
            )
        )["job_file_id"]
    )
    sessions = client.app.state.database.sessions
    sources = [
        client.portal.call(seed_interview, sessions, file_id, text)
        for text in case["prior_employee_statements"]
    ]
    prefix = f"/api/job-files/{file_id}/jd"
    revision = checked(client.get(prefix + "/profile"))["revision_id"]
    revision = checked(
        client.post(
            prefix + "/profile",
            json={
                "command_id": str(uuid4()),
                "expected_revision_id": revision,
                "changes": [
                    {
                        "action": "set_field",
                        "field": "purpose",
                        "value": case["initial_document"]["purpose"],
                    }
                ],
            },
        )
    )["revision_id"]
    task_sources = []
    for area in case["initial_document"]["areas"]:
        result = checked(
            client.post(
                prefix + "/areas",
                json={
                    "command_id": str(uuid4()),
                    "expected_revision_id": revision,
                    "change": {
                        "action": "create_area",
                        "title": area["title"],
                        "scope_text": area["scope_text"],
                    },
                },
            )
        )
        revision, area_id = result["revision_id"], result["areas"][-1]["area_id"]
        for task in area["tasks"]:
            result = checked(
                client.post(
                    prefix + "/tasks",
                    json={
                        "command_id": str(uuid4()),
                        "expected_revision_id": revision,
                        "change": {
                            "action": "create_task",
                            "area_id": area_id,
                            "title": task["title"],
                            "description": task["description"],
                            "outcomes": [],
                            "requirements": [],
                        },
                    },
                )
            )
            revision = result["revision_id"]
            task_sources.append(
                (
                    UUID(result["tasks"][-1]["task_id"]),
                    sources[task["source_statement"] - 1],
                )
            )
    client.portal.call(seed_sources, sessions, file_id, UUID(revision), task_sources)
    return {
        "arm": arm,
        "case_id": case["case_id"],
        "job_file_id": str(file_id),
        "before": document(client, file_id),
    }


def reference_fixture():
    # Existing validated contract fixture; no employee's hidden annual facts.
    from tests.unit.test_occupation_reference_client import (
        reference_payload,
        search_payload,
        task_payload,
    )

    reference = reference_payload()
    reference.update(
        title="流程與紀錄作業（合成參考）", overview="核對資訊、維護紀錄及異常交接。"
    )
    reference["units"][0]["tasks"][0]["names"] = [{"code": "T1", "name": "核對與交接"}]
    reference["units"][0]["tasks"] = reference["units"][0]["tasks"][:1]
    search = search_payload()
    search["references"][0]["reference"] = reference
    task = task_payload()
    task["names"] = reference["units"][0]["tasks"][0]["names"]
    task["competency_blocks"][0].update(
        outputs=[{"code": "O1", "name": "可追查紀錄"}],
        indicators=[{"code": "P1", "text": "依確認資料核對，異常記錄及交接。"}],
        knowledge=[{"code": None, "name": "核對規則"}],
        skills=[{"code": "S1", "name": "差異記錄"}],
    )
    return {"reference": reference, "search": search, "task": task}


def prepare(*, case_ids=None, limits=None):
    cases = (
        read_json(HERE / "cases.json")["cases"]
        + read_json(HERE / "holdout-cases.json")["cases"]
    )
    if case_ids is not None:
        cases = [case for case in cases if case["case_id"] in case_ids]
        assert len(cases) == len(case_ids)
    assert len({case["case_id"] for case in cases}) == len(cases)
    for case in cases:
        for area in case["initial_document"]["areas"]:
            for task in area["tasks"]:
                assert (
                    1
                    <= task["source_statement"]
                    <= len(case["prior_employee_statements"])
                )
    old = old_constant(PROMPT_PATH, "CONSULTANT_INSTRUCTIONS")
    old_reference = old_constant(REFERENCE_PATH, "OCCUPATION_REFERENCE_INSTRUCTIONS")
    prompts = {
        "old": old + "\n\n" + old_reference,
        "new": runner_module.CONSULTANT_INSTRUCTIONS
        + "\n\n"
        + runner_module.OCCUPATION_REFERENCE_INSTRUCTIONS,
    }
    paths = [
        HERE / "run_comparison.py",
        HERE / "cases.json",
        HERE / "holdout-cases.json",
        SHARED / "study_guard.py",
        SHARED / "study_manifest.py",
        ROOT / "apps/api/tests/unit/test_occupation_reference_client.py",
        ROOT / "apps/api/uv.lock",
    ]
    paths.extend((ROOT / "apps/api/src/caliburn").rglob("*.py"))
    files = freeze_files(paths, root=ROOT, output=OUTPUT)
    schema = "jd_prompt_" + uuid4().hex
    settings = database_settings(schema)
    with psycopg.connect(settings.url, autocommit=True) as connection:
        connection.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
    engine = create_engine(
        settings.sqlalchemy_url, connect_args={"options": f"-c search_path={schema}"}
    )
    try:
        with engine.begin() as connection:
            config = migration_config()
            config.attributes.update(connection=connection, schema=schema)
            command.upgrade(config, "head")
    finally:
        engine.dispose()
    fixtures = []
    with test_client(settings) as client:
        for index, case in enumerate(cases):
            for arm in ("old", "new") if index % 2 == 0 else ("new", "old"):
                fixtures.append(seed_case(client, case, arm))
    tools = consultant_tool_definitions(occupation_references_enabled=True)
    save_new(
        OUTPUT / "manifest.json",
        {
            "baseline": BASELINE,
            "model": "gpt-6-luna",
            "effort": "high",
            "max_output_tokens": 16384,
            "database": DATABASE,
            "schema": schema,
            "files": files,
            "cases": cases,
            "instructions": prompts,
            "main_instructions": {
                "old": old,
                "new": runner_module.CONSULTANT_INSTRUCTIONS,
            },
            "reference_instructions": {
                "old": old_reference,
                "new": runner_module.OCCUPATION_REFERENCE_INSTRUCTIONS,
            },
            "tools": {"old": tools, "new": tools},
            "schedule": [{"arm": f["arm"], "case_id": f["case_id"]} for f in fixtures],
            "reference_fixture": reference_fixture(),
            "fixtures": fixtures,
            "budget_usd": (limits or {}).get("budget_usd", "0.10"),
            "seconds": (limits or {}).get("seconds", 1200),
            "parent_boundary": limits,
            "scope": "A prompt comparison; real PostgreSQL/candidate/tools; frozen synthetic reference HTTP; no Memory workers or retrieval quality claim",
        },
    )
    print(
        f"PREPARED {len(fixtures)} independent files; no model calls; schema {schema}",
        flush=True,
    )


async def run_turn(client, saver, sdk, settings, file_id, text, reference):
    sessions = client.app.state.database.sessions
    accepted = (
        await InterviewInputWorkflow(sessions).accept(
            SubmitInterviewInput(file_id, uuid4(), text)
        )
    ).accepted
    scope = ExecutionScope(
        file_id, accepted.execution_id, ExecutionKind.CONSULTANT_TURN
    )
    async with sessions.begin() as session:
        writer = await executions.claim_writer(session, scope, writer_id=uuid4())
    exchange = await runner_module.ConsultantRunner(
        sessions,
        saver,
        sdk,
        settings,
        occupation_references=reference,
    ).run(writer)
    if not hasattr(exchange, "consultant_reply"):
        raise ResearchStop("unexpected_pause")
    return {"execution_id": str(scope.execution_id), "exchange": asdict(exchange)}


def execute():
    manifest = read_json(OUTPUT / "manifest.json")
    verify_files(manifest["files"], root=ROOT)
    database = database_settings(manifest["schema"])
    key = read_openai_api_key(ROOT / "apps/api/.env")
    remaining_seconds = manifest["seconds"]
    parent = manifest.get("parent_boundary")
    if parent:
        remaining_seconds = min(
            remaining_seconds,
            int(
                (
                    datetime.fromisoformat(parent["deadline_utc"]) - datetime.now(UTC)
                ).total_seconds()
            ),
        )
    if remaining_seconds < 1:
        save_new(OUTPUT / "not-started.json", {"reason": "original_deadline_reached"})
        return
    claim_run(
        OUTPUT,
        {
            "authorization": "Same user-approved US$0.10 / 20 minute batch; no renewed allowance",
            "budget_usd": manifest["budget_usd"],
            "seconds": remaining_seconds,
            "parent_boundary": parent,
        },
    )
    guard = StudyGuard(
        OUTPUT,
        batch_usd=Decimal(manifest["budget_usd"]),
        seconds=remaining_seconds,
        prior_usd=Decimal(0),
    )
    guard.frozen_policy = manifest
    completed = []
    current = None
    with test_client(database) as client:

        async def scenario():
            nonlocal current
            dsn = make_conninfo(
                database.url, options=f"-c search_path={database.schema}"
            )
            async with AsyncPostgresSaver.from_conn_string(
                dsn, serde=create_graph_serializer()
            ) as saver:
                await saver.setup()
                sdk = create_responses_client(
                    api_key=key,
                    timeout_seconds=120,
                    http_client=httpx2.AsyncClient(
                        event_hooks={
                            "request": [guard.request],
                            "response": [guard.response],
                        },
                        timeout=120,
                    ),
                )
                ref_calls = []

                def reference_response(request):
                    ref_calls.append(
                        {"method": request.method, "path": request.url.path}
                    )
                    if request.url.path.endswith(":search"):
                        payload = manifest["reference_fixture"]["search"]
                    elif "/tasks/" in request.url.path:
                        payload = manifest["reference_fixture"]["task"]
                    else:
                        payload = manifest["reference_fixture"]["reference"]
                    return httpx2.Response(200, json=payload)

                async with httpx2.AsyncClient(
                    base_url="http://references.invalid",
                    transport=httpx2.MockTransport(reference_response),
                ) as transport:
                    reference = OccupationReferenceClient(transport)
                    settings = ModelSettings(
                        api_key=key, model=manifest["model"], max_attempts_per_request=1
                    )
                    try:
                        for fixture in manifest["fixtures"]:
                            current = {
                                "arm": fixture["arm"],
                                "case_id": fixture["case_id"],
                            }
                            guard.phase = current
                            case = next(
                                case
                                for case in manifest["cases"]
                                if case["case_id"] == current["case_id"]
                            )
                            # In this isolated process only; both tool sets are frozen/current.
                            runner_module.CONSULTANT_INSTRUCTIONS = manifest[
                                "main_instructions"
                            ][current["arm"]]
                            runner_module.OCCUPATION_REFERENCE_INSTRUCTIONS = manifest[
                                "reference_instructions"
                            ][current["arm"]]
                            file_id = UUID(fixture["job_file_id"])
                            before_usage = guard.summary()
                            ref_start = len(ref_calls)
                            turns = [
                                await run_turn(
                                    client,
                                    saver,
                                    sdk,
                                    settings,
                                    file_id,
                                    case["employee_input"],
                                    reference,
                                )
                            ]
                            save_new(
                                OUTPUT
                                / f"{current['case_id']}-{current['arm']}-turn-1.json",
                                turns[-1],
                            )
                            if current["case_id"] == "probe_before_closure":
                                reply = turns[-1]["exchange"]["consultant_reply"][
                                    "interview_text"
                                ]
                                probes = (
                                    "年度",
                                    "一年",
                                    "每年",
                                    "低頻",
                                    "特殊期間",
                                    "不常",
                                    "平常之外",
                                    "平常以外",
                                    "週期",
                                    "周期",
                                )
                                if any(word in reply for word in probes) and (
                                    "？" in reply or "?" in reply
                                ):
                                    turns.append(
                                        await run_turn(
                                            client,
                                            saver,
                                            sdk,
                                            settings,
                                            file_id,
                                            "每年十二月有一次財務一起參加的全倉盤點，我照分到的區域點貨，再把結果交主管；那次是全倉，不只是月底我的區域。",
                                            reference,
                                        )
                                    )
                                    turns.append(
                                        await run_turn(
                                            client,
                                            saver,
                                            sdk,
                                            settings,
                                            file_id,
                                            "對，那個補上就好，今天先到這裡。",
                                            reference,
                                        )
                                    )
                            # portal.call is already running in the client's loop; use the
                            # real read workflows rather than nested synchronous HTTP here.
                            completed.append(
                                {
                                    **fixture,
                                    "turns": turns,
                                    "reference_calls": ref_calls[ref_start:],
                                    "usage_before": before_usage,
                                    "usage_after": guard.summary(),
                                }
                            )
                            save_new(
                                OUTPUT
                                / f"{current['case_id']}-{current['arm']}-turns.json",
                                completed[-1],
                            )
                            print(
                                f"DONE {current['case_id']} {current['arm']} ({len(turns)} turns), occupied ${guard.summary()['batch_occupied_usd']}",
                                flush=True,
                            )
                    finally:
                        await sdk.close()

        try:
            client.portal.call(scenario)
        except ResearchStop as error:
            save_new(
                OUTPUT / "failure.json",
                {"phase": current, "reason": str(error), "accounting": guard.summary()},
            )
            print(f"STOP {error}; evidence retained", flush=True)
        except Exception as error:  # noqa: BLE001 -- outer process boundary records without retry.
            save_new(
                OUTPUT / "failure.json",
                {
                    "phase": current,
                    "error_type": type(error).__name__,
                    "frames": [
                        {
                            "file": Path(frame.filename).name,
                            "line": frame.lineno,
                            "function": frame.name,
                        }
                        for frame in traceback.extract_tb(error.__traceback__)
                    ],
                    "accounting": guard.summary(),
                },
            )
            print(f"STOP local {type(error).__name__}; no automatic replay", flush=True)
        finally:
            for fixture in completed:
                save_new(
                    OUTPUT / f"{fixture['case_id']}-{fixture['arm']}-after.json",
                    document(client, fixture["job_file_id"]),
                )
            save_new(
                OUTPUT / "result.json",
                {
                    "completed": [
                        {"arm": f["arm"], "case_id": f["case_id"]} for f in completed
                    ],
                    "accounting": guard.summary(),
                },
            )


def followup():
    global OUTPUT
    original = read_json(OUTPUT / "result.json")
    if (OUTPUT / "failure.json").exists() or Decimal(
        original["accounting"]["pending_reserved_usd"]
    ) != 0:
        raise ValueError("Prior unresolved send forbids a followup")
    started = read_json(OUTPUT / "started.json")
    deadline = datetime.fromisoformat(started["started_at"]) + timedelta(seconds=1200)
    remaining = Decimal("0.10") - Decimal(original["accounting"]["batch_occupied_usd"])
    seconds = int((deadline - datetime.now(UTC)).total_seconds())
    if remaining <= 0 or seconds < 1:
        raise ValueError("Original authorized boundary reached")
    OUTPUT = HERE / "followup-01"
    prepare(
        case_ids={"derive_and_link_capabilities", "group_nonwarehouse_work"},
        limits={
            "budget_usd": str(remaining),
            "seconds": seconds,
            "deadline_utc": deadline.isoformat(),
            "prior_occupied_usd": original["accounting"]["batch_occupied_usd"],
            "reason": "One declared corrective iteration on the two observed omissions; exploratory, original criteria unchanged",
        },
    )
    execute()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["prepare", "execute", "followup"])
    arguments = parser.parse_args()
    if arguments.mode == "prepare":
        prepare()
    elif arguments.mode == "execute":
        execute()
    else:
        followup()
