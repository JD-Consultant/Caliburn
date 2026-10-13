"""Read the original JD ledger and fixed values; execution qualification stays with its owner."""

from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.features.job_description import candidate_persistence, persistence, source_persistence
from caliburn.features.job_description.change_comparison import JdChangeSnapshot
from caliburn.features.job_description.work_queries import read_work_at


class JdChangeHistoryUnavailableError(LookupError):
    """A required historical endpoint or original operation cannot be recovered."""


async def read_manual_change_endpoints(
    session: AsyncSession,
    job_file_id: UUID,
    execution_id: UUID,
    *,
    start_revision_id: UUID,
    previous_completed_execution_id: UUID | None,
) -> tuple[JdChangeSnapshot, JdChangeSnapshot]:
    current = await candidate_persistence.read_candidate(session, job_file_id, execution_id)
    if current is None or current.status != "open" or current.base_revision_id != start_revision_id:
        raise JdChangeHistoryUnavailableError(
            "The current candidate does not match the fixed start"
        )
    base, _ = await read_manual_change_base(session, job_file_id, previous_completed_execution_id)
    return (
        await read_change_snapshot(session, job_file_id, base),
        await read_change_snapshot(session, job_file_id, start_revision_id),
    )


async def read_manual_change_base(
    session: AsyncSession,
    job_file_id: UUID,
    previous_completed_execution_id: UUID | None,
) -> tuple[UUID, datetime | None]:
    # 完成 ancestry 由 execution owner 選定；JD 只核自己的採用位置。
    if previous_completed_execution_id is None:
        return (await persistence.read_document(session, job_file_id)).initial_revision_id, None
    previous = await candidate_persistence.read_candidate(
        session, job_file_id, previous_completed_execution_id
    )
    if previous is None or previous.status != "adopted":
        raise JdChangeHistoryUnavailableError("The completed Turn has no adopted JD position")
    return previous.current_revision_id, previous.created_at


async def read_change_snapshot(
    session: AsyncSession, job_file_id: UUID, revision_id: UUID
) -> JdChangeSnapshot:
    profile = await persistence.read_revision(session, job_file_id, revision_id)
    return JdChangeSnapshot(
        profile.profile,
        await read_work_at(session, job_file_id, revision_id),
        await source_persistence.read_source_references(session, job_file_id, revision_id),
    )


async def read_adopted_turn_changes(
    session: AsyncSession, job_file_id: UUID, execution_id: UUID
) -> tuple[JdChangeSnapshot, JdChangeSnapshot]:
    """Read retained before/after values; caller qualifies this as a completed Turn."""
    candidate = await candidate_persistence.read_candidate(session, job_file_id, execution_id)
    if candidate is None or candidate.status != "adopted":
        raise JdChangeHistoryUnavailableError("The Turn has no retained adopted JD endpoints")
    return (
        await read_change_snapshot(session, job_file_id, candidate.base_revision_id),
        await read_change_snapshot(session, job_file_id, candidate.current_revision_id),
    )
