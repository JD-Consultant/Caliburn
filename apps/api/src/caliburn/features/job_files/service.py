"""Create a file once; replay the original creation result, not today's renamed label."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.features.job_files import persistence
from caliburn.features.job_files.models import (
    CreateJobFile,
    CreationCommandConflictError,
    JobFile,
    JobFileCreation,
    JobFileNotFoundError,
)


async def create_job_file(session: AsyncSession, command: CreateJobFile) -> JobFileCreation:
    record = await persistence.insert_job_file(session, command)
    is_new = record is not None
    if record is None:
        record = await persistence.read_creation(session, command.command_id)
        if (record.initial_display_name, record.employee_name) != (
            command.display_name,
            command.employee_name,
        ):
            raise CreationCommandConflictError("command_id was already used with different input")
    return JobFileCreation(
        job_file=JobFile(
            job_file_id=record.job_file_id,
            display_name=record.initial_display_name,
            employee_name=record.employee_name,
            created_at=record.created_at,
        ),
        is_new=is_new,
    )


async def lock_job_file(session: AsyncSession, job_file_id: UUID) -> None:
    """Serialize short admission/manual-edit/sequence decisions for this file only."""
    if await persistence.lock_job_file(session, job_file_id) is None:
        raise JobFileNotFoundError("Job file not found")
