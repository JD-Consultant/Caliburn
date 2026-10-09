"""Reference candidate operations join the caller's qualified, locked short transaction."""

from uuid import UUID, uuid4, uuid5

from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.features.occupation_references import persistence
from caliburn.features.occupation_references.models import (
    OccupationReferenceState,
    ReferenceStateConflictError,
    ReferenceStateError,
    ReferenceStatePosition,
    StaleReferenceStateError,
)
from caliburn.features.occupation_references.models import select_references as select_references
from caliburn.features.occupation_references.models import (
    update_excluded_work as update_excluded_work,
)


async def start_candidate(
    session: AsyncSession,
    job_file_id: UUID,
    execution_id: UUID,
    base: OccupationReferenceState,
) -> ReferenceStatePosition:
    """Capture the caller-qualified baseline once; reentry never refreshes it."""
    existing = await read_candidate(session, job_file_id, execution_id)
    if existing is not None:
        return existing
    generation_id, revision_id = uuid4(), uuid4()
    operation = persistence.ReferenceOperationRecord(
        job_file_id=job_file_id,
        execution_id=execution_id,
        operation_id=uuid5(execution_id, "occupation_reference.start"),
        kind="start",
        generation_id=generation_id,
        result_generation_id=generation_id,
        expected_revision_id=None,
        parent_revision_id=None,
        revision_id=revision_id,
        state=persistence.state_payload(base),
    )
    session.add(operation)
    await session.flush()
    session.add(
        persistence.ReferenceCandidateRecord(
            job_file_id=job_file_id,
            execution_id=execution_id,
            generation_id=generation_id,
            base_revision_id=revision_id,
            current_revision_id=revision_id,
        )
    )
    await session.flush()
    return _operation_position(operation)


async def read_candidate(
    session: AsyncSession, job_file_id: UUID, execution_id: UUID
) -> ReferenceStatePosition | None:
    candidate = await persistence.read_candidate(session, job_file_id, execution_id)
    if candidate is None:
        return None
    return await _candidate_position(session, candidate)


async def apply_state(
    session: AsyncSession,
    job_file_id: UUID,
    position: ReferenceStatePosition,
    operation_id: UUID,
    new_state: OccupationReferenceState,
) -> ReferenceStatePosition:
    candidate = await _require_candidate(session, job_file_id, position.execution_id)
    _require_generation(candidate, position)
    original = await persistence.read_operation(session, job_file_id, operation_id)
    if original is not None:
        _require_same_request(original, position, kind="apply")
        if original.state != persistence.state_payload(new_state):
            raise ReferenceStateConflictError("The operation already has different reference state")
        await _require_saved_position(session, job_file_id, position)
        return _operation_position(original)
    await _require_current_position(session, candidate, position)
    return await _append_operation(
        session,
        candidate,
        position,
        operation_id,
        kind="apply",
        parent_revision_id=position.revision_id,
        generation_id=position.generation_id,
        state=new_state,
    )


async def restore_candidate(
    session: AsyncSession,
    job_file_id: UUID,
    position: ReferenceStatePosition,
    target_revision_id: UUID,
    operation_id: UUID,
) -> ReferenceStatePosition:
    """Restore a retained ancestor and revoke writes from the abandoned generation."""
    candidate = await _require_candidate(session, job_file_id, position.execution_id)
    original = await persistence.read_operation(session, job_file_id, operation_id)
    if original is not None:
        _require_same_request(original, position, kind="restore")
        if original.parent_revision_id != target_revision_id:
            raise ReferenceStateConflictError(
                "The restore operation already has a different target"
            )
        if candidate.generation_id != original.result_generation_id:
            raise StaleReferenceStateError("This restore result belongs to a revoked generation")
        await _require_saved_position(session, job_file_id, position)
        return _operation_position(original)
    _require_generation(candidate, position)
    await _require_current_position(session, candidate, position)
    target = await _read_ancestor(session, candidate, target_revision_id)
    return await _append_operation(
        session,
        candidate,
        position,
        operation_id,
        kind="restore",
        parent_revision_id=target.revision_id,
        generation_id=uuid4(),
        state=persistence.state_value(target.state),
    )


