"""Read-only execution evidence for scoped local inspection; no eligibility changes."""

from typing import cast
from uuid import UUID

from pydantic import JsonValue
from sqlalchemy import Select, Table, func, select, tuple_

from caliburn.features.executions import budget_persistence, history_persistence, persistence


def executions_projection(
    *, job_file_id: UUID | None, execution_id: UUID | None, limit: int | None, after: UUID | None
) -> Select[dict[str, JsonValue]]:
    table = cast(Table, persistence.ExecutionRecord.__table__)
    statement = select(func.to_jsonb(table.table_valued())).order_by(
        table.c.created_at, table.c.execution_id
    )
    if job_file_id is not None:
        statement = statement.where(table.c.job_file_id == job_file_id)
    if execution_id is not None:
        statement = statement.where(table.c.execution_id == execution_id)
    if after is not None:
        cursor = table.alias("diagnostic_cursor")
        boundary = select(cursor.c.created_at, cursor.c.execution_id).where(
            cursor.c.job_file_id == job_file_id, cursor.c.execution_id == after
        )
        statement = statement.where(
            tuple_(table.c.created_at, table.c.execution_id) > boundary.scalar_subquery()
        )
    return statement.limit(limit) if limit is not None else statement


def attempts_projection(job_file_id: UUID, execution_id: UUID) -> Select[dict[str, JsonValue]]:
    table = cast(Table, budget_persistence.OutboundAttemptRecord.__table__)
    execution = persistence.ExecutionRecord
    return (
        select(func.to_jsonb(table.table_valued()))
        .join(execution, execution.execution_id == table.c.execution_id)
        .where(execution.job_file_id == job_file_id, execution.execution_id == execution_id)
        .order_by(table.c.admitted_at, table.c.attempt_id)
    )


def bindings_projection(job_file_id: UUID, execution_id: UUID) -> Select[dict[str, JsonValue]]:
    table = cast(Table, history_persistence.ContextHistoryBindingRecord.__table__)
    return select(func.to_jsonb(table.table_valued())).where(
        table.c.job_file_id == job_file_id, table.c.execution_id == execution_id
    )


def budget_projection(job_file_id: UUID, execution_id: UUID) -> Select[dict[str, JsonValue]]:
    table = cast(Table, budget_persistence.ExecutionBudgetRecord.__table__)
    execution = persistence.ExecutionRecord
    return (
        select(func.to_jsonb(table.table_valued()))
        .join(execution, execution.execution_id == table.c.execution_id)
        .where(execution.job_file_id == job_file_id, execution.execution_id == execution_id)
    )
