"""Scoped immutable Memory evidence for local diagnostics; no publication decisions."""

from typing import cast
from uuid import UUID

from pydantic import JsonValue, TypeAdapter
from sqlalchemy import Select, Table, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.features.work_memory import (
    batch_persistence,
    candidate_operations,
    position_persistence,
)
from caliburn.features.work_memory.revision_service import read_fixed_revisions
from caliburn.features.work_memory.revisions import MemoryObjectRevision, MemoryRevisionReference


def batch_projection(job_file_id: UUID, execution_id: UUID) -> Select[dict[str, JsonValue]]:
    table = cast(Table, batch_persistence.MemoryBatchRecord.__table__)
    return select(func.to_jsonb(table.table_valued())).where(
        table.c.job_file_id == job_file_id, table.c.execution_id == execution_id
    )


def operations_projection(job_file_id: UUID, execution_id: UUID) -> Select[dict[str, JsonValue]]:
    table = cast(Table, batch_persistence.MemoryOperationRecord.__table__)
    return (
        select(func.to_jsonb(table.table_valued()))
        .where(table.c.job_file_id == job_file_id, table.c.execution_id == execution_id)
        .order_by(table.c.command_id)
    )


def snapshots_projection(job_file_id: UUID, execution_id: UUID) -> Select[dict[str, JsonValue]]:
    table = cast(Table, batch_persistence.MemorySnapshotRecord.__table__)
    return (
        select(func.to_jsonb(table.table_valued()))
        .where(table.c.job_file_id == job_file_id, table.c.execution_id == execution_id)
        .order_by(table.c.created_at, table.c.snapshot_id)
    )


async def read_history(
    session: AsyncSession, job_file_id: UUID, execution_id: UUID, *, snapshot_id: UUID | None
) -> dict[str, JsonValue]:
    """Resolve only this execution's positions and its captured publication, using owner codecs."""
    positions: set[UUID] = set()
    missing: list[JsonValue] = []
    if snapshot_id is not None:
        snapshot = await batch_persistence.read_snapshot(session, job_file_id, snapshot_id)
        if snapshot is None:
            missing.append(f"snapshot:{snapshot_id}")
        else:
            positions.add(snapshot.position_id)
    batch = await batch_persistence.read_batch(session, job_file_id, execution_id)
    if batch is not None:
        positions.update((batch.base_position_id, batch.current_position_id))
    operations = await session.scalars(
        select(batch_persistence.MemoryOperationRecord).where(
            batch_persistence.MemoryOperationRecord.job_file_id == job_file_id,
            batch_persistence.MemoryOperationRecord.execution_id == execution_id,
        )
    )
    for operation in operations:
        request, result = operation.request_payload, operation.result_payload
        for payload in (request, result):
            if not isinstance(payload, dict):
                continue
            candidate = payload.get("position", payload)
            if isinstance(candidate, dict) and "position_id" in candidate:
                position = candidate_operations.result_position(candidate)
                if (position.job_file_id, position.execution_id) != (job_file_id, execution_id):
                    raise ValueError("A saved Memory position belongs to another execution")
                positions.add(position.position_id)
    selected: list[JsonValue] = []
    references: set[MemoryRevisionReference] = set()
    for position_id in sorted(positions):
        members = await position_persistence.read_position_members(
            session, job_file_id, position_id
        )
        if members is None:
            missing.append(f"position:{position_id}")
            continue
        references.update(members)
        selected.append(
            {
                "position_id": str(position_id),
                "members": [
                    {"object_id": str(ref.object_id), "revision_id": str(ref.revision_id)}
                    for ref in members
                ],
            }
        )
    revisions = await read_fixed_revisions(
        session, job_file_id=job_file_id, references=frozenset(references)
    )
    adapter = TypeAdapter(MemoryObjectRevision)
    return {
        "positions": selected,
        "revisions": [
            adapter.dump_python(revisions[ref], mode="json") for ref in sorted(revisions)
        ],
        "missing": missing,
    }
