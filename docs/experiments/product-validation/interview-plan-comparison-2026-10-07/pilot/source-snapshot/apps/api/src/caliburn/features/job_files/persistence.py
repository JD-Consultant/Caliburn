"""SQL for current job-file metadata and immutable creation/rename results."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Text,
    delete,
    func,
    select,
    update,
)
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from caliburn.adapters.database import Base
from caliburn.features.job_files.models import CreateJobFile, RenameJobFile


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
        CheckConstraint("name_revision BETWEEN 1 AND 9007199254740991", name="name_revision_range"),
    )

    job_file_id: Mapped[UUID] = mapped_column(primary_key=True)
    creation_command_id: Mapped[UUID] = mapped_column(unique=True)
    initial_display_name: Mapped[str] = mapped_column(Text)
    display_name: Mapped[str] = mapped_column(Text)
    name_revision: Mapped[int] = mapped_column(BigInteger, server_default="1")
    employee_name: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class JobFileRenameRecord(Base):
    """Minimal immutable original command/result; current metadata remains in job_files."""

    __tablename__ = "job_file_renames"
    __table_args__ = (
        CheckConstraint(
            "length(btrim(display_name)) > 0 AND length(display_name) <= 200",
            name="display_name_length",
        ),
        CheckConstraint(
            "expected_name_revision BETWEEN 1 AND 9007199254740991 "
            "AND name_revision BETWEEN expected_name_revision AND expected_name_revision + 1",
            name="name_revision_range",
        ),
    )

    job_file_id: Mapped[UUID] = mapped_column(
        ForeignKey("job_files.job_file_id", ondelete="CASCADE"), primary_key=True
    )
    command_id: Mapped[UUID] = mapped_column(primary_key=True)
    display_name: Mapped[str] = mapped_column(Text)
    expected_name_revision: Mapped[int] = mapped_column(BigInteger)
    name_revision: Mapped[int] = mapped_column(BigInteger)


async def read_rename(
    session: AsyncSession, job_file_id: UUID, command_id: UUID
) -> JobFileRenameRecord | None:
    return await session.get(JobFileRenameRecord, (job_file_id, command_id))


async def apply_rename(
    session: AsyncSession, job_file_id: UUID, command: RenameJobFile
) -> JobFileRenameRecord:
    # The caller holds the file row lock. The DB maintains the name counter on label changes.
    name_revision = (
        await session.scalars(
            update(JobFileRecord)
            .where(JobFileRecord.job_file_id == job_file_id)
            .values(display_name=command.display_name)
            .returning(JobFileRecord.name_revision)
        )
    ).one()
    result = JobFileRenameRecord(
        job_file_id=job_file_id,
        command_id=command.command_id,
        display_name=command.display_name,
        expected_name_revision=command.expected_name_revision,
        name_revision=name_revision,
    )
    session.add(result)
    await session.flush()
    return result


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


async def delete_job_file(session: AsyncSession, job_file_id: UUID) -> None:
    """The database cascades this root deletion; the caller owns its transaction."""
    await session.execute(delete(JobFileRecord).where(JobFileRecord.job_file_id == job_file_id))
