"""Create or rename once; replay original command results, not today's metadata."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.features.job_files import persistence
from caliburn.features.job_files.models import (
    CreateJobFile,
    CreationCommandConflictError,
    JobFile,
    JobFileCreation,
    JobFileNotFoundError,
    RenameCommandConflictError,
    RenameJobFile,
    StaleJobFileNameError,
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
            name_revision=1,
            employee_name=record.employee_name,
            created_at=record.created_at,
        ),
        is_new=is_new,
    )


async def lock_job_file(session: AsyncSession, job_file_id: UUID) -> None:
    """Serialize short admission/manual-edit/sequence decisions for this file only."""
    if await persistence.lock_job_file(session, job_file_id) is None:
        raise JobFileNotFoundError("Job file not found")


async def rename_job_file(
    session: AsyncSession, job_file_id: UUID, command: RenameJobFile
) -> JobFile:
    """Lock, recover the original result or rename once; transaction belongs to the caller."""
    file = await persistence.lock_job_file(session, job_file_id)
    if file is None:
        raise JobFileNotFoundError("Job file not found")
    result = await persistence.read_rename(session, job_file_id, command.command_id)
    if result is not None:
        if (result.display_name, result.expected_name_revision) != (
            command.display_name,
            command.expected_name_revision,
        ):
            raise RenameCommandConflictError("command_id was already used with different input")
    else:
        if file.name_revision != command.expected_name_revision:
            raise StaleJobFileNameError("Read the current label before renaming")
        result = await persistence.apply_rename(session, job_file_id, command)
    return JobFile(
        job_file_id=job_file_id,
        display_name=result.display_name,
        name_revision=result.name_revision,
        employee_name=file.employee_name,
        created_at=file.created_at,
    )
