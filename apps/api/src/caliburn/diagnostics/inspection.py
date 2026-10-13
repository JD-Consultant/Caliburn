"""Assemble scoped originals in one read-only database snapshot; never execute work.

Any stays within this JSON export boundary, combining already scoped owner projections
and safe native JSON. The complete report is validated before it leaves this module.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from pydantic import JsonValue, TypeAdapter
from sqlalchemy import text

from caliburn.adapters.database import Database, consistent_read_session
from caliburn.adapters.database_settings import DatabaseSettings
from caliburn.diagnostics.checkpoints import read_checkpoint_records
from caliburn.diagnostics.control_history import collect_control_history
from caliburn.diagnostics.projection import (
    collect_analysis_contexts,
    collect_compactions,
    collect_initial_context,
    collect_steps,
    collect_tool_calls,
    redact,
)
from caliburn.features.executions import diagnostics_queries as executions
from caliburn.features.executions import history
from caliburn.features.executions.history_models import AgentRole
from caliburn.features.executions.models import ExecutionKind, ExecutionScope
from caliburn.features.interview_plans import diagnostics_queries as plans
from caliburn.features.interviews import diagnostics_queries as interviews
from caliburn.features.job_description import diagnostics_queries as jd
from caliburn.features.occupation_references import diagnostics_queries as references
from caliburn.features.work_memory import diagnostics_queries as memory

_DOCUMENTS = TypeAdapter(list[dict[str, JsonValue]])


async def read_diagnostics(
    settings: DatabaseSettings,
    *,
    job_file_id: UUID | None = None,
    execution_id: UUID | None = None,
    request_id: UUID | None = None,
    full: bool = False,
    limit: int | None = 100,
    after: UUID | None = None,
) -> list[dict[str, JsonValue]]:
    """File scope lists rounds; execution scope lists Steps; full explicitly includes bodies."""
    if (job_file_id is None) == (execution_id is None):
        raise ValueError("Select exactly one job_file_id or execution_id")
    if request_id is not None and execution_id is None:
        raise ValueError("A request selector requires execution_id")
    if after is not None and job_file_id is None:
        raise ValueError("A round cursor requires job_file_id")
    if limit is not None and limit < 1:
        raise ValueError("The round limit must be positive")
    database = Database(settings)
    started = datetime.now(UTC).isoformat()
    try:
        async with consistent_read_session(database.sessions) as session:
            await session.execute(text("SET LOCAL statement_timeout = '60s'"))
            await session.execute(text("SET LOCAL lock_timeout = '5s'"))
            rows = list(
                await session.scalars(
                    executions.executions_projection(
                        job_file_id=job_file_id,
                        execution_id=execution_id,
                        limit=limit if job_file_id is not None and not full else None,
                        after=after,
                    )
                )
            )
            documents: list[dict[str, Any]] = []
            for execution in rows:
                file_id, run_id = (
                    UUID(str(execution["job_file_id"])),
                    UUID(str(execution["execution_id"])),
                )
                detailed = execution_id is not None or full
                records = (
                    await read_checkpoint_records(session, job_file_id=file_id, execution_id=run_id)
                    if detailed
                    else []
                )
                steps = collect_steps(records)
                if request_id is not None:
                    steps = [step for step in steps if step["request_id"] == str(request_id)]
                document: dict[str, Any] = {
                    "execution": execution,
                    "steps": steps,
                    "tool_calls": collect_tool_calls(steps),
                    "compactions": collect_compactions(records),
                    "control_history": collect_control_history(records),
                    "attempts": list(
                        await session.scalars(executions.attempts_projection(file_id, run_id))
                    ),
                    "context_bindings": list(
                        await session.scalars(executions.bindings_projection(file_id, run_id))
                    ),
                    "budget": await session.scalar(executions.budget_projection(file_id, run_id)),
                }
                if detailed:
                    manual_operations: list[dict[str, JsonValue]] = []
                    jd_candidate = await session.scalar(jd.candidate_projection(file_id, run_id))
                    if (
                        execution["kind"] == ExecutionKind.CONSULTANT_TURN
                        and jd_candidate is not None
                        and any(
                            binding["role"] == AgentRole.JOB_CONSULTANT
                            for binding in document["context_bindings"]
                        )
                    ):
                        previous = await history.read_previous_completed_execution(
                            session,
                            ExecutionScope(file_id, run_id, ExecutionKind.CONSULTANT_TURN),
                            AgentRole.JOB_CONSULTANT,
                        )
                        manual_operations = await jd.read_manual_operations_projection(
                            session,
                            file_id,
                            run_id,
                            previous_completed_execution_id=previous.execution_id
                            if previous
                            else None,
                        )
                    document["captured_analysis_contexts"] = collect_analysis_contexts(records)
                    document["captured_initial_context"] = collect_initial_context(records)
                    document["interviews"] = list(
                        await session.scalars(
                            interviews.exchange_projection(file_id, run_id, include_text=full)
                        )
                    )
                    document["operations"] = {
                        "jd": [
                            *manual_operations,
                            *list(await session.scalars(jd.operations_projection(file_id, run_id))),
                        ],
                        "memory": list(
                            await session.scalars(memory.operations_projection(file_id, run_id))
                        ),
                        "plan": list(
                            await session.scalars(plans.operations_projection(file_id, run_id))
                        ),
                        "references": list(
                            await session.scalars(references.operations_projection(file_id, run_id))
                        ),
                    }
                    for call in document["tool_calls"]:
                        receipts = (
                            [
                                {"owner": owner, "operation_id": call["operation_id"]}
                                for owner, operations in document["operations"].items()
                                for operation in operations
                                if operation.get("command_id", operation.get("operation_id"))
                                == call["operation_id"]
                            ]
                            if call["operation_id"] is not None
                            else []
                        )
                        if receipts:
                            call.update(receipt_state="recorded", receipts=receipts)
                    document["candidates"] = {
                        "jd": jd_candidate,
                        "memory": await session.scalar(memory.batch_projection(file_id, run_id)),
                        "plan": await session.scalar(plans.candidate_projection(file_id, run_id)),
                        "references": await session.scalar(
                            references.candidate_projection(file_id, run_id)
                        ),
                    }
                    document["memory_publications"] = list(
                        await session.scalars(memory.snapshots_projection(file_id, run_id))
                    )
                    for boundary in document["compactions"]:
                        boundary["role_reference_state"] = (
                            "referenced"
                            if any(
                                binding.get(f"{kind}_thread_id") == boundary["thread_id"]
                                and binding.get(f"{kind}_checkpoint_id")
                                == boundary.get("adopted_checkpoint_id")
                                for binding in document["context_bindings"]
                                for kind in ("base", "prepared", "completed")
                            )
                            else "not_referenced"
                        )
                    if full:
                        captured = document["captured_initial_context"]
                        binding = captured["binding"] if captured is not None else {}
                        document["versions"] = {
                            "memory": await memory.read_history(
                                session,
                                file_id,
                                run_id,
                                snapshot_id=UUID(binding["snapshot_id"])
                                if binding.get("snapshot_id")
                                else None,
                            ),
                            "jd": await jd.read_history(
                                session,
                                file_id,
                                run_id,
                                captured=frozenset(
                                    UUID(binding[key])
                                    for key in (
                                        "candidate_base_revision_id",
                                        "candidate_revision_id",
                                    )
                                    if binding.get(key)
                                ),
                                manual_operations=manual_operations,
                            ),
                            "plan": await plans.read_history(
                                session,
                                file_id,
                                run_id,
                                captured=UUID(binding["plan_base_revision_id"])
                                if binding.get("plan_base_revision_id")
                                else None,
                            ),
                        }
                if not full:
                    document["steps"] = [
                        {
                            key: value
                            for key, value in step.items()
                            if key not in {"request", "response", "tool_results"}
                        }
                        for step in steps
                    ]
                    document.pop("captured_initial_context", None)
                    document.pop("captured_analysis_contexts", None)
                    # Original operation bodies are explicit full-mode content too.
                    document.pop("operations", None)
                    document["tool_calls"] = [
                        {
                            key: value
                            for key, value in call.items()
                            if key not in {"arguments", "output", "receipts"}
                        }
                        for call in document["tool_calls"]
                    ]
                    document["compactions"] = [
                        {
                            key: value
                            for key, value in compact.items()
                            if key not in {"request", "compaction"}
                        }
                        for compact in document["compactions"]
                    ]
                documents.append(document)
    finally:
        await database.close()
    ended = datetime.now(UTC).isoformat()
    for document in documents:
        document["read"] = {
            "started_at": started,
            "finished_at": ended,
            "isolation": "repeatable_read",
            "read_only": True,
            "full": full,
        }
    return _DOCUMENTS.validate_python(redact(documents))
