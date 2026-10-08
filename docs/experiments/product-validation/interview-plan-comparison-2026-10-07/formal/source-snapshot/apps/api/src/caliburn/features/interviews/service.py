"""Preserve App opening and employee submissions with separate source eligibility."""

from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.features.interviews import persistence
from caliburn.features.interviews.models import (
    AcceptedInterviewInput,
    FormalInterviewExchange,
    InputCommandConflictError,
    InterviewCompletionConflictError,
    InterviewInputNotFoundError,
    SubmitInterviewInput,
)
from caliburn.features.interviews.opening import OPENING_TEXT


async def create_opening(session: AsyncSession, job_file_id: UUID) -> None:
    await persistence.insert_opening(
        session, job_file_id=job_file_id, source_id=uuid4(), interview_text=OPENING_TEXT
    )


async def find_accepted_input(
    session: AsyncSession, command: SubmitInterviewInput
) -> AcceptedInterviewInput | None:
    found = await persistence.read_input_submission(
        session, job_file_id=command.job_file_id, command_id=command.command_id
    )
    if found is None:
        return None
    record, original = found
    if original.interview_text != command.text:
        raise InputCommandConflictError("Submission command was used with different text")
    return AcceptedInterviewInput(
        record.job_file_id, record.command_id, record.source_id, record.execution_id
    )


async def accept_input(
    session: AsyncSession, command: SubmitInterviewInput, *, execution_id: UUID
) -> AcceptedInterviewInput:
    """Persist once in the workflow's admission transaction; this grants no formal sequence."""
    source_id = uuid4()
    await persistence.insert_input(
        session,
        job_file_id=command.job_file_id,
        command_id=command.command_id,
        source_id=source_id,
        execution_id=execution_id,
        interview_text=command.text,
    )
    return AcceptedInterviewInput(command.job_file_id, command.command_id, source_id, execution_id)


async def read_formal_exchange(
    session: AsyncSession, *, job_file_id: UUID, execution_id: UUID
) -> FormalInterviewExchange | None:
    """Original completion result, never the most recent messages in this file."""
    reply_id = await persistence.read_reply_source_id(
        session, job_file_id=job_file_id, execution_id=execution_id
    )
    if reply_id is None:
        return None
    original = await persistence.read_execution_input(
        session, job_file_id=job_file_id, execution_id=execution_id
    )
    if original is None:
        raise RuntimeError("A recorded reply has no accepted input")
    messages = await persistence.list_formal_interviews(
        session, job_file_id, source_ids=(original.source_id, reply_id)
    )
    if len(messages) != 2 or messages[0].source_id != original.source_id:
        raise RuntimeError("A recorded reply has incomplete formal membership")
    return FormalInterviewExchange(messages[0], messages[1])


def require_same_reply(exchange: FormalInterviewExchange, reply_text: str) -> None:
    if exchange.consultant_reply.interview_text != reply_text:
        raise InterviewCompletionConflictError("The execution already has a different reply")


async def formalize_exchange(
    session: AsyncSession, *, job_file_id: UUID, execution_id: UUID, reply_text: str
) -> FormalInterviewExchange:
    """Participant only: caller holds file/writer locks and commits all A effects together.

    No model call or commit here. Sequence allocation is protected by the file row lock,
    so aborting this transaction neither consumes numbers nor grants formal membership.
    """
    if not reply_text.strip() or "\x00" in reply_text:
        raise ValueError("A formal reply must contain non-whitespace text without NUL")
    existing = await read_formal_exchange(
        session, job_file_id=job_file_id, execution_id=execution_id
    )
    if existing is not None:
        require_same_reply(existing, reply_text)
        return existing
    original = await persistence.read_execution_input(
        session, job_file_id=job_file_id, execution_id=execution_id
    )
    if original is None:
        raise InterviewInputNotFoundError("No accepted input exists in this execution scope")
    input_sequence = await persistence.read_formal_frontier(session, job_file_id) + 1
    await persistence.insert_formal_exchange(
        session,
        job_file_id=job_file_id,
        execution_id=execution_id,
        input_source_id=original.source_id,
        reply_source_id=uuid4(),
        reply_text=reply_text,
        input_sequence=input_sequence,
    )
    result = await read_formal_exchange(session, job_file_id=job_file_id, execution_id=execution_id)
    if result is None:
        raise RuntimeError("The newly inserted exchange could not be read")
    return result
