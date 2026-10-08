"""Current candidate bindings and immutable publication reads use distinct projections."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.features.work_memory import batch_persistence, position_persistence
from caliburn.features.work_memory.candidates import (
    MemoryBatchPosition,
    MemoryCandidateObject,
    MemoryCandidateStateError,
    MemorySnapshot,
    require_layer_read,
)
from caliburn.features.work_memory.models import MemoryMapEntry, MemorySourceWindow
from caliburn.features.work_memory.revision_service import read_fixed_revision
from caliburn.features.work_memory.revisions import (
    MemoryLayer,
    MemoryObjectRevision,
    MemoryRevisionNotFoundError,
    MemoryRevisionReference,
)


def batch_position(record: batch_persistence.MemoryBatchRecord) -> MemoryBatchPosition:
    return MemoryBatchPosition(
        record.job_file_id,
        record.execution_id,
        record.generation_id,
        record.stage_id,
        MemoryLayer(record.phase),
        record.current_position_id,
    )


def source_window(record: batch_persistence.MemoryBatchRecord) -> MemorySourceWindow:
    return MemorySourceWindow(
        record.job_file_id,
        record.through_source_id,
        record.covered_through_sequence,
        record.through_sequence,
    )


def snapshot_value(record: batch_persistence.MemorySnapshotRecord) -> MemorySnapshot:
    return MemorySnapshot(
        record.job_file_id,
        record.snapshot_id,
        record.position_id,
        record.through_source_id,
        record.covered_through_sequence,
    )


async def require_stage(
    session: AsyncSession, expected: MemoryBatchPosition, *, exact_position: bool = False
) -> batch_persistence.MemoryBatchRecord:
    record = await batch_persistence.read_batch(
        session, expected.job_file_id, expected.execution_id
    )
    if record is None or record.status != "open":
        raise MemoryCandidateStateError("No open Memory candidate in this execution")
    current = batch_position(record)
    if (
        current.generation_id != expected.generation_id
        or current.stage_id != expected.stage_id
        or current.phase != expected.phase
        or (exact_position and current.position_id != expected.position_id)
    ):
        raise MemoryCandidateStateError("The candidate stage or position was superseded")
    return record


async def read_members(
    session: AsyncSession, job_file_id: UUID, position_id: UUID
) -> dict[UUID, MemoryRevisionReference]:
    references = await position_persistence.read_position_members(session, job_file_id, position_id)
    if references is None:
        raise MemoryCandidateStateError("The fixed candidate position is unavailable")
    return {reference.object_id: reference for reference in references}


async def read_selected(
    session: AsyncSession,
    job_file_id: UUID,
    members: dict[UUID, MemoryRevisionReference],
    object_id: UUID,
) -> MemoryObjectRevision:
    reference = members.get(object_id)
    if reference is None:
        raise MemoryRevisionNotFoundError("The object is not selected at this position")
    return await read_fixed_revision(session, job_file_id=job_file_id, reference=reference)


async def read_candidate_map(
    session: AsyncSession, stage: MemoryBatchPosition, layer: MemoryLayer
) -> tuple[MemoryMapEntry, ...]:
    require_layer_read(stage.phase, layer)
    record = await require_stage(session, stage)
    return await position_persistence.read_position_map(
        session, stage.job_file_id, record.current_position_id, layer
    )


async def read_candidate_object(
    session: AsyncSession, stage: MemoryBatchPosition, layer: MemoryLayer, object_id: UUID
) -> MemoryCandidateObject:
    require_layer_read(stage.phase, layer)
    record = await require_stage(session, stage)
    # Capture one immutable position before resolving any reference. Never reread latest.
    members = await read_members(session, stage.job_file_id, record.current_position_id)
    revision = await read_selected(session, stage.job_file_id, members, object_id)
    if revision.layer != layer:
        raise MemoryRevisionNotFoundError("The object does not belong to the selected layer")
    return MemoryCandidateObject(
        revision.object_id,
        revision.revision_id,
        revision.layer,
        revision.content,
        revision.interview_references,
        frozenset(members[ref.object_id] for ref in revision.work_situation_references),
    )


async def read_snapshot(
    session: AsyncSession, job_file_id: UUID, snapshot_id: UUID
) -> MemorySnapshot:
    record = await batch_persistence.read_snapshot(session, job_file_id, snapshot_id)
    if record is None:
        raise MemoryRevisionNotFoundError("Published Memory snapshot not found in this job file")
    return snapshot_value(record)


async def read_latest_snapshot(session: AsyncSession, job_file_id: UUID) -> MemorySnapshot | None:
    head = await batch_persistence.read_head(session, job_file_id)
    return snapshot_value(head) if head is not None else None


async def read_snapshot_object(
    session: AsyncSession, job_file_id: UUID, snapshot_id: UUID, object_id: UUID
) -> MemoryObjectRevision:
    snapshot = await read_snapshot(session, job_file_id, snapshot_id)
    members = await read_members(session, job_file_id, snapshot.position_id)
    return await read_selected(session, job_file_id, members, object_id)


async def read_snapshot_map(
    session: AsyncSession, job_file_id: UUID, snapshot_id: UUID, layer: MemoryLayer
) -> tuple[MemoryMapEntry, ...]:
    snapshot = await read_snapshot(session, job_file_id, snapshot_id)
    return await position_persistence.read_position_map(
        session, job_file_id, snapshot.position_id, layer
    )
