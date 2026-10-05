"""Real Memory parent and PostgreSQL, two fixed batches; never targets production."""

import argparse
import asyncio
import hashlib
import json
import os
import subprocess
from dataclasses import asdict
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import httpx2
import psycopg
from alembic import command
from caliburn.adapters.database import Database, migration_config
from caliburn.adapters.graph_checkpointer import create_graph_serializer
from caliburn.adapters.openai_credentials import read_openai_api_key
from caliburn.adapters.openai_failures import classify_response_failure
from caliburn.adapters.openai_responses import create_responses_client
from caliburn.agent_execution.context_compaction import read_prepared_history
from caliburn.agent_execution.tool_steps import read_completed_response_history
from caliburn.agents.memory_analysis.dispatch import MemoryRoleDispatch
from caliburn.agents.work_situation_analyst.instructions import SITUATION_INSTRUCTIONS
from caliburn.agents.work_situation_analyst.runner import WorkSituationAnalystRunner
from caliburn.agents.work_understanding_analyst.instructions import (
    UNDERSTANDING_INSTRUCTIONS,
)
from caliburn.agents.work_understanding_analyst.runner import (
    WorkUnderstandingAnalystRunner,
)
from caliburn.features.executions import history
from caliburn.features.executions import service as executions
from caliburn.features.executions.history_models import AgentRole
from caliburn.features.executions.models import ExecutionKind, ExecutionScope
from caliburn.features.work_memory.revisions import MemoryLayer
from caliburn.settings import DatabaseSettings, ModelSettings
from caliburn.transport.model_tools.memory_analysis import MEMORY_CHECKPOINT_TYPES
from caliburn.workflows.memory_batch import MemoryBatchWorkflow
from caliburn.workflows.memory_candidates import MemoryCandidateWorkflow
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from openai import APIStatusError
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from sqlalchemy import create_engine

HERE = Path(__file__).resolve().parent
ROOT = next(parent for parent in HERE.parents if (parent / "AGENTS.md").exists())
MESSAGES = (
    "請說明庫存盤點與年度查核的工作、頻率與決定權。",
    "我每月盤點庫存，核對帳面與實物，記錄差異交倉庫主管；主管核准才能調整ERP，我沒有核准權。每年一次協助年度查核，準備盤點表和單據，不負責查核結論。",
    "盤點有沒有變更？是否還有其他工作？",
    "更正：盤點目前改成每季一次，不是每月；其他核准責任不變，年度查核也不變。新增工作是每週核對客戶退貨的品項與數量，記錄差異交品保；能不能再次銷售由品保決定，我只依品保結論登錄，不判定商品可售。",
)


def public_document(value):
    """Recursive: provider output nests both reasoning and compaction items."""
    if isinstance(value, list):
        return [public_document(item) for item in value]
    if not isinstance(value, dict):
        return value
    result = {}
    for key, item in value.items():
        if value.get("type") == "reasoning" and key == "content":
            continue
        if key == "encrypted_content":
            if item is not None:
                result["encrypted_length"] = len(item)
                result["encrypted_sha256"] = hashlib.sha256(item.encode()).hexdigest()
        else:
            result[key] = public_document(item)
    return result


def append(path: Path, payload: dict) -> None:
    with path.open("a", encoding="utf-8") as stream:
        stream.write(
            json.dumps(
                {"at": datetime.now(UTC).isoformat(), **payload},
                ensure_ascii=False,
                default=str,
            )
            + "\n"
        )
        stream.flush()


def initialize_schema(settings: DatabaseSettings) -> None:
    with psycopg.connect(settings.url, autocommit=True) as connection:
        connection.execute(
            sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(settings.schema))
        )
    engine = create_engine(
        settings.sqlalchemy_url,
        connect_args={"options": f"-c search_path={settings.schema}"},
    )
    try:
        with engine.begin() as connection:
            config = migration_config()
            config.attributes.update(connection=connection, schema=settings.schema)
            command.upgrade(config, "head")
    finally:
        engine.dispose()


def seed_messages(settings: DatabaseSettings, file_id, *, batch: int):
    with psycopg.connect(
        settings.url, autocommit=True, options=f"-c search_path={settings.schema}"
    ) as connection:
        if batch == 1:
            connection.execute(
                "INSERT INTO job_files (job_file_id, creation_command_id,initial_display_name,display_name,employee_name) VALUES (%s,%s,'compaction test','compaction test','合成')",
                (file_id, uuid4()),
            )
        last_source = None
        for offset in range(2):
            sequence = (batch - 1) * 2 + offset + 1
            last_source = uuid4()
            speaker = (
                "app" if sequence == 1 else "consultant" if offset == 0 else "employee"
            )
            connection.execute(
                "INSERT INTO interview_texts (job_file_id,source_id,speaker,interview_text) VALUES (%s,%s,%s,%s)",
                (file_id, last_source, speaker, MESSAGES[sequence - 1]),
            )
            connection.execute(
                "INSERT INTO formal_interviews (job_file_id,interview_sequence,source_id) VALUES (%s,%s,%s)",
                (file_id, sequence, last_source),
            )
        return last_source


