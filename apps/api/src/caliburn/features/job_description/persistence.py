"""JD-owned SQL: fixed profile revisions, formal head and immutable operation results."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from caliburn.adapters.database import Base
from caliburn.features.job_description import area_persistence, task_persistence
from caliburn.features.job_description.areas import ResponsibilityArea
from caliburn.features.job_description.models import JdProfile, JdProfileRevision
from caliburn.features.job_description.tasks import WorkTask


class JdRevisionRecord(Base):
    __tablename__ = "jd_revisions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["job_file_id", "parent_revision_id"],
            ["jd_revisions.job_file_id", "jd_revisions.revision_id"],
            name="fk_jd_revisions_parent",
        ),
        CheckConstraint(
            "parent_revision_id IS NULL OR parent_revision_id <> revision_id",
            name="not_self_parent",
        ),
    )

    job_file_id: Mapped[UUID] = mapped_column(ForeignKey("job_files.job_file_id"), primary_key=True)
    revision_id: Mapped[UUID] = mapped_column(primary_key=True)
    parent_revision_id: Mapped[UUID | None]
    job_title: Mapped[str | None] = mapped_column(Text)
    organization_unit: Mapped[str | None] = mapped_column(Text)
    reports_to: Mapped[str | None] = mapped_column(Text)
    purpose: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class JobDescriptionRecord(Base):
    __tablename__ = "job_descriptions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["job_file_id", "initial_revision_id"],
            ["jd_revisions.job_file_id", "jd_revisions.revision_id"],
            name="fk_job_descriptions_initial_revision",
        ),
        ForeignKeyConstraint(
            ["job_file_id", "current_revision_id"],
            ["jd_revisions.job_file_id", "jd_revisions.revision_id"],
            name="fk_job_descriptions_current_revision",
        ),
    )

    job_file_id: Mapped[UUID] = mapped_column(ForeignKey("job_files.job_file_id"), primary_key=True)
    initial_revision_id: Mapped[UUID]
    current_revision_id: Mapped[UUID]


class JdOperationRecord(Base):
    __tablename__ = "jd_operations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["job_file_id", "expected_revision_id"],
            ["jd_revisions.job_file_id", "jd_revisions.revision_id"],
            name="fk_jd_operations_expected_revision",
        ),
        ForeignKeyConstraint(
            ["job_file_id", "result_revision_id"],
            ["jd_revisions.job_file_id", "jd_revisions.revision_id"],
            name="fk_jd_operations_result_revision",
        ),
        CheckConstraint("kind IN ('revise_profile', 'edit_areas', 'edit_tasks')", name="kind"),
    )

    job_file_id: Mapped[UUID] = mapped_column(ForeignKey("job_files.job_file_id"), primary_key=True)
    command_id: Mapped[UUID] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(Text)
    expected_revision_id: Mapped[UUID]
    result_revision_id: Mapped[UUID]
    # Loaded JSON is untrusted until compared with the typed original command.
    request_payload: Mapped[object] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


async def read_document(session: AsyncSession, job_file_id: UUID) -> JobDescriptionRecord:
    record = await session.get(JobDescriptionRecord, job_file_id)
    if record is None:
        raise RuntimeError("JD head missing from an existing target job file")
    return record


async def read_revision(
    session: AsyncSession, job_file_id: UUID, revision_id: UUID
) -> JdProfileRevision:
    record = await session.get(JdRevisionRecord, (job_file_id, revision_id))
    if record is None:
        raise RuntimeError("Required fixed JD revision is unavailable")
    return JdProfileRevision(
        revision_id=record.revision_id,
        profile=JdProfile(
            job_title=record.job_title,
            organization_unit=record.organization_unit,
            reports_to=record.reports_to,
            purpose=record.purpose,
        ),
    )


async def read_operation(
    session: AsyncSession, job_file_id: UUID, command_id: UUID
) -> JdOperationRecord | None:
    return await session.get(JdOperationRecord, (job_file_id, command_id))


async def insert_revision(
    session: AsyncSession,
    job_file_id: UUID,
    revision: JdProfileRevision,
    *,
    parent_revision_id: UUID | None,
    areas: tuple[ResponsibilityArea, ...] | None = None,
    tasks: tuple[WorkTask, ...] | None = None,
) -> None:
    session.add(
        JdRevisionRecord(
            job_file_id=job_file_id,
            revision_id=revision.revision_id,
            parent_revision_id=parent_revision_id,
            job_title=revision.profile.job_title,
            organization_unit=revision.profile.organization_unit,
            reports_to=revision.profile.reports_to,
            purpose=revision.profile.purpose,
        )
    )
    await session.flush()
    if areas is not None:
        await area_persistence.select_areas(session, job_file_id, revision.revision_id, areas)
    elif parent_revision_id is not None:
        await area_persistence.copy_area_selection(
            session, job_file_id, parent_revision_id, revision.revision_id
        )
    if tasks is not None:
        await task_persistence.select_tasks(session, job_file_id, revision.revision_id, tasks)
    elif parent_revision_id is not None:
        await task_persistence.copy_task_selection(
            session, job_file_id, parent_revision_id, revision.revision_id
        )
