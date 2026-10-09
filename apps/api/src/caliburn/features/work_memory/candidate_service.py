"""Candidate content changes join the caller's qualified, short Memory transaction."""

from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.features.work_memory import batch_persistence, position_persistence
from caliburn.features.work_memory import candidate_operations as operations
from caliburn.features.work_memory import candidate_queries as queries
from caliburn.features.work_memory.candidates import (
    CreateMemoryObject,
    DeleteMemoryObject,
    MemoryBatchPosition,
    MemoryCandidateStateError,
    MemoryCommandConflictError,
    MemoryEdit,
    MemoryEditResult,
    ReviseMemoryObject,
    require_layer_write,
)
from caliburn.features.work_memory.changes import (
    apply_content_changes,
    apply_reference_changes,
    require_unique_title,
)
from caliburn.features.work_memory.models import MemoryContent
from caliburn.features.work_memory.revision_service import (
    read_fixed_headers,
    rebind_understanding_sources,
    write_object_revision,
)
from caliburn.features.work_memory.revisions import (
    MemoryLayer,
    MemoryObjectRevision,
    MemoryRevisionNotFoundError,
    MemoryRevisionReference,
)
from caliburn.features.work_memory.sources import bind_memory_source_window, read_reference_headers


async def start_candidate(
    session: AsyncSession, job_file_id: UUID, execution_id: UUID, through_source_id: UUID
) -> MemoryBatchPosition | None:
    existing = await batch_persistence.read_batch(session, job_file_id, execution_id)
    if existing is not None:
        if existing.through_source_id != through_source_id:
            raise MemoryCommandConflictError("The original batch source boundary cannot change")
        if existing.status != "open":
            raise MemoryCandidateStateError("A finished candidate cannot restart")
        return queries.batch_position(existing)
    head = await batch_persistence.read_head(session, job_file_id)
    window = await bind_memory_source_window(
        session,
        job_file_id=job_file_id,
        through_source_id=through_source_id,
        covered_through_sequence=head.covered_through_sequence if head is not None else 0,
    )
    if window is None:
        session.add(
            batch_persistence.MemoryOperationRecord(
                job_file_id=job_file_id,
                execution_id=execution_id,
                command_id=execution_id,
                kind="start_covered",
                request_payload={"through_source_id": str(through_source_id)},
                result_payload={"status": "already_covered"},
            )
        )
        await session.flush()
        return None
    if head is None:
        base_position_id = uuid4()
        await position_persistence.insert_position(session, job_file_id, base_position_id, None, ())
    else:
        base_position_id = head.position_id
    record = batch_persistence.MemoryBatchRecord(
        job_file_id=job_file_id,
        execution_id=execution_id,
        base_snapshot_id=head.snapshot_id if head is not None else None,
        base_position_id=base_position_id,
        current_position_id=base_position_id,
        generation_id=uuid4(),
        stage_id=uuid4(),
        phase=MemoryLayer.WORK_SITUATION.value,
        status="open",
        through_source_id=through_source_id,
        covered_through_sequence=window.covered_through_sequence,
        through_sequence=window.through_sequence,
    )
    session.add(record)
    await session.flush()
    position = queries.batch_position(record)
    await operations.record_result(
        session, position, execution_id, "start", {"through_source_id": str(through_source_id)}
    )
    return position


async def recover_covered_start(
    session: AsyncSession, job_file_id: UUID, execution_id: UUID, through_source_id: UUID
) -> bool:
    original = await batch_persistence.read_operation(session, job_file_id, execution_id)
    if original is None or original.kind == "start":
        return False
    result = await operations.recover(
        session,
        job_file_id,
        execution_id,
        execution_id,
        "start_covered",
        {"through_source_id": str(through_source_id)},
    )
    if result != {"status": "already_covered"}:
        raise MemoryCommandConflictError("The saved no-work result is incomplete")
    return True


async def require_base(session: AsyncSession, record: batch_persistence.MemoryBatchRecord) -> None:
    head = await batch_persistence.read_head(session, record.job_file_id)
    if (head.snapshot_id if head is not None else None) != record.base_snapshot_id:
        raise MemoryCandidateStateError("The published Memory base has changed")


