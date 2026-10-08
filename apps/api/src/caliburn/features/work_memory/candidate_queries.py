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
from caliburn.features.work_memory.read_models import MemoryObjectMetadata
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


async def read_position_selection(
    session: AsyncSession,
    job_file_id: UUID,
    position_id: UUID,
    object_ids: tuple[UUID, ...],
) -> dict[UUID, MemoryObjectMetadata]:
    """在固定封存位置內取得有限物件標頭；位置不可讀時不回傳空結果。"""
    selected = await position_persistence.read_position_selection(
        session, job_file_id, position_id, object_ids
    )
    if selected is None:
        raise MemoryCandidateStateError("The fixed candidate position is unavailable")
    return {item.object_id: item for item in selected}


async def read_position_object(
    session: AsyncSession, job_file_id: UUID, position_id: UUID, object_id: UUID
) -> MemoryObjectRevision:
    """只讀一個選中的物件；正文沿既有封存版本 owner 取得。"""
    selected = await read_position_selection(session, job_file_id, position_id, (object_id,))
    item = selected.get(object_id)
    if item is None:
        raise MemoryRevisionNotFoundError("The object is not selected at this position")
    return await read_fixed_revision(
        session,
        job_file_id=job_file_id,
        reference=MemoryRevisionReference(item.object_id, item.revision_id),
    )


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
    # 先固定一次位置，正文與來源導覽共用這個位置。
    revision = await read_position_object(
        session, stage.job_file_id, record.current_position_id, object_id
    )
    if revision.layer != layer:
        raise MemoryRevisionNotFoundError("The object does not belong to the selected layer")
    sources = (
        await read_position_selection(
            session,
            stage.job_file_id,
            record.current_position_id,
            tuple(ref.object_id for ref in revision.work_situation_references),
        )
        if revision.work_situation_references
        else {}
    )
    if len(sources) != len(revision.work_situation_references):
        raise MemoryRevisionNotFoundError("A source binding is unavailable in the read view")
    return MemoryCandidateObject(
        revision.object_id,
        revision.revision_id,
        revision.layer,
        revision.content,
        revision.interview_references,
        frozenset(
            MemoryRevisionReference(item.object_id, item.revision_id) for item in sources.values()
        ),
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
    return await read_position_object(session, job_file_id, snapshot.position_id, object_id)


async def read_snapshot_map(
    session: AsyncSession, job_file_id: UUID, snapshot_id: UUID, layer: MemoryLayer
) -> tuple[MemoryMapEntry, ...]:
    snapshot = await read_snapshot(session, job_file_id, snapshot_id)
    return await position_persistence.read_position_map(
        session, job_file_id, snapshot.position_id, layer
    )
