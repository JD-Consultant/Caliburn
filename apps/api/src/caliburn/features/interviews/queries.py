"""Formal history only; execution originals without formal membership stay invisible."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.features.interviews import persistence
from caliburn.features.interviews.models import (
    InterviewInputNotFoundError,
    InterviewMessage,
    InterviewReadError,
    InterviewReadScope,
    InterviewSpeaker,
    RecentInterviews,
    StoredInterviewInput,
)


async def read_interview_history(
    session: AsyncSession, job_file_id: UUID
) -> list[InterviewMessage]:
    return await persistence.list_formal_interviews(session, job_file_id)


async def read_execution_input(
    session: AsyncSession, *, job_file_id: UUID, execution_id: UUID
) -> StoredInterviewInput:
    """Private App recovery/UI query, NOT an Agent's shared historical-source tool."""
    original = await persistence.read_execution_input(
        session, job_file_id=job_file_id, execution_id=execution_id
    )
    if original is None:
        raise InterviewInputNotFoundError("No accepted input exists in this execution scope")
    return StoredInterviewInput(original.source_id, original.interview_text)


async def read_history_frontier(session: AsyncSession, job_file_id: UUID) -> int:
    """Caller pins this value once for A; Memory F comes from the triggering employee source."""
    return await persistence.read_formal_frontier(session, job_file_id)


def _check_sequence(scope: InterviewReadScope, sequence: int) -> None:
    if type(sequence) is not int or sequence < 1 or sequence > scope.through_sequence:
        raise InterviewReadError("Select positive formal sequences within the fixed read boundary")


async def read_interview_messages(
    session: AsyncSession, scope: InterviewReadScope, *, sequences: tuple[int, ...]
) -> list[InterviewMessage]:
    if not sequences:
        raise InterviewReadError("Select at least one formal interview sequence")
    for sequence in sequences:
        _check_sequence(scope, sequence)
    selected = tuple(sorted(set(sequences)))
    messages = await persistence.list_formal_interviews(
        session, scope.job_file_id, sequences=selected
    )
    if len(messages) != len(selected):
        raise InterviewReadError("The entire selection must exist as formal interview sources")
    return messages


async def read_interview_range(
    session: AsyncSession, scope: InterviewReadScope, *, start_sequence: int, end_sequence: int
) -> list[InterviewMessage]:
    """Inclusive range, no partial success and no inferred question/answer pairing."""
    _check_sequence(scope, start_sequence)
    _check_sequence(scope, end_sequence)
    if start_sequence > end_sequence:
        raise InterviewReadError("The start sequence must not follow the end sequence")
    messages = await persistence.list_formal_interviews(
        session, scope.job_file_id, start_sequence=start_sequence, end_sequence=end_sequence
    )
    # Count without allocating range(start, end): even a bad huge boundary stays bounded by rows.
    if len(messages) != end_sequence - start_sequence + 1:
        raise InterviewReadError("The entire range must exist as formal interview sources")
    return messages


async def read_recent_interviews(
    session: AsyncSession, scope: InterviewReadScope, *, covered_through_sequence: int
) -> RecentInterviews:
    """Return (K,H/F] plus at most one earlier guidance, marked separately from coverage.

    Bounds belong to the caller's fixed Memory/execution binding. No querying latest Memory,
    current pending input, topic filtering, compaction or token truncation occurs here.
    """
    if (
        type(covered_through_sequence) is not int
        or covered_through_sequence < 0
        or covered_through_sequence > scope.through_sequence
    ):
        raise InterviewReadError("Coverage must be within the fixed history boundary")
    if scope.through_sequence:
        await read_interview_messages(session, scope, sequences=(scope.through_sequence,))
    if covered_through_sequence:
        await read_interview_messages(session, scope, sequences=(covered_through_sequence,))
    messages = (
        await read_interview_range(
            session,
            scope,
            start_sequence=covered_through_sequence + 1,
            end_sequence=scope.through_sequence,
        )
        if covered_through_sequence < scope.through_sequence
        else []
    )
    context_sequences: tuple[int, ...] = ()
    if not messages or messages[0].speaker == InterviewSpeaker.EMPLOYEE:
        before_sequence = messages[0].interview_sequence if messages else scope.through_sequence + 1
        preceding = await persistence.read_preceding_guidance_sequence(
            session, job_file_id=scope.job_file_id, before_sequence=before_sequence
        )
        if preceding is not None:
            guidance = await read_interview_messages(session, scope, sequences=(preceding,))
            messages = guidance + messages
            context_sequences = (preceding,)
    return RecentInterviews(tuple(messages), context_sequences)
