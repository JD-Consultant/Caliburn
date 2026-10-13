"""Scoped reference operation evidence; diagnostics never select adoption eligibility."""

from typing import cast
from uuid import UUID

from pydantic import JsonValue
from sqlalchemy import Select, Table, func, select

from caliburn.features.occupation_references import persistence


def operations_projection(job_file_id: UUID, execution_id: UUID) -> Select[dict[str, JsonValue]]:
    table = cast(Table, persistence.ReferenceOperationRecord.__table__)
    return (
        select(func.to_jsonb(table.table_valued()))
        .where(table.c.job_file_id == job_file_id, table.c.execution_id == execution_id)
        .order_by(table.c.operation_id)
    )


def candidate_projection(job_file_id: UUID, execution_id: UUID) -> Select[dict[str, JsonValue]]:
    table = cast(Table, persistence.ReferenceCandidateRecord.__table__)
    return select(func.to_jsonb(table.table_valued())).where(
        table.c.job_file_id == job_file_id, table.c.execution_id == execution_id
    )
