"""Formal source reads and separate private App recovery queries without source eligibility."""

from uuid import UUID

from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.features.interviews import persistence
from caliburn.features.interviews.models import (
    AcceptedInterviewInput,
    FormalExchangePosition,
    InterviewHistoryEntry,
    InterviewInputNotFoundError,
    InterviewMessage,
    InterviewReadError,
    InterviewReadScope,
    InterviewScopeError,
    InterviewSourceNotAvailableError,
    InterviewSpeaker,
    InvalidInterviewSelectionError,
    RecentInterviews,
    StoredInterviewInput,
)


async def read_interview_history(
    session: AsyncSession, job_file_id: UUID
) -> list[InterviewMessage]:
    return await persistence.list_formal_interviews(session, job_file_id)


async def read_public_interview_history(
    session: AsyncSession, job_file_id: UUID
) -> list[InterviewHistoryEntry]:
    """UI-only reply locator; no native context or extra formal-source qualification."""
    return await persistence.list_public_interview_history(session, job_file_id)


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


async def read_accepted_input(
    session: AsyncSession, *, job_file_id: UUID, command_id: UUID
) -> AcceptedInterviewInput | None:
    """Private App recovery by original command, not a formal history/source lookup."""
    found = await persistence.read_input_submission(
        session, job_file_id=job_file_id, command_id=command_id
    )
    if found is None:
        return None
    record, _original = found
    return AcceptedInterviewInput(
        record.job_file_id, record.command_id, record.source_id, record.execution_id
    )


async def read_history_frontier(session: AsyncSession, job_file_id: UUID) -> int:
    """Caller pins this value once for A; Memory F comes from the triggering employee source."""
    return await persistence.read_formal_frontier(session, job_file_id)


async def list_formal_exchange_positions(
    session: AsyncSession, scope: InterviewReadScope
) -> tuple[FormalExchangePosition, ...]:
    """Public metadata boundary for matched formal exchanges within a fixed input frontier."""
    return await persistence.list_formal_exchange_positions(
        session, scope.job_file_id, scope.through_sequence
    )


def formal_exchange_positions_projection(scope: InterviewReadScope) -> Select[UUID, int]:
    """只公開同職務、固定員工輸入上界內的正式 exchange 身分及排序序號。"""
    return persistence.formal_exchange_positions_projection(
        scope.job_file_id, scope.through_sequence
    )


def _check_sequence(scope: InterviewReadScope, sequence: int) -> None:
    if type(sequence) is not int or sequence < 1:
        raise InvalidInterviewSelectionError("Select positive integer formal interview sequences")
    if sequence > scope.through_sequence:
        raise InterviewScopeError("The selection exceeds the fixed interview read boundary")


async def read_interview_messages(
    session: AsyncSession, scope: InterviewReadScope, *, sequences: tuple[int, ...]
) -> list[InterviewMessage]:
    if not sequences:
        raise InvalidInterviewSelectionError("Select at least one formal interview sequence")
    for sequence in sequences:
        _check_sequence(scope, sequence)
    selected = tuple(sorted(set(sequences)))
    messages = await persistence.list_formal_interviews(
        session, scope.job_file_id, sequences=selected
    )
    if len(messages) != len(selected):
        raise InterviewSourceNotAvailableError(
            "The entire selection must exist as formal interview sources"
        )
    return messages


async def read_interview_sources(
    session: AsyncSession, scope: InterviewReadScope, *, source_ids: tuple[UUID, ...]
) -> list[InterviewMessage]:
    """Resolve an entire source selection within the fixed formal boundary, regardless of role."""
    if not source_ids:
        raise InvalidInterviewSelectionError("Select at least one formal interview source")
    selected = tuple(dict.fromkeys(source_ids))
    messages = await persistence.list_formal_interviews(
        session, scope.job_file_id, source_ids=selected, end_sequence=scope.through_sequence
    )
    if len(messages) != len(selected):
        raise InterviewSourceNotAvailableError(
            "The entire selection must exist as formal interview sources within the fixed boundary"
        )
    return messages


async def read_interview_range(
    session: AsyncSession, scope: InterviewReadScope, *, start_sequence: int, end_sequence: int
) -> list[InterviewMessage]:
    """Inclusive range, no partial success and no inferred question/answer pairing."""
    _check_sequence(scope, start_sequence)
    _check_sequence(scope, end_sequence)
    if start_sequence > end_sequence:
        raise InvalidInterviewSelectionError("The start sequence must not follow the end sequence")
    messages = await persistence.list_formal_interviews(
        session, scope.job_file_id, start_sequence=start_sequence, end_sequence=end_sequence
    )
    # Count without allocating range(start, end): even a bad huge boundary stays bounded by rows.
    if len(messages) != end_sequence - start_sequence + 1:
        raise InterviewSourceNotAvailableError(
            "The entire range must exist as formal interview sources"
        )
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