async def edit_candidate(session: AsyncSession, command: MemoryEdit) -> MemoryEditResult:
    require_layer_write(command.position.phase, command.layer)
    payload = operations.edit_payload(command)
    original = await operations.recover(
        session,
        command.position.job_file_id,
        command.position.execution_id,
        command.command_id,
        "edit",
        payload,
    )
    if original is not None:
        # Recovery may revisit an old position, but never a discarded generation.
        current = await batch_persistence.read_batch(
            session, command.position.job_file_id, command.position.execution_id
        )
        if (
            current is None
            or current.status != "open"
            or current.generation_id != command.position.generation_id
        ):
            raise MemoryCandidateStateError("The original operation belongs to a discarded branch")
        return MemoryEditResult(
            operations.result_position(original), operations.stored_uuid(original, "object_id")
        )
    record = await queries.require_stage(session, command.position, exact_position=True)
    await require_base(session, record)
    members = await queries.read_members(session, record.job_file_id, record.current_position_id)
    before = members.copy()
    if isinstance(command, CreateMemoryObject):
        revision = await _write_revision(
            session,
            record,
            members,
            command.layer,
            command.content,
            command.reference_ids,
            previous=None,
        )
        members[revision.object_id] = _reference(revision)
        object_id = revision.object_id
    else:
        prior = await queries.read_selected(session, record.job_file_id, members, command.object_id)
        if prior.layer != command.layer:
            raise MemoryRevisionNotFoundError("The object is outside the selected layer")
        if isinstance(command, DeleteMemoryObject):
            await _remove_object(session, record, members, prior)
        else:
            revision = await _revise_object(session, record, members, command, prior)
            members[revision.object_id] = _reference(revision)
        object_id = prior.object_id
    if members != before:
        next_position = uuid4()
        await position_persistence.insert_position(
            session,
            record.job_file_id,
            next_position,
            record.current_position_id,
            tuple(sorted(members.values())),
        )
        record.current_position_id = next_position
    result = MemoryEditResult(queries.batch_position(record), object_id)
    await operations.record_result(
        session, result.position, command.command_id, "edit", payload, object_id=object_id
    )
    return result


async def _revise_object(
    session: AsyncSession,
    record: batch_persistence.MemoryBatchRecord,
    members: dict[UUID, MemoryRevisionReference],
    command: ReviseMemoryObject,
    prior: MemoryObjectRevision,
) -> MemoryObjectRevision:
    content = (
        apply_content_changes(prior.content, command.content_changes)
        if command.content_changes is not None
        else prior.content
    )
    source_ids = (
        prior.interview_references
        if prior.layer == MemoryLayer.WORK_SITUATION
        else frozenset(ref.object_id for ref in prior.work_situation_references)
    )
    if command.reference_changes is not None:
        added = command.reference_changes.add
        if prior.layer == MemoryLayer.WORK_SITUATION:
            await read_reference_headers(session, queries.source_window(record), source_ids=added)
            allowed = added
        else:
            allowed = frozenset(members)
        source_ids = apply_reference_changes(source_ids, command.reference_changes, allowed)
    return await _write_revision(
        session, record, members, prior.layer, content, source_ids, previous=prior
    )


async def _write_revision(
    session: AsyncSession,
    record: batch_persistence.MemoryBatchRecord,
    members: dict[UUID, MemoryRevisionReference],
    layer: MemoryLayer,
    content: MemoryContent,
    source_ids: frozenset[UUID],
    *,
    previous: MemoryObjectRevision | None,
) -> MemoryObjectRevision:
    entries = await position_persistence.read_position_map(
        session, record.job_file_id, record.current_position_id, layer
    )
    require_unique_title(previous.object_id if previous is not None else uuid4(), content, entries)
    refs: frozenset[MemoryRevisionReference] = frozenset()
    if layer == MemoryLayer.WORK_UNDERSTANDING:
        if not source_ids <= members.keys():
            raise MemoryRevisionNotFoundError(
                "A selected Memory source is absent from the position"
            )
        # The revision owner validates all fixed source headers/layers/windows in one set.
        refs = frozenset(members[identity] for identity in source_ids)
    return await write_object_revision(
        session,
        queries.source_window(record),
        layer=layer,
        content=content,
        previous=_reference(previous) if previous is not None else None,
        interview_references=source_ids if layer == MemoryLayer.WORK_SITUATION else frozenset(),
        work_situation_references=refs,
    )


async def _remove_object(
    session: AsyncSession,
    record: batch_persistence.MemoryBatchRecord,
    members: dict[UUID, MemoryRevisionReference],
    target: MemoryObjectRevision,
) -> None:
    del members[target.object_id]
    if target.layer != MemoryLayer.WORK_SITUATION:
        return
    # Deterministic binding removal, not B1 interpreting or receiving understanding content.
    headers = await read_fixed_headers(
        session, job_file_id=record.job_file_id, references=frozenset(members.values())
    )
    bindings = {}
    for reference, dependent in headers.items():
        retained = frozenset(
            ref for ref in dependent.work_situation_references if ref.object_id != target.object_id
        )
        if retained == dependent.work_situation_references:
            continue
        bindings[reference] = retained
    members.update(
        await rebind_understanding_sources(session, queries.source_window(record), bindings)
    )


def _reference(revision: MemoryObjectRevision) -> MemoryRevisionReference:
    return MemoryRevisionReference(revision.object_id, revision.revision_id)
