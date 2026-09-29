"""SQL for job-file metadata and its immutable original creation identity."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, Text, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from caliburn.adapters.database import Base
from caliburn.features.job_files.models import CreateJobFile


class JobFileRecord(Base):
    __tablename__ = "job_files"
    __table_args__ = (
        CheckConstraint(
            "length(btrim(display_name)) > 0 AND length(display_name) <= 200",
            name="display_name_length",
        ),
        CheckConstraint(
            "length(btrim(employee_name)) > 0 AND length(employee_name) <= 200",
            name="employee_name_length",
        ),
    )

    job_file_id: Mapped[UUID] = mapped_column(primary_key=True)
    creation_command_id: Mapped[UUID] = mapped_column(unique=True)
    initial_display_name: Mapped[str] = mapped_column(Text)
    display_name: Mapped[str] = mapped_column(Text)
    employee_name: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


async def insert_job_file(session: AsyncSession, command: CreateJobFile) -> JobFileRecord | None:
    statement = (
        insert(JobFileRecord)
        .values(
            job_file_id=uuid4(),
            creation_command_id=command.command_id,
            initial_display_name=command.display_name,
            display_name=command.display_name,
            employee_name=command.employee_name,
        )
        .on_conflict_do_nothing(index_elements=[JobFileRecord.creation_command_id])
        .returning(JobFileRecord)
    )
    return (await session.scalars(statement)).one_or_none()


async def read_creation(session: AsyncSession, command_id: UUID) -> JobFileRecord:
    return (
        await session.scalars(
            select(JobFileRecord).where(JobFileRecord.creation_command_id == command_id)
        )
    ).one()


async def read_job_file(session: AsyncSession, job_file_id: UUID) -> JobFileRecord | None:
    return await session.get(JobFileRecord, job_file_id)


async def lock_job_file(session: AsyncSession, job_file_id: UUID) -> JobFileRecord | None:
    return (
        await session.scalars(
            select(JobFileRecord)
            .where(JobFileRecord.job_file_id == job_file_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).one_or_none()


async def list_job_files(session: AsyncSession) -> list[JobFileRecord]:
    return list(
        await session.scalars(
            select(JobFileRecord).order_by(JobFileRecord.created_at, JobFileRecord.job_file_id)
        )
    )
