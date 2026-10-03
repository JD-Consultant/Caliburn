"""Memory stage handoff, branch restore and publication; no model or checkpoint logic."""

from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.features.work_memory import batch_persistence, position_persistence
from caliburn.features.work_memory import candidate_operations as operations
from caliburn.features.work_memory import candidate_queries as queries
from caliburn.features.work_memory.candidate_service import require_base
from caliburn.features.work_memory.candidates import (
    MemoryBatchPosition,
    MemoryCandidateStateError,
    MemorySnapshot,
)
from caliburn.features.work_memory.revision_service import write_object_revision
from caliburn.features.work_memory.revisions import MemoryLayer, MemoryRevisionReference


async def _recover_control(
    session: AsyncSession,
    position: MemoryBatchPosition,
    command_id: UUID,
    kind: str,
    payload: dict[str, object],
) -> MemoryBatchPosition | None:
    original = await operations.recover(
        session, position.job_file_id, position.execution_id, command_id, kind, payload
    )
    if original is None:
        return None
    result = operations.result_position(original)
    record = await batch_persistence.read_batch(
        session, position.job_file_id, position.execution_id
    )
    generation = result.generation_id if kind == "restore" else position.generation_id
    if record is None or record.generation_id != generation:
        raise MemoryCandidateStateError("The saved control result belongs to a superseded branch")
    return result


async def handoff(
    session: AsyncSession, position: MemoryBatchPosition, command_id: UUID
) -> MemoryBatchPosition:
    if position.phase != MemoryLayer.WORK_SITUATION:
        raise MemoryCandidateStateError("Memory handoff only advances situations to understandings")
    payload: dict[str, object] = {"position": operations.position_fields(position)}
    prior = await _recover_control(session, position, command_id, "handoff", payload)
    if prior is not None:
        return prior
    record = await queries.require_stage(session, position, exact_position=True)
    await require_base(session, record)
    record.phase = MemoryLayer.WORK_UNDERSTANDING.value
    record.stage_id = uuid4()
    result = queries.batch_position(record)
    await operations.record_result(session, result, command_id, "handoff", payload)
    return result


async def restore(
    session: AsyncSession,
    position: MemoryBatchPosition,
    target: MemoryBatchPosition,
    command_id: UUID,
) -> MemoryBatchPosition:
    if (target.job_file_id, target.execution_id) != (position.job_file_id, position.execution_id):
        raise MemoryCandidateStateError("Restore requires a position from the same batch")
    payload: dict[str, object] = {
        "position": operations.position_fields(position),
        "target": operations.position_fields(target),
    }
    prior = await _recover_control(session, position, command_id, "restore", payload)
    if prior is not None:
        return prior
    record = await queries.require_stage(session, position, exact_position=True)
    await require_base(session, record)
    if not await batch_persistence.has_recorded_position(
        session, position.job_file_id, position.execution_id, operations.position_fields(target)
    ):
        raise MemoryCandidateStateError("Restore requires an authentic retained stage position")
    if not await position_persistence.is_position_ancestor(
        session,
        position.job_file_id,
        target.position_id,
        position.position_id,
        record.base_position_id,
    ):
        raise MemoryCandidateStateError("Restore cannot adopt a foreign or abandoned position")
    record.current_position_id = target.position_id
    record.phase = target.phase.value
    record.generation_id = uuid4()
    record.stage_id = uuid4()
    result = queries.batch_position(record)
    await operations.record_result(session, result, command_id, "restore", payload)
    return result


async def recover_discard(
    session: AsyncSession, position: MemoryBatchPosition, command_id: UUID
) -> bool:
    payload: dict[str, object] = {"position": operations.position_fields(position)}
    return await _recover_control(session, position, command_id, "discard", payload) is not None


async def discard(session: AsyncSession, position: MemoryBatchPosition, command_id: UUID) -> None:
    if await recover_discard(session, position, command_id):
        return
    record = await queries.require_stage(session, position, exact_position=True)
    record.status = "discarded"
    await operations.record_result(
        session, position, command_id, "discard", {"position": operations.position_fields(position)}
    )


async def recover_publication(
    session: AsyncSession, position: MemoryBatchPosition, command_id: UUID
) -> MemorySnapshot | None:
    payload: dict[str, object] = {"position": operations.position_fields(position)}
    original = await operations.recover(
        session, position.job_file_id, position.execution_id, command_id, "publish", payload
    )
    if original is None:
        return None
    return await queries.read_snapshot(
        session, position.job_file_id, operations.stored_uuid(original, "snapshot_id")
    )


async def publish(
    session: AsyncSession, position: MemoryBatchPosition, command_id: UUID
) -> MemorySnapshot:
    """Caller supplies B2's actual completion and atomically finishes execution with this result."""
    prior = await recover_publication(session, position, command_id)
    if prior is not None:
        return prior
    record = await queries.require_stage(session, position, exact_position=True)
    if position.phase != MemoryLayer.WORK_UNDERSTANDING:
        raise MemoryCandidateStateError("Only the current understanding stage can complete Memory")
    await require_base(session, record)
    members = await queries.read_members(session, position.job_file_id, position.position_id)
    fixed_members = members.copy()
    for reference in members.values():
        revision = await queries.read_selected(
            session, position.job_file_id, members, reference.object_id
        )
        if revision.layer != MemoryLayer.WORK_UNDERSTANDING:
            continue
        fixed_sources = frozenset(
            members[source.object_id] for source in revision.work_situation_references
        )
        if fixed_sources == revision.work_situation_references:
            continue
        fixed = await write_object_revision(
            session,
            queries.source_window(record),
            layer=revision.layer,
            content=revision.content,
            previous=reference,
            work_situation_references=fixed_sources,
        )
        fixed_members[fixed.object_id] = MemoryRevisionReference(fixed.object_id, fixed.revision_id)
    if fixed_members != members:
        next_position_id = uuid4()
        await position_persistence.insert_position(
            session,
            position.job_file_id,
            next_position_id,
            position.position_id,
            tuple(sorted(fixed_members.values())),
        )
        record.current_position_id = next_position_id
    snapshot_id = uuid4()
    snapshot = batch_persistence.MemorySnapshotRecord(
        job_file_id=position.job_file_id,
        snapshot_id=snapshot_id,
        execution_id=position.execution_id,
        position_id=record.current_position_id,
        through_source_id=record.through_source_id,
        covered_through_sequence=record.through_sequence,
    )
    session.add(snapshot)
    await session.flush()
    await batch_persistence.set_head(session, position.job_file_id, snapshot_id)
    record.status = "published"
    await operations.record_result(
        session,
        queries.batch_position(record),
        command_id,
        "publish",
        {"position": operations.position_fields(position)},
        snapshot_id=snapshot_id,
    )
    return queries.snapshot_value(snapshot)
