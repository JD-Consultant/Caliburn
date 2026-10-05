"""Clone the stopped research DB and discard only its failed A candidate through the product."""

import argparse
import asyncio
import hashlib
import json
import subprocess
from dataclasses import asdict
from uuid import UUID

import psycopg
from caliburn.adapters.database import Database
from caliburn.adapters.database_settings import DatabaseSettings
from caliburn.adapters.graph_checkpointer import create_graph_serializer
from caliburn.adapters.process_lock import PostgresProcessLock
from caliburn.features.executions import history
from caliburn.features.executions import service as executions
from caliburn.features.executions.history_models import AgentRole, HistoryWindowKind
from caliburn.features.executions.models import ExecutionStatus, ExecutionWriter
from caliburn.transport.model_tools.memory_analysis import MEMORY_CHECKPOINT_TYPES
from caliburn.workflows.consultant_completion import ConsultantCompletionWorkflow
from caliburn.workflows.context_history import RoleContextHistory
from caliburn.workflows.job_files import JobFileWorkflow
from continuation_support import validate_prefix
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from pilot import HERE, dump, memory_probe, save_product
from preparation import ARMS
from psycopg import sql
from psycopg.conninfo import make_conninfo
from sqlalchemy.engine import URL

CONTAINER = "caliburn-jd-docker-test-postgres-1"
CLONE_NAME = "caliburn_compaction_main03"
SCHEMA = "eval_compaction_main_98af32b2461245c8a50f7ff816d984b8"
FILE_ID = UUID("8a207649-05df-4c06-a86c-83111c432e28")


def database_url(database: str) -> str:
    if database not in ("postgres", "caliburn_docker_test", CLONE_NAME):
        raise ValueError("Only named isolated databases permitted")
    inspected = json.loads(
        subprocess.check_output(["docker", "inspect", CONTAINER], text=True)
    )[0]
    if inspected["Name"] != "/" + CONTAINER or not inspected["State"]["Running"]:
        raise ValueError("Expected the running isolated research container")
    bindings = inspected["NetworkSettings"]["Ports"]["5432/tcp"]
    if not all(
        p["HostPort"] == "55441" and p["HostIp"] in ("127.0.0.1", "::1")
        for p in bindings
    ):
        raise ValueError("Isolated container port changed")
    environment = dict(
        entry.split("=", 1) for entry in inspected["Config"]["Env"] if "=" in entry
    )
    return URL.create(
        "postgresql",
        host="127.0.0.1",
        port=55441,
        username="caliburn",
        password=environment["POSTGRES_PASSWORD"],
        database=database,
    ).render_as_string(hide_password=False)


def cloned_database_url() -> str:
    return database_url(CLONE_NAME)


def create_clone() -> None:
    with psycopg.connect(
        database_url("postgres"), autocommit=True, connect_timeout=10
    ) as conn:
        if conn.execute(
            "SELECT count(*) FROM pg_stat_activity WHERE datname=%s",
            ("caliburn_docker_test",),
        ).fetchone()[0]:
            raise ValueError("Source DB has clients; do not interrupt them")
        if conn.execute(
            "SELECT 1 FROM pg_database WHERE datname=%s", (CLONE_NAME,)
        ).fetchone():
            raise ValueError("Clone exists; refusing to overwrite or rerun preparation")
        conn.execute(
            sql.SQL("CREATE DATABASE {} TEMPLATE {}").format(
                sql.Identifier(CLONE_NAME), sql.Identifier("caliburn_docker_test")
            )
        )


async def prepare(*, clone_already_created: bool = False) -> None:
    path = HERE / "continuation-preflight.json"
    if path.exists():
        raise ValueError("Preflight evidence already exists")
    hashes = validate_prefix(HERE / "main-02" / ARMS[0])
    if not clone_already_created:
        await asyncio.to_thread(create_clone)
    database = Database(DatabaseSettings(url=cloned_database_url(), schema=SCHEMA))
    lock = PostgresProcessLock(database.settings)
    try:
        await lock.acquire()
        files = JobFileWorkflow(database.sessions)
        interviews_before = await files.read_interviews(FILE_ID)
        if (
            len(interviews_before) != 103
            or interviews_before[-1].message.interview_sequence != 103
        ):
            raise ValueError("Clone does not hold exactly 51 completed exchanges")
        await save_product(
            database, files, FILE_ID, HERE / "continuation-product-before.json"
        )
        async with database.sessions() as session:
            active = await executions.read_current_consultant(session, FILE_ID)
            adopted = await history.read_adopted_context(
                session, FILE_ID, AgentRole.JOB_CONSULTANT
            )
        if (
            active is None
            or active.writer_id is None
            or active.status != ExecutionStatus.ACTIVE
        ):
            raise ValueError("Expected the stopped, still active e052 execution")
        if adopted is None or adopted.kind != HistoryWindowKind.PREPARED_HISTORY:
            raise ValueError("Expected the adopted safe pre-work compaction")
        writer = ExecutionWriter(active.scope, active.writer_id)
        async with AsyncPostgresSaver.from_conn_string(
            make_conninfo(database.settings.url, options=f"-c search_path={SCHEMA}"),
            serde=create_graph_serializer(allowed_types=MEMORY_CHECKPOINT_TYPES),
        ) as saver:
            items_before = await RoleContextHistory(
                database.sessions, writer, AgentRole.JOB_CONSULTANT, saver
            )._read_position(adopted)
        # No graph/model execution; use the existing product cancellation transaction.
        stopped = await ConsultantCompletionWorkflow(database.sessions).stop(
            writer, ExecutionStatus.FAILED
        )
        await save_product(
            database, files, FILE_ID, HERE / "continuation-product-after.json"
        )
        async with database.sessions() as session:
            head_after = await history.read_adopted_context(
                session, FILE_ID, AgentRole.JOB_CONSULTANT
            )
            current = await executions.read_current_consultant(session, FILE_ID)
        before = (HERE / "continuation-product-before.json").read_bytes()
        after = (HERE / "continuation-product-after.json").read_bytes()
        if before != after or head_after != adopted or current is not None:
            raise ValueError(
                "Cancellation changed formal results or adopted compaction"
            )
        dump(
            path,
            {
                "status": "verified",
                "database": CLONE_NAME,
                "schema": SCHEMA,
                "job_file_id": FILE_ID,
                "prefix_sha256": hashes,
                "formal_messages": 103,
                "events_completed": 51,
                "covered_through_sequence": 88,
                "discarded_execution": asdict(stopped),
                "adopted_context": asdict(adopted),
                "safe_native_items": memory_probe.public_document(items_before),
                "safe_native_sha256": hashlib.sha256(
                    json.dumps(
                        items_before, ensure_ascii=False, sort_keys=True
                    ).encode()
                ).hexdigest(),
                "formal_product_sha256": hashlib.sha256(before).hexdigest(),
                "formal_product_unchanged": True,
                "adopted_compaction_unchanged": True,
                "model_sends": 0,
                "original_database_mutations": 0,
            },
        )
        print(
            "Clone verified: 51 completed events retained; failed candidate discarded; safe compaction unchanged; no model sends.",
            flush=True,
        )
    finally:
        await lock.close()
        await database.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--clone-already-created",
        action="store_true",
        help="Continue only after a recorded failure before clone mutation",
    )
    args = parser.parse_args()
    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        runner.run(prepare(clone_already_created=args.clone_already_created))