async def read_snapshot(candidates: MemoryCandidateWorkflow, snapshot) -> dict:
    objects = []
    for layer in MemoryLayer:
        entries = await candidates.read_snapshot_map(
            snapshot.job_file_id, snapshot.snapshot_id, layer
        )
        for entry in entries:
            item = await candidates.read_snapshot_object(
                snapshot.job_file_id, snapshot.snapshot_id, entry.object_id
            )
            objects.append(asdict(item))
    return json.loads(
        json.dumps(
            {"snapshot": asdict(snapshot), "objects": objects},
            ensure_ascii=False,
            default=str,
        )
    )


async def run(output_dir: Path, settings: DatabaseSettings) -> None:
    git_head = await asyncio.to_thread(
        subprocess.check_output, ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    )
    manifest = {
        "git_head": git_head.strip(),
        "schema": settings.schema,
        "model": "gpt-6-luna",
        "effort": "high",
        "messages": MESSAGES,
        "openai": version("openai"),
        "thresholds": {"control": 128_000, "compacted": 1},
        "protocol_sha256": hashlib.sha256(
            (HERE / "protocol.md").read_bytes()
        ).hexdigest(),
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "instructions_sha256": {
            "B1": hashlib.sha256(SITUATION_INSTRUCTIONS.encode()).hexdigest(),
            "B2": hashlib.sha256(UNDERSTANDING_INSTRUCTIONS.encode()).hexdigest(),
        },
        "maximum_generation_calls": 64,
        "maximum_input_tokens": 2_000_000,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    await asyncio.to_thread(initialize_schema, settings)
    database = Database(settings)
    trace_context = {}
    budget = {
        "model_calls": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "compactions": 0,
        "cached_tokens": 0,
        "outbound_calls": 0,
    }

    async def on_request(request):
        budget["outbound_calls"] += 1
        payload = json.loads(request.content)
        if request.url.path.endswith("/responses"):
            await asyncio.sleep(5)
            if budget["model_calls"] >= 64:
                raise ValueError("Experiment generation budget exhausted")
            budget["model_calls"] += 1
        if request.url.path.endswith("/compact"):
            budget["compactions"] += 1
        append(
            output_dir / "trace.jsonl",
            {
                "event": "request",
                **trace_context,
                "path": request.url.path,
                "payload": public_document(payload),
            },
        )

    async def on_response(response):
        await response.aread()
        if response.status_code != 200:
            failure = classify_response_failure(
                APIStatusError(
                    "Experimental provider failure",
                    response=response,
                    body=response.json().get("error"),
                )
            )
            append(
                output_dir / "trace.jsonl",
                {
                    "event": "provider_error",
                    **trace_context,
                    "http_status": response.status_code,
                    "failure": asdict(failure),
                },
            )
            # BaseException bypasses the product's normal rate-limit retry policy.
            # Only this isolated driver stops; no production behavior is altered.
            raise asyncio.CancelledError("experiment_provider_stop")
        payload = response.json()
        append(
            output_dir / "trace.jsonl",
            {
                "event": "response",
                **trace_context,
                "path": response.request.url.path,
                "payload": public_document(payload),
            },
        )
        if response.request.url.path.endswith("/input_tokens") and (
            payload["input_tokens"] > 125_000
            or budget["input_tokens"] + payload["input_tokens"] > 2_000_000
        ):
            raise ValueError("Experiment input budget exhausted")
        usage = payload.get("usage")
        if usage:
            budget["input_tokens"] += usage["input_tokens"]
            budget["output_tokens"] += usage["output_tokens"]
            budget["cached_tokens"] += usage.get("input_tokens_details", {}).get(
                "cached_tokens", 0
            )

    try:
        async with httpx2.AsyncClient(  # noqa: SIM117 - explicit transport scope protects cleanup if SDK construction fails
            follow_redirects=False,
            event_hooks={"request": [on_request], "response": [on_response]},
        ) as transport:
            async with create_responses_client(
                api_key=read_openai_api_key(ROOT / "apps/api/.env"),
                timeout_seconds=90,
                http_client=transport,
            ) as client:
                dsn = make_conninfo(
                    settings.url, options=f"-c search_path={settings.schema}"
                )
                async with AsyncPostgresSaver.from_conn_string(
                    dsn,
                    serde=create_graph_serializer(
                        allowed_types=MEMORY_CHECKPOINT_TYPES
                    ),
                ) as saver:
                    await saver.setup()
                    model = ModelSettings(
                        api_key="configured-by-client",
                        max_output_tokens=4096,
                        max_model_steps=64,
                        max_outbound_attempts=64,
                        max_attempts_per_request=1,
                        max_compactions=2,
                        turn_timeout_seconds=720,
                    )
                    dispatch = MemoryRoleDispatch(
                        WorkSituationAnalystRunner(
                            database.sessions, saver, client, model
                        ),
                        WorkUnderstandingAnalystRunner(
                            database.sessions, saver, client, model
                        ),
                    )
                    parent = MemoryBatchWorkflow(database.sessions, run_role=dispatch)
                    candidates = MemoryCandidateWorkflow(database.sessions)
                    async with asyncio.timeout(1800):
                        for arm, threshold in (("control", 128_000), ("compacted", 1)):
                            file_id = uuid4()
                            first = None
                            snapshots = []
                            with patch(
                                "caliburn.agents.memory_analysis.runner.HISTORY_THRESHOLD_TOKENS",
                                threshold,
                            ):
                                for batch in (1, 2):
                                    trace_context.clear()
                                    trace_context.update(
                                        arm=arm, batch=batch, job_file_id=str(file_id)
                                    )
                                    source_id = await asyncio.to_thread(
                                        seed_messages, settings, file_id, batch=batch
                                    )
                                    scope = ExecutionScope(
                                        file_id, uuid4(), ExecutionKind.MEMORY_BATCH
                                    )
                                    async with database.sessions.begin() as session:
                                        await executions.admit_execution(session, scope)
                                        writer = await executions.claim_writer(
                                            session, scope, writer_id=uuid4()
                                        )
                                    stage = await candidates.start(writer, source_id)
                                    if stage is None:
                                        raise ValueError(
                                            "Expected a nonempty Memory batch"
                                        )
                                    snapshot = await parent.run(writer)
                                    fixed = await read_snapshot(candidates, snapshot)
                                    before_reentry = dict(budget)
                                    repeated = await parent.run(writer)
                                    role_history = {}
                                    for role in (
                                        AgentRole.WORK_SITUATION_ANALYST,
                                        AgentRole.WORK_UNDERSTANDING_ANALYST,
                                    ):
                                        async with database.sessions() as session:
                                            binding = (
                                                await history.read_context_history(
                                                    session, scope, role
                                                )
                                            )
                                            head = await history.read_adopted_context(
                                                session, file_id, role
                                            )
                                        prepared = await read_prepared_history(
                                            saver,
                                            thread_id=binding.prepared.thread_id,
                                            checkpoint_id=binding.prepared.checkpoint_id,
                                        )
                                        completed = await read_completed_response_history(
                                            saver,
                                            thread_id=binding.completed.thread_id,
                                            checkpoint_id=binding.completed.checkpoint_id,
                                        )
                                        role_history[role.value] = {
                                            "prepared": asdict(binding.prepared),
                                            "completed": asdict(binding.completed),
                                            "head_matches_completed": head
                                            == binding.completed,
                                            "prepared_item_types": [
                                                item.get("type", "message")
                                                for item in prepared.items
                                            ],
                                            "completed_item_types": [
                                                item.get("type", "message")
                                                for item in completed.items
                                            ],
                                        }
                                    original_unchanged = True
                                    if first is None:
                                        first = fixed
                                    else:
                                        original_unchanged = (
                                            first
                                            == await read_snapshot(
                                                candidates, snapshots[0]
                                            )
                                        )
                                    snapshots.append(snapshot)
                                    record = {
                                        **trace_context,
                                        "execution_id": str(scope.execution_id),
                                        "published": True,
                                        "fixed": fixed,
                                        "old_snapshot_unchanged": original_unchanged,
                                        "reentry_same_snapshot": repeated == snapshot,
                                        "reentry_no_outbound": before_reentry == budget,
                                        "role_history": role_history,
                                    }
                                    append(output_dir / "results.jsonl", record)
                                    print(
                                        json.dumps(
                                            {
                                                key: record[key]
                                                for key in (
                                                    "arm",
                                                    "batch",
                                                    "published",
                                                    "old_snapshot_unchanged",
                                                    "reentry_no_outbound",
                                                )
                                            }
                                        ),
                                        flush=True,
                                    )
        append(output_dir / "run.jsonl", {"event": "completed", **budget})
    except (Exception, asyncio.CancelledError) as error:  # noqa: BLE001 - outer experiment boundary preserves failures without sensitive payloads
        append(
            output_dir / "run.jsonl",
            {"event": "stopped", "error_type": type(error).__name__, **budget},
        )
        print(
            f"Stopped safely: {type(error).__name__}; retained schema {settings.schema}",
            flush=True,
        )
        raise SystemExit(2) from None
    finally:
        await database.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True)
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    if not args.live or Path(args.run).name != args.run or args.run in (".", ".."):
        parser.error("Use --live and a plain, new run name")
    url = os.environ.get("CALIBURN_TEST_DATABASE_URL", "")
    info = conninfo_to_dict(url)
    if info.get("host") not in ("127.0.0.1", "localhost", "::1") or not info.get(
        "dbname", ""
    ).endswith("_test"):
        parser.error("Explicit loopback database ending in _test required")
    output_dir = HERE / args.run
    output_dir.mkdir(exist_ok=False)
    settings = DatabaseSettings(url=url, schema="eval_memory_" + uuid4().hex)
    asyncio.run(run(output_dir, settings), loop_factory=asyncio.SelectorEventLoop)
