"""Current metadata projections; creation replay remains a separate command result."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.features.job_files import persistence
from caliburn.features.job_files.models import JobFile, JobFileNotFoundError


def to_job_file(record: persistence.JobFileRecord) -> JobFile:
    return JobFile(
        job_file_id=record.job_file_id,
        display_name=record.display_name,
        name_revision=record.name_revision,
        employee_name=record.employee_name,
        created_at=record.created_at,
    )


async def read_job_file(session: AsyncSession, job_file_id: UUID) -> JobFile:
    record = await persistence.read_job_file(session, job_file_id)
    if record is None:
        raise JobFileNotFoundError("Job file not found")
    return to_job_file(record)


async def list_job_files(session: AsyncSession) -> list[JobFile]:
    return [to_job_file(record) for record in await persistence.list_job_files(session)]
