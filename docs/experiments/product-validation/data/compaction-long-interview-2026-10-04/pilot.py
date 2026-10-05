"""Bounded research pilot; the actual product workflows own all business effects."""

import argparse
import asyncio
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import time
from dataclasses import asdict
from decimal import Decimal
from importlib.metadata import version
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx2
from caliburn.adapters.database import Database
from caliburn.adapters.database_settings import DatabaseSettings
from caliburn.adapters.graph_checkpointer import create_graph_serializer
from caliburn.adapters.openai_credentials import read_openai_api_key
from caliburn.adapters.openai_models import model_profile
from caliburn.adapters.openai_responses import ResponseRequest, create_responses_client
from caliburn.adapters.process_lock import PostgresProcessLock
from caliburn.agents.job_consultant.instructions import CONSULTANT_INSTRUCTIONS
from caliburn.agents.job_consultant.runner import ConsultantRunner
from caliburn.agents.job_consultant.tools import consultant_tool_definitions
from caliburn.agents.memory_analysis.dispatch import MemoryRoleDispatch
from caliburn.agents.work_situation_analyst.runner import WorkSituationAnalystRunner
from caliburn.agents.work_understanding_analyst.runner import (
    WorkUnderstandingAnalystRunner,
)
from caliburn.features.executions import service as executions
from caliburn.features.executions.models import ExecutionKind, ExecutionScope
from caliburn.features.interviews.models import (
    FormalInterviewExchange,
    SubmitInterviewInput,
)
from caliburn.features.job_description.queries import read_profile
from caliburn.features.job_description.work_queries import read_work
from caliburn.features.job_files.models import CreateJobFile
from caliburn.settings import ModelSettings
from caliburn.transport.model_tools.memory_analysis import MEMORY_CHECKPOINT_TYPES
from caliburn.workflows.interview_inputs import InterviewInputWorkflow
from caliburn.workflows.jd_evidence import JdEvidenceWorkflow
from caliburn.workflows.job_files import JobFileWorkflow
from caliburn.workflows.memory_batch import MemoryBatchWorkflow
from caliburn.workflows.memory_candidates import MemoryCandidateWorkflow
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from preparation import employee_input, load_scenario
from psycopg.conninfo import conninfo_to_dict, make_conninfo

HERE = Path(__file__).resolve().parent
ROOT = next(parent for parent in HERE.parents if (parent / "AGENTS.md").exists())
PILOT_EVENTS = ("e001", "e002", "e004", "e006", "e055")


