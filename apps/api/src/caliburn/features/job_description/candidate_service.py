"""Private JD positions reuse fixed revisions; lifecycle changes join a short caller transaction."""

from dataclasses import dataclass
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.features.job_description import candidate_persistence, persistence, revision_editing
from caliburn.features.job_description.candidates import (
    CandidateStateError,
    JdCandidatePosition,
    JdCandidateScope,
)
from caliburn.features.job_description.models import (
    JdCommandConflictError,
    JdProfile,
    StaleJdRevisionError,
)
from caliburn.features.job_description.work_queries import JdWorkRevision, read_work_at


@dataclass(frozen=True, slots=True)
class JdCandidatePreview:
    position: JdCandidatePosition
    profile: JdProfile
    work: JdWorkRevision


def _position(record: candidate_persistence.JdCandidateRecord) -> JdCandidatePosition:
    return JdCandidatePosition(
        JdCandidateScope(record.execution_id, record.generation_id),
        record.base_revision_id,
        record.current_revision_id,
    )


async def start_candidate(
    session: AsyncSession, job_file_id: UUID, execution_id: UUID
) -> JdCandidatePosition:
    """Ensure one private draft without copying bodies or reopening a closed draft."""
    existing = await candidate_persistence.read_candidate(session, job_file_id, execution_id)
    if existing is not None:
        if existing.status != "open":
            raise CandidateStateError("A closed candidate cannot be restarted")
        return _position(existing)
    formal = await persistence.read_document(session, job_file_id)
    record = candidate_persistence.JdCandidateRecord(
        job_file_id=job_file_id,
        execution_id=execution_id,
        base_revision_id=formal.current_revision_id,
        current_revision_id=formal.current_revision_id,
        generation_id=uuid4(),
        status="open",
    )
    session.add(record)
    await session.flush()
    return _position(record)


async def read_position(
    session: AsyncSession, job_file_id: UUID, execution_id: UUID
) -> JdCandidatePosition:
    record = await candidate_persistence.read_candidate(session, job_file_id, execution_id)
    if record is None or record.status != "open":
        raise CandidateStateError("No open candidate in this execution")
    return _position(record)


async def read_preview(
    session: AsyncSession, job_file_id: UUID, execution_id: UUID
) -> JdCandidatePreview:
    position = await read_position(session, job_file_id, execution_id)
    profile = await persistence.read_revision(session, job_file_id, position.revision_id)
    return JdCandidatePreview(
        position, profile.profile, await read_work_at(session, job_file_id, position.revision_id)
    )


async def require_position(
    session: AsyncSession, job_file_id: UUID, position: JdCandidatePosition
) -> candidate_persistence.JdCandidateRecord:
    record = await revision_editing.require_open_candidate(session, job_file_id, position.scope)
    if (
        record.current_revision_id != position.revision_id
        or record.base_revision_id != position.base_revision_id
    ):
        raise StaleJdRevisionError("The candidate has advanced past the selected position")
    return record


async def _recover_control(
    session: AsyncSession,
    job_file_id: UUID,
    position: JdCandidatePosition,
    command_id: UUID,
    kind: str,
    payload: dict[str, str],
) -> JdCandidatePosition | None:
    operation = await revision_editing.read_edit_operation(
        session, job_file_id, command_id, position.scope
    )
    if operation is None:
        return None
    if operation.kind != kind or operation.expected_revision_id != position.revision_id:
        raise JdCommandConflictError("command_id was used for another candidate action")
    saved = operation.request_payload
    if not isinstance(saved, dict) or any(
        saved.get(key) != value for key, value in payload.items()
    ):
        raise JdCommandConflictError("command_id was used with different candidate intent")
    record = await candidate_persistence.read_candidate(
        session, job_file_id, position.scope.execution_id
    )
    if record is None or record.base_revision_id != position.base_revision_id:
        raise CandidateStateError("The candidate base is unavailable")
    generation_id = (
        UUID(saved["result_generation_id"])
        if kind == "restore_candidate"
        else position.scope.generation_id
    )
    return JdCandidatePosition(
        JdCandidateScope(position.scope.execution_id, generation_id),
        record.base_revision_id,
        operation.result_revision_id,
    )


async def restore_candidate(
    session: AsyncSession,
    job_file_id: UUID,
    position: JdCandidatePosition,
    target_revision_id: UUID,
    command_id: UUID,
) -> JdCandidatePosition:
    payload = {"target_revision_id": str(target_revision_id)}
    original = await _recover_control(
        session, job_file_id, position, command_id, "restore_candidate", payload
    )
    if original is not None:
        return original
    record = await require_position(session, job_file_id, position)
    if not await persistence.is_revision_ancestor(
        session,
        job_file_id,
        ancestor=target_revision_id,
        descendant=position.revision_id,
        boundary=position.base_revision_id,
    ):
        raise CandidateStateError("Restore requires a retained ancestor within this candidate")
    generation_id = uuid4()
    record.current_revision_id = target_revision_id
    record.generation_id = generation_id
    payload["result_generation_id"] = str(generation_id)
    _record_control(
        session, job_file_id, position, command_id, "restore_candidate", payload, target_revision_id
    )
    await session.flush()
    return _position(record)


async def discard_candidate(
    session: AsyncSession, job_file_id: UUID, position: JdCandidatePosition, command_id: UUID
) -> JdCandidatePosition:
    original = await _recover_control(
        session, job_file_id, position, command_id, "discard_candidate", {}
    )
    if original is not None:
        return original
    record = await require_position(session, job_file_id, position)
    record.status = "discarded"
    _record_control(
        session, job_file_id, position, command_id, "discard_candidate", {}, position.revision_id
    )
    await session.flush()
    return position


async def adopt_candidate(
    session: AsyncSession, job_file_id: UUID, position: JdCandidatePosition, command_id: UUID
) -> JdCandidatePosition:
    """JD participant only: caller must commit formal interview, final reply and intent together."""
    original = await recover_adoption(session, job_file_id, position, command_id)
    if original is not None:
        return original
    record = await require_position(session, job_file_id, position)
    document = await persistence.read_document(session, job_file_id)
    document.current_revision_id = position.revision_id
    record.status = "adopted"
    _record_control(
        session, job_file_id, position, command_id, "adopt_candidate", {}, position.revision_id
    )
    await session.flush()
    return position


async def recover_adoption(
    session: AsyncSession, job_file_id: UUID, position: JdCandidatePosition, command_id: UUID
) -> JdCandidatePosition | None:
    """The completed Turn may recover its original adoption without regaining write admission."""
    return await _recover_control(session, job_file_id, position, command_id, "adopt_candidate", {})


def _record_control(
    session: AsyncSession,
    job_file_id: UUID,
    position: JdCandidatePosition,
    command_id: UUID,
    kind: str,
    payload: dict[str, str],
    result_revision_id: UUID,
) -> None:
    session.add(
        persistence.JdOperationRecord(
            job_file_id=job_file_id,
            command_id=command_id,
            kind=kind,
            expected_revision_id=position.revision_id,
            result_revision_id=result_revision_id,
            candidate_execution_id=position.scope.execution_id,
            candidate_generation_id=position.scope.generation_id,
            request_payload=payload,
        )
    )
