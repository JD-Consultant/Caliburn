"""Bind Memory source coverage through the formal interview owner's public queries."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.features.interviews import queries as interviews
from caliburn.features.interviews.models import (
    InterviewReadScope,
    InterviewSourceHeader,
    InterviewSpeaker,
    RecentInterviews,
)
from caliburn.features.work_memory.models import MemorySourceWindow, MemorySourceWindowError


async def bind_memory_source_window(
    session: AsyncSession,
    *,
    job_file_id: UUID,
    through_source_id: UUID,
    covered_through_sequence: int,
) -> MemorySourceWindow | None:
    """Resolve the original request's employee source; return None when already covered.

    Caller supplies K from the selected published snapshot and the exact source
    recorded with A's successful request. This query neither creates that intent
    nor persists a batch. Restore a started batch from its saved window instead.
    """
    if type(covered_through_sequence) is not int or covered_through_sequence < 0:
        raise MemorySourceWindowError("Coverage must be a nonnegative integer")
    # Latest frontier bounds validation only. F comes from the requested source,
    # not this max sequence, which also includes final replies and later turns.
    frontier = await interviews.read_history_frontier(session, job_file_id)
    scope = InterviewReadScope(job_file_id, frontier)
    (endpoint,) = await interviews.read_interview_source_headers(
        session, scope, source_ids=(through_source_id,)
    )
    if endpoint.speaker != InterviewSpeaker.EMPLOYEE:
        raise MemorySourceWindowError("A Memory request must end at a formal employee input")
    if covered_through_sequence:
        (covered,) = await interviews.read_interview_messages(
            session, scope, sequences=(covered_through_sequence,)
        )
        if covered.speaker != InterviewSpeaker.EMPLOYEE:
            raise MemorySourceWindowError("Published coverage must end at a formal employee input")
    if endpoint.interview_sequence <= covered_through_sequence:
        return None
    return MemorySourceWindow(
        job_file_id, through_source_id, covered_through_sequence, endpoint.interview_sequence
    )


async def read_required_interviews(
    session: AsyncSession, window: MemorySourceWindow
) -> RecentInterviews:
    """Read complete new sources using the batch's fixed bounds, without latest refresh."""
    return await interviews.read_recent_interviews(
        session,
        InterviewReadScope(window.job_file_id, window.through_sequence),
        covered_through_sequence=window.covered_through_sequence,
    )


async def read_reference_headers(
    session: AsyncSession, window: MemorySourceWindow, *, source_ids: frozenset[UUID]
) -> tuple[InterviewSourceHeader, ...]:
    """Validate identity references against formal membership, file and fixed upper bound."""
    if not source_ids:
        return ()
    return await interviews.read_interview_source_headers(
        session,
        InterviewReadScope(window.job_file_id, window.through_sequence),
        source_ids=tuple(source_ids),
    )
