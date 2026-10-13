"""Original JD operation receipts and candidate coordinates, never today's body as history."""

from typing import cast
from uuid import UUID

from pydantic import JsonValue, TypeAdapter
from sqlalchemy import Select, Table, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.features.job_description import candidate_persistence, persistence
from caliburn.features.job_description.change_comparison import JdChangeSnapshot
from caliburn.features.job_description.change_queries import (
    JdChangeHistoryUnavailableError,
    read_change_snapshot,
    read_manual_change_base,
)


def candidate_projection(job_file_id: UUID, execution_id: UUID) -> Select[dict[str, JsonValue]]:
    table = cast(Table, candidate_persistence.JdCandidateRecord.__table__)
    return select(func.to_jsonb(table.table_valued())).where(
        table.c.job_file_id == job_file_id, table.c.execution_id == execution_id
    )


def operations_projection(job_file_id: UUID, execution_id: UUID) -> Select[dict[str, JsonValue]]:
    table = cast(Table, persistence.JdOperationRecord.__table__)
    return (
        select(func.to_jsonb(table.table_valued()))
        .where(table.c.job_file_id == job_file_id, table.c.candidate_execution_id == execution_id)
        .order_by(table.c.created_at, table.c.command_id)
    )


async def read_manual_operations_projection(
    session: AsyncSession,
    job_file_id: UUID,
    execution_id: UUID,
    *,
    previous_completed_execution_id: UUID | None,
) -> list[dict[str, JsonValue]]:
    candidate = await candidate_persistence.read_candidate(session, job_file_id, execution_id)
    if candidate is None:
        return []
    base, since = await read_manual_change_base(
        session, job_file_id, previous_completed_execution_id
    )
    chain = dict(
        await persistence.read_revision_interval(
            session, job_file_id, base_revision_id=base, end_revision_id=candidate.base_revision_id
        )
    )
    if base not in chain:
        raise JdChangeHistoryUnavailableError("The fixed manual JD base is not a retained ancestor")
    records = await persistence.read_manual_operations(
        session, job_file_id, tuple(chain), created_before=candidate.created_at, created_since=since
    )
    effects = {
        record.result_revision_id: record.expected_revision_id
        for record in records
        if record.result_revision_id != record.expected_revision_id
    }
    if any(
        effects.get(revision) != parent for revision, parent in chain.items() if revision != base
    ):
        raise JdChangeHistoryUnavailableError(
            "A formal revision lacks its original manual operation"
        )
    table = cast(Table, persistence.JdOperationRecord.__table__)
    return list(
        await session.scalars(
            select(func.to_jsonb(table.table_valued()))
            .where(
                table.c.job_file_id == job_file_id,
                table.c.command_id.in_(record.command_id for record in records),
            )
            .order_by(table.c.created_at, table.c.command_id)
        )
    )


async def read_history(
    session: AsyncSession,
    job_file_id: UUID,
    execution_id: UUID,
    *,
    captured: frozenset[UUID],
    manual_operations: list[dict[str, JsonValue]],
) -> dict[str, JsonValue]:
    revisions = set(captured)
    for manual_operation in manual_operations:
        revisions.update(
            (
                UUID(str(manual_operation["expected_revision_id"])),
                UUID(str(manual_operation["result_revision_id"])),
            )
        )
    candidate = await candidate_persistence.read_candidate(session, job_file_id, execution_id)
    if candidate is not None:
        revisions.update((candidate.base_revision_id, candidate.current_revision_id))
    operations = await session.scalars(
        select(persistence.JdOperationRecord).where(
            persistence.JdOperationRecord.job_file_id == job_file_id,
            persistence.JdOperationRecord.candidate_execution_id == execution_id,
        )
    )
    for operation in operations:
        revisions.update((operation.expected_revision_id, operation.result_revision_id))
    available = (
        set(
            await session.scalars(
                select(persistence.JdRevisionRecord.revision_id).where(
                    persistence.JdRevisionRecord.job_file_id == job_file_id,
                    persistence.JdRevisionRecord.revision_id.in_(revisions),
                )
            )
        )
        if revisions
        else set()
    )
    adapter = TypeAdapter(JdChangeSnapshot)
    return {
        "revisions": [
            {
                "revision_id": str(revision),
                "snapshot": adapter.dump_python(
                    await read_change_snapshot(session, job_file_id, revision), mode="json"
                ),
            }
            for revision in sorted(available)
        ],
        "missing": [str(revision) for revision in sorted(revisions - available)],
    }
