"""Run a separately authorized frozen batch once; never auto-resume a stopped run."""

import argparse
import asyncio
import json
import os
from contextlib import AsyncExitStack
from dataclasses import asdict
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import httpx2
from baseline_store import HERE, ROOT, seed_baseline
from caliburn.adapters.database import Database
from caliburn.adapters.database_settings import DatabaseSettings
from caliburn.adapters.graph_checkpointer import create_graph_serializer
from caliburn.adapters.openai_responses import create_responses_client
from caliburn.settings import ModelSettings
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from memory_fixture import seed_memory
from prepare_study import verify_inventory, verify_prepared
from psycopg.conninfo import make_conninfo
from study_batch import ARMS, ContinuationCase, run_schedule
from study_context import StudyArm
from study_guard import ResearchStop, StudyGuard
from study_manifest import claim_run, save_new, verify_files
from study_runner import StudyRunner
from study_storage import create_namespace, export_product


async def execute_batch(
    output: Path,
    *,
    database_url: str,
    api_key: str,
    batch_usd: Decimal,
    seconds: int,
    authorization_note: str,
    transport: httpx2.AsyncBaseTransport | None = None,
) -> None:
    manifest = verify_prepared(output)
    if (output / "started.json").exists():
        raise FileExistsError("This batch already started; no automatic paid restart")
    if not authorization_note.strip():
        raise ValueError("A separate human authorization record is required")
    # Constructing the guard performs limit validation but no outbound calls.
    guard = StudyGuard(
        output,
        batch_usd=batch_usd,
        seconds=seconds,
        prior_usd=Decimal(manifest["prior_cumulative_occupied_usd"]),
    )
    guard.frozen_policy = manifest
    settings = ModelSettings(api_key=api_key)
    claim_run(
        output,
        {
            "authorization_note": authorization_note,
            "batch_usd": str(batch_usd),
            "seconds": seconds,
            "prior_cumulative_occupied_usd": manifest["prior_cumulative_occupied_usd"],
        },
    )
    cases: list[ContinuationCase] = json.loads(
        (HERE / "continuation.json").read_text(encoding="utf-8")
    )["cases"]
    result: dict[str, object] = {"status": "initializing"}
    async with AsyncExitStack() as stack:
        try:
            runners = {}
            bindings = {}
            for arm in ARMS:
                schema = "eval_reset_" + uuid4().hex
                database_settings = DatabaseSettings(database_url, schema)
                # Save the identifier first; retain partial initialization for inspection.
                save_new(output / f"namespace-{arm}.json", {"schema": schema})
                await asyncio.to_thread(create_namespace, database_settings)
                database = Database(database_settings)
                stack.push_async_callback(database.close)
                file_id = await seed_baseline(database)
                snapshot_id = await seed_memory(database, file_id) if arm == "memory" else None
                save_new(
                    output / f"binding-{arm}.json",
                    {"schema": schema, "job_file_id": file_id, "snapshot_id": snapshot_id},
                )
                saver = await stack.enter_async_context(
                    AsyncPostgresSaver.from_conn_string(
                        make_conninfo(database_url, options=f"-c search_path={schema}"),
                        serde=create_graph_serializer(),
                    )
                )
                await saver.setup()
                # A single SDK client is shared across the three arms below.
                bindings[arm] = (database, file_id, snapshot_id, saver)
                await export_product(database, file_id, output / f"initial-{arm}.json")
            client = await stack.enter_async_context(
                create_responses_client(
                    api_key=api_key,
                    timeout_seconds=120,
                    http_client=httpx2.AsyncClient(
                        transport=transport,
                        follow_redirects=False,
                        event_hooks={"request": [guard.request], "response": [guard.response]},
                    ),
                )
            )
            for arm, (database, _, _, saver) in bindings.items():
                runners[arm] = StudyRunner(
                    database, saver, client, settings, manifest["instructions"][arm]
                )

            async def run_case(arm: StudyArm, case: ContinuationCase) -> None:
                # Concurrent code edits must not silently change a comparison mid-batch.
                verify_files(manifest["files"], root=ROOT)
                verify_inventory(manifest)
                guard.phase = {"arm": arm, "case_id": case["case_id"]}
                database, file_id, snapshot_id, _ = bindings[arm]
                exchange = await runners[arm].run(
                    file_id,
                    arm=arm,
                    employee_input=case["employee_input"],
                    snapshot_id=snapshot_id,
                )
                save_new(output / f"exchange-{arm}-{case['case_id']}.json", asdict(exchange))
                await export_product(
                    database, file_id, output / f"product-{arm}-{case['case_id']}.json"
                )

            def record(event: dict[str, object]) -> None:
                save_new(output / f"event-{event['arm']}-{event['case_id']}.json", event)

            async with asyncio.timeout(seconds):
                outcome = await run_schedule(cases, run_case, record)
            result = {
                "status": "completed" if not outcome["capacity_stops"] else "partial_capacity_stop",
                **outcome,
            }
        except ResearchStop as error:
            result = {"status": "stopped", "reason": str(error), "last_case": guard.phase}
        except TimeoutError:
            result = {"status": "stopped", "reason": "batch_deadline", "last_case": guard.phase}
        except Exception as error:
            # Credentials can occur in connection exceptions; keep only the type in public evidence.
            result = {
                "status": "failed",
                "error_type": type(error).__name__,
                "last_case": guard.phase,
            }
            raise
        finally:
            completed = {
                arm: [
                    case["case_id"]
                    for case in cases
                    if (output / f"exchange-{arm}-{case['case_id']}.json").is_file()
                ]
                for arm in ARMS
            }
            save_new(
                output / "result.json",
                {
                    **result,
                    "completed": completed,
                    "usage": guard.summary(),
                },
            )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--approved-batch-usd", type=Decimal, required=True)
    parser.add_argument("--approved-seconds", type=int, required=True)
    parser.add_argument("--authorization-note", required=True)
    args = parser.parse_args()
    try:
        with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as loop:
            loop.run(
                execute_batch(
                    args.output,
                    database_url=os.environ["CALIBURN_TEST_DATABASE_URL"],
                    api_key=os.environ["OPENAI_API_KEY"],
                    batch_usd=args.approved_batch_usd,
                    seconds=args.approved_seconds,
                    authorization_note=args.authorization_note,
                )
            )
    except Exception as error:
        print(json.dumps({"status": "failed", "error_type": type(error).__name__}))
        raise SystemExit(1) from None
    print((args.output / "result.json").read_text(encoding="utf-8"))