def _operation_position(operation: persistence.ReferenceOperationRecord) -> ReferenceStatePosition:
    return ReferenceStatePosition(
        operation.execution_id,
        operation.result_generation_id,
        operation.revision_id,
        persistence.state_value(operation.state),
    )


async def _candidate_position(
    session: AsyncSession, candidate: persistence.ReferenceCandidateRecord
) -> ReferenceStatePosition:
    operation = await persistence.read_revision(
        session, candidate.job_file_id, candidate.execution_id, candidate.current_revision_id
    )
    if operation is None or operation.result_generation_id != candidate.generation_id:
        raise ReferenceStateError("The candidate's saved reference position is unavailable")
    return _operation_position(operation)


async def _require_candidate(
    session: AsyncSession, job_file_id: UUID, execution_id: UUID
) -> persistence.ReferenceCandidateRecord:
    candidate = await persistence.read_candidate(session, job_file_id, execution_id)
    if candidate is None:
        raise ReferenceStateError("No reference candidate belongs to this execution scope")
    return candidate


def _require_generation(
    candidate: persistence.ReferenceCandidateRecord, position: ReferenceStatePosition
) -> None:
    if candidate.generation_id != position.generation_id:
        raise StaleReferenceStateError("The reference candidate generation has been revoked")


async def _require_current_position(
    session: AsyncSession,
    candidate: persistence.ReferenceCandidateRecord,
    position: ReferenceStatePosition,
) -> None:
    if candidate.current_revision_id != position.revision_id:
        raise StaleReferenceStateError("The reference candidate has advanced past this revision")
    await _require_saved_position(session, candidate.job_file_id, position)


async def _require_saved_position(
    session: AsyncSession, job_file_id: UUID, position: ReferenceStatePosition
) -> None:
    saved = await persistence.read_revision(
        session, job_file_id, position.execution_id, position.revision_id
    )
    if saved is None or _operation_position(saved) != position:
        raise ReferenceStateError("The supplied position does not match its saved reference state")


def _require_same_request(
    operation: persistence.ReferenceOperationRecord,
    position: ReferenceStatePosition,
    *,
    kind: str,
) -> None:
    if (
        operation.kind != kind
        or operation.execution_id != position.execution_id
        or operation.generation_id != position.generation_id
        or operation.expected_revision_id != position.revision_id
    ):
        raise ReferenceStateConflictError(
            "The operation identity already belongs to another intent"
        )


async def _read_ancestor(
    session: AsyncSession, candidate: persistence.ReferenceCandidateRecord, target_revision_id: UUID
) -> persistence.ReferenceOperationRecord:
    current: UUID | None = candidate.current_revision_id
    visited: set[UUID] = set()
    while current is not None and current not in visited:
        visited.add(current)
        revision = await persistence.read_revision(
            session, candidate.job_file_id, candidate.execution_id, current
        )
        if revision is None:
            raise ReferenceStateError("A retained reference ancestor is unavailable")
        if current == target_revision_id:
            return revision
        current = revision.parent_revision_id
    raise ReferenceStateError("Restore requires an ancestor within this Turn's current branch")


async def _append_operation(
    session: AsyncSession,
    candidate: persistence.ReferenceCandidateRecord,
    position: ReferenceStatePosition,
    operation_id: UUID,
    *,
    kind: str,
    parent_revision_id: UUID,
    generation_id: UUID,
    state: OccupationReferenceState,
) -> ReferenceStatePosition:
    operation = persistence.ReferenceOperationRecord(
        job_file_id=candidate.job_file_id,
        execution_id=candidate.execution_id,
        operation_id=operation_id,
        kind=kind,
        generation_id=position.generation_id,
        result_generation_id=generation_id,
        expected_revision_id=position.revision_id,
        parent_revision_id=parent_revision_id,
        revision_id=uuid4(),
        state=persistence.state_payload(state),
    )
    session.add(operation)
    await session.flush()
    candidate.current_revision_id = operation.revision_id
    candidate.generation_id = generation_id
    await session.flush()
    return _operation_position(operation)
