"""Preserve App opening and employee submissions with separate source eligibility."""

from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.features.interviews import persistence
from caliburn.features.interviews.models import (
    AcceptedInterviewInput,
    InputCommandConflictError,
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
