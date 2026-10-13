"""Scoped Plan ledger coordinates; body reads use the fixed-position service."""

from typing import cast
from uuid import UUID

from pydantic import JsonValue, TypeAdapter
from sqlalchemy import Select, Table, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.features.interview_plans import persistence
from caliburn.features.interview_plans.models import PlanPosition, PlanSnapshot
from caliburn.features.interview_plans.service import read_at


def operations_projection(job_file_id: UUID, execution_id: UUID) -> Select[dict[str, JsonValue]]:
    table = cast(Table, persistence.PlanOperationRecord.__table__)
    return (
        select(func.to_jsonb(table.table_valued()))
        .where(table.c.job_file_id == job_file_id, table.c.execution_id == execution_id)
        .order_by(table.c.operation_id)
    )


def candidate_projection(job_file_id: UUID, execution_id: UUID) -> Select[dict[str, JsonValue]]:
    table = cast(Table, persistence.PlanCandidateRecord.__table__)
    return select(func.to_jsonb(table.table_valued())).where(
        table.c.job_file_id == job_file_id, table.c.execution_id == execution_id
    )


async def read_history(
    session: AsyncSession, job_file_id: UUID, execution_id: UUID, *, captured: UUID | None
) -> dict[str, JsonValue]:
    revisions = set(
        await session.scalars(
            select(persistence.PlanOperationRecord.revision_id).where(
                persistence.PlanOperationRecord.job_file_id == job_file_id,
                persistence.PlanOperationRecord.execution_id == execution_id,
            )
        )
    )
    adapter = TypeAdapter(PlanSnapshot)
    return {
        "revisions": [
            adapter.dump_python(
                await read_at(session, PlanPosition(job_file_id, execution_id, revision)),
                mode="json",
            )
            for revision in sorted(revisions)
        ],
        "missing": [str(captured)] if captured is not None and captured not in revisions else [],
    }