def load_helper(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ValueError("Unavailable existing experiment helper")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


memory_probe = load_helper(
    "pilot_memory_helpers",
    HERE.parent / "memory-compaction-publish-2026-10-04/experiment.py",
)
provider = load_helper(
    "pilot_provider_observations",
    HERE.parent / "design-comparisons-2026-10-04/provider_observations.py",
)


def fingerprint(payload: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


class PilotStop(BaseException):
    """Terminal research boundary, not a provider error for the product to retry."""


class PilotAllowance:
    def __init__(
        self,
        *,
        max_input_tokens: int = 2_000_000,
        max_outbound_calls: int = 160,
        max_estimated_usd: Decimal = Decimal("1.00"),
    ) -> None:
        self.generation_calls = 0
        self.admitted_input_tokens = 0
        self.outbound_calls = 0
        self.reserved_usd = Decimal(0)
        self.max_input_tokens = max_input_tokens
        self.max_outbound_calls = max_outbound_calls
        self.max_estimated_usd = max_estimated_usd
        self.counts: dict[str, int] = {}
        self.started = time.monotonic()

    def record_count(self, payload: dict[str, Any], input_tokens: object) -> None:
        if type(input_tokens) is not int or input_tokens <= 0:
            raise PilotStop("invalid_remote_count")
        self.counts[fingerprint(payload)] = input_tokens

    def admit(self, path: str, payload: dict[str, Any]) -> None:
        if (
            time.monotonic() - self.started >= 1800
            or self.outbound_calls >= self.max_outbound_calls
        ):
            raise PilotStop("outbound_or_time_limit")
        tokens = 0
        reserve = Decimal("0.0001")
        if path == "/v1/responses":
            request = ResponseRequest.from_snapshot(payload)
            tokens = self.counts.get(fingerprint(request.count_payload()), 0)
            if (
                tokens <= 0
                or self.generation_calls >= 48
                or self.admitted_input_tokens + tokens > self.max_input_tokens
                or payload["max_output_tokens"] != 16_384
                or payload["model"] != "gpt-6-luna"
            ):
                raise PilotStop("generation_or_input_limit")
            reserve = model_profile("gpt-6-luna").pricing.reserve_response_cost(
                input_tokens=tokens, max_output_tokens=16_384
            )
        elif path != "/v1/responses/input_tokens":
            raise PilotStop("unapproved_endpoint")
        if self.reserved_usd + reserve > self.max_estimated_usd:
            raise PilotStop("estimated_budget_limit")
        self.outbound_calls += 1
        self.reserved_usd += reserve
        if tokens:
            self.generation_calls += 1
            self.admitted_input_tokens += tokens


class Recorder:
    def __init__(self, run_dir: Path) -> None:
        self.run_dir = run_dir
        self.allowance = PilotAllowance()
        self.phase: dict[str, Any] = {}
        self.headers: dict[str, str] = {}
        self.received_at = time.monotonic()

    def event(self, payload: dict[str, Any]) -> None:
        memory_probe.append(self.run_dir / "trace.jsonl", {**self.phase, **payload})

    async def request(self, request: httpx2.Request) -> None:
        payload = json.loads(request.content)
        path = request.url.path
        if path == "/v1/responses":
            count = self.allowance.counts.get(
                fingerprint(ResponseRequest.from_snapshot(payload).count_payload()), 0
            )
            delay = provider.admission_delay(
                self.headers, time.monotonic() - self.received_at, count + 16_384 - 4096
            )
            if delay > 120 or time.monotonic() - self.allowance.started + delay >= 1800:
                raise PilotStop("rate_wait_exceeds_pilot")
            if delay:
                self.event({"event": "wait", "seconds": delay})
                await asyncio.sleep(delay)
        try:
            self.allowance.admit(path, payload)
        except PilotStop as error:
            self.event({"event": "admission_stopped", "reason": str(error), "path": path})
            raise
        self.event(
            {
                "event": "request",
                "path": path,
                "payload": memory_probe.public_document(payload),
            }
        )

    async def response(self, response: httpx2.Response) -> None:
        await response.aread()
        self.headers = provider.rate_headers(response.headers)
        self.received_at = time.monotonic()
        path = response.request.url.path
        if response.status_code != 200:
            self.event(
                {
                    "event": "provider_error",
                    "path": path,
                    "http_status": response.status_code,
                }
            )
            raise PilotStop("provider_http_failure")
        payload = response.json()
        if path == "/v1/responses/input_tokens":
            self.allowance.record_count(
                json.loads(response.request.content), payload.get("input_tokens")
            )
        self.event(
            {
                "event": "response",
                "path": path,
                "rate_headers": self.headers,
                "payload": memory_probe.public_document(payload),
            }
        )


def dump(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


async def save_product(
    database: Database, files: JobFileWorkflow, file_id: Any, path: Path
) -> None:
    evidence = JdEvidenceWorkflow(database.sessions)
    overview = await evidence.read_overview(file_id)
    sources = []
    for entry in overview.references:
        content = await evidence.read_content(file_id, overview.revision_id, entry.citation_id)
        sources.append({"entry": asdict(entry), "content": asdict(content)})
    async with database.sessions() as session:
        profile = await read_profile(session, file_id)
        work = await read_work(session, file_id)
    dump(
        path,
        {
            "profile": asdict(profile),
            "work": asdict(work),
            "evidence": sources,
            "interviews": [asdict(entry) for entry in await files.read_interviews(file_id)],
        },
    )


async def run(run_dir: Path, settings: DatabaseSettings) -> None:
    scenario = load_scenario(HERE / "employee-scenario.json")
    git_head = await asyncio.to_thread(
        subprocess.check_output, ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    )
    manifest = {
        "git_head": git_head.strip(),
        "schema": settings.schema,
        "model": "gpt-6-luna",
        "effort": "high",
        "openai": version("openai"),
        "employee_event_ids": PILOT_EVENTS,
        "max_generation_calls": 48,
        "max_outbound_calls": 160,
        "max_input_tokens": 2_000_000,
        "max_output_tokens": 16_384,
        "max_seconds": 1800,
        "max_estimated_usd": "1.00",
        "max_compaction_calls": 0,
        "native_thresholds_unchanged": {
            "before_work": 128_000,
            "complete_step": 160_000,
        },
        "sha256": {
            str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (
                Path(__file__),
                HERE / "pilot-plan.md",
                HERE / "employee-scenario.json",
                HERE / "preparation.py",
                Path(memory_probe.__file__),
                Path(provider.__file__),
            )
        },
        "consultant_instructions_sha256": hashlib.sha256(
            CONSULTANT_INSTRUCTIONS.encode()
        ).hexdigest(),
        "consultant_tools": consultant_tool_definitions(),
        "dependencies": {
            name: version(name)
            for name in (
                "openai",
                "langgraph",
                "langgraph-checkpoint-postgres",
                "psycopg",
                "sqlalchemy",
            )
        },
        "runtime_sources_sha256": {
            str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted((ROOT / "apps/api/src/caliburn").rglob("*.py"))
        },
    }
    dump(run_dir / "manifest.json", manifest)
    await asyncio.to_thread(memory_probe.initialize_schema, settings)
    database = Database(settings)
    lock = PostgresProcessLock(settings)
    recorder = Recorder(run_dir)
    try:
        await lock.acquire()
        # Close the transport even if SDK credential loading fails.
        async with httpx2.AsyncClient(
            follow_redirects=False,
            event_hooks={
                "request": [recorder.request],
                "response": [recorder.response],
            },
        ) as transport:
            async with create_responses_client(
                api_key=read_openai_api_key(ROOT / "apps/api/.env"),
                timeout_seconds=120,
                http_client=transport,
            ) as client:
                async with AsyncPostgresSaver.from_conn_string(
                    make_conninfo(settings.url, options=f"-c search_path={settings.schema}"),
                    serde=create_graph_serializer(allowed_types=MEMORY_CHECKPOINT_TYPES),
                ) as saver:
                    await saver.setup()
                    model = ModelSettings(
                        api_key="configured-by-client",
                        max_model_steps=16,
                        max_attempts_per_request=1,
                        max_outbound_attempts=64,
                        max_compactions=1,
                        max_cost_usd=Decimal("0.40"),
                    )
                    consultant = ConsultantRunner(database.sessions, saver, client, model)
                    files = JobFileWorkflow(database.sessions)
                    created = await files.create(
                        CreateJobFile(uuid4(), "長訪談先導：庫存與物流", "合成員工")
                    )
                    file_id = created.job_file.job_file_id
                    dump(run_dir / "job-file.json", asdict(created.job_file))
                    inputs = InterviewInputWorkflow(database.sessions)
                    dispatch = MemoryRoleDispatch(
                        WorkSituationAnalystRunner(database.sessions, saver, client, model),
                        WorkUnderstandingAnalystRunner(database.sessions, saver, client, model),
                    )
                    memory = MemoryBatchWorkflow(database.sessions, run_role=dispatch)
                    for index, event_id in enumerate(PILOT_EVENTS, 1):
                        recorder.phase = {
                            "phase": "consultant",
                            "event_id": event_id,
                            "turn": index,
                        }
                        accepted = await inputs.accept(
                            SubmitInterviewInput(
                                file_id, uuid4(), employee_input(scenario, event_id)
                            )
                        )
                        scope = ExecutionScope(
                            file_id,
                            accepted.accepted.execution_id,
                            ExecutionKind.CONSULTANT_TURN,
                        )
                        async with database.sessions.begin() as session:
                            writer = await executions.claim_writer(
                                session, scope, writer_id=uuid4()
                            )
                        await lock.check()
                        exchange = await consultant.run(writer)
                        if not isinstance(exchange, FormalInterviewExchange):
                            raise PilotStop("unexpected_pause")
                        dump(
                            run_dir / f"exchange-{index}.json",
                            {
                                "event_id": event_id,
                                "execution_id": scope.execution_id,
                                **asdict(exchange),
                            },
                        )
                        await save_product(
                            database, files, file_id, run_dir / f"product-{index}.json"
                        )
                        print(f"A turn {index} completed ({event_id})", flush=True)
                        if index == 4:
                            recorder.phase = {
                                "phase": "memory",
                                "after_event": event_id,
                            }
                            memory_scope = ExecutionScope(
                                file_id, uuid4(), ExecutionKind.MEMORY_BATCH
                            )
                            async with database.sessions.begin() as session:
                                await executions.admit_execution(session, memory_scope)
                                memory_writer = await executions.claim_writer(
                                    session, memory_scope, writer_id=uuid4()
                                )
                            candidates = MemoryCandidateWorkflow(database.sessions)
                            await candidates.start(memory_writer, exchange.employee_input.source_id)
                            await lock.check()
                            snapshot = await memory.run(memory_writer)
                            dump(
                                run_dir / "memory-snapshot.json",
                                await memory_probe.read_snapshot(candidates, snapshot),
                            )
                            print("B1 -> B2 -> Memory published", flush=True)
        dump(
            run_dir / "result.json",
            {
                "status": "completed",
                "schema": settings.schema,
                "generation_calls": recorder.allowance.generation_calls,
                "outbound_calls": recorder.allowance.outbound_calls,
                "admitted_input_tokens": recorder.allowance.admitted_input_tokens,
                "reserved_estimate_usd": recorder.allowance.reserved_usd,
                "elapsed_seconds": time.monotonic() - recorder.allowance.started,
            },
        )
    # Research boundary: preserve failure evidence without sensitive exception bodies.
    except (Exception, PilotStop, asyncio.CancelledError) as error:
        dump(
            run_dir / "result.json",
            {
                "status": "stopped",
                "schema": settings.schema,
                "phase": recorder.phase,
                "error_type": type(error).__name__,
                "reason": str(error) if isinstance(error, PilotStop) else None,
                "generation_calls": recorder.allowance.generation_calls,
                "outbound_calls": recorder.allowance.outbound_calls,
                "admitted_input_tokens": recorder.allowance.admitted_input_tokens,
                "reserved_estimate_usd": recorder.allowance.reserved_usd,
            },
        )
        print(f"Stopped: {type(error).__name__}; isolated schema retained", flush=True)
        raise SystemExit(2) from None
    finally:
        await lock.close()
        await database.close()


def test_database_url() -> str:
    """A caller supplies the explicit retained research database; never guess credentials."""
    supplied = os.environ.get("CALIBURN_TEST_DATABASE_URL")
    if not supplied:
        raise ValueError("Configure an explicit isolated test database URL")
    return supplied


def validate_database_url(url: str) -> str:
    info = conninfo_to_dict(url)
    if (
        set(info) - {"host", "port", "dbname", "user", "password"}
        or any(
            os.environ.get(name)
            for name in ("PGHOSTADDR", "PGSERVICE", "PGSERVICEFILE", "PGOPTIONS")
        )
        or info.get("host") != "127.0.0.1"
        or info.get("port") != "55441"
        or info.get("dbname") != "caliburn_docker_test"
        or info.get("user") != "caliburn"
    ):
        raise ValueError(
            "Only the fixed isolated research database without connection overrides is allowed"
        )
    return url


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True)
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    if not args.live or Path(args.run).name != args.run or args.run in (".", ".."):
        parser.error("Explicit --live and a new plain run name required")
    url = validate_database_url(test_database_url())
    run_dir = HERE / args.run
    run_dir.mkdir(exist_ok=False)
    settings = DatabaseSettings(url=url, schema="eval_compaction_pilot_" + uuid4().hex)
    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        runner.run(asyncio.wait_for(run(run_dir, settings), timeout=1800))
