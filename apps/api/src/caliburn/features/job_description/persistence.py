"""JD-owned SQL: fixed profile revisions, formal head and immutable operation results."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Text,
    func,
    or_,
    select,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from caliburn.adapters.database import Base
from caliburn.features.job_description import (
    area_persistence,
    capability_persistence,
    collaborator_persistence,
    condition_persistence,
    task_persistence,
)
from caliburn.features.job_description.areas import ResponsibilityArea
from caliburn.features.job_description.capabilities import Capability, TaskCapabilityLink
from caliburn.features.job_description.collaborators import Collaborator
from caliburn.features.job_description.conditions import JobCondition
from caliburn.features.job_description.models import JdProfile, JdProfileRevision
from caliburn.features.job_description.tasks import WorkTask


class JdRevisionRecord(Base):
    __tablename__ = "jd_revisions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["job_file_id", "parent_revision_id"],
            ["jd_revisions.job_file_id", "jd_revisions.revision_id"],
            name="fk_jd_revisions_parent",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "parent_revision_id IS NULL OR parent_revision_id <> revision_id",
            name="not_self_parent",
        ),
    )

    job_file_id: Mapped[UUID] = mapped_column(
        ForeignKey("job_files.job_file_id", ondelete="CASCADE"), primary_key=True
    )
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
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["job_file_id", "current_revision_id"],
            ["jd_revisions.job_file_id", "jd_revisions.revision_id"],
            name="fk_job_descriptions_current_revision",
            ondelete="CASCADE",
        ),
    )

    job_file_id: Mapped[UUID] = mapped_column(
        ForeignKey("job_files.job_file_id", ondelete="CASCADE"), primary_key=True
    )
    initial_revision_id: Mapped[UUID]
    current_revision_id: Mapped[UUID]


class JdOperationRecord(Base):
    __tablename__ = "jd_operations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["job_file_id", "expected_revision_id"],
            ["jd_revisions.job_file_id", "jd_revisions.revision_id"],
            name="fk_jd_operations_expected_revision",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["job_file_id", "result_revision_id"],
            ["jd_revisions.job_file_id", "jd_revisions.revision_id"],
            name="fk_jd_operations_result_revision",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "kind IN ('revise_profile', 'edit_areas', 'edit_tasks', 'edit_capabilities', "
            "'edit_collaborators', 'edit_conditions', 'restore_candidate', "
            "'discard_candidate', 'adopt_candidate', 'edit_sources', 'undo_completed_turn')",
            name="kind",
        ),
        ForeignKeyConstraint(
            ["job_file_id", "candidate_execution_id"],
            ["jd_candidates.job_file_id", "jd_candidates.execution_id"],
            name="fk_jd_operations_candidate",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "(candidate_execution_id IS NULL) = (candidate_generation_id IS NULL)",
            name="candidate_scope",
        ),
    )

    job_file_id: Mapped[UUID] = mapped_column(
        ForeignKey("job_files.job_file_id", ondelete="CASCADE"), primary_key=True
    )
    command_id: Mapped[UUID] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(Text)
    expected_revision_id: Mapped[UUID]
    result_revision_id: Mapped[UUID]
    candidate_execution_id: Mapped[UUID | None]
    candidate_generation_id: Mapped[UUID | None]
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


async def read_revision_interval(
    session: AsyncSession, job_file_id: UUID, *, base_revision_id: UUID, end_revision_id: UUID
) -> tuple[tuple[UUID, UUID | None], ...]:
    """JD-owned ancestry only, stopping at the App-selected base."""
    chain = (
        select(JdRevisionRecord.revision_id, JdRevisionRecord.parent_revision_id)
        .where(
            JdRevisionRecord.job_file_id == job_file_id,
            JdRevisionRecord.revision_id == end_revision_id,
        )
        .cte("manual_jd_ancestry", recursive=True)
    )
    chain = chain.union_all(
        select(JdRevisionRecord.revision_id, JdRevisionRecord.parent_revision_id)
        .join(chain, JdRevisionRecord.revision_id == chain.c.parent_revision_id)
        .where(JdRevisionRecord.job_file_id == job_file_id, chain.c.revision_id != base_revision_id)
    )
    return tuple((row[0], row[1]) for row in (await session.execute(select(chain))).all())


async def read_manual_operations(
    session: AsyncSession,
    job_file_id: UUID,
    revision_ids: tuple[UUID, ...],
    *,
    created_before: datetime,
    created_since: datetime | None,
) -> tuple[JdOperationRecord, ...]:
    """Read original manual effects, including no-op receipts, never candidate edits."""
    record = JdOperationRecord
    statement = select(record).where(
        record.job_file_id == job_file_id,
        record.candidate_execution_id.is_(None),
        record.expected_revision_id.in_(revision_ids),
        record.result_revision_id.in_(revision_ids),
        record.created_at <= created_before,
    )
    if created_since is not None:
        # Changed revisions are identified by ancestry. No-op records need an interval
        # boundary because they leave no new revision. No manual writes are admitted
        # during the prior candidate's lifetime; use its start, not completion txn time.
        statement = statement.where(
            or_(
                record.expected_revision_id != record.result_revision_id,
                record.created_at >= created_since,
            )
        )
    return tuple(await session.scalars(statement.order_by(record.created_at, record.command_id)))


async def is_revision_ancestor(
    session: AsyncSession, job_file_id: UUID, *, ancestor: UUID, descendant: UUID, boundary: UUID
) -> bool:
    """Follow fixed parents only as far as this candidate's initial formal base."""
    chain = (
        select(JdRevisionRecord.revision_id, JdRevisionRecord.parent_revision_id)
        .where(
            JdRevisionRecord.job_file_id == job_file_id, JdRevisionRecord.revision_id == descendant
        )
        .cte("candidate_ancestry", recursive=True)
    )
    chain = chain.union_all(
        select(JdRevisionRecord.revision_id, JdRevisionRecord.parent_revision_id)
        .join(chain, JdRevisionRecord.revision_id == chain.c.parent_revision_id)
        .where(JdRevisionRecord.job_file_id == job_file_id, chain.c.revision_id != boundary)
    )
    return (
        await session.scalar(
            select(chain.c.revision_id).where(chain.c.revision_id == ancestor).limit(1)
        )
    ) is not None


async def insert_revision(
    session: AsyncSession,
    job_file_id: UUID,
    revision: JdProfileRevision,
    *,
    parent_revision_id: UUID | None,
    areas: tuple[ResponsibilityArea, ...] | None = None,
    tasks: tuple[WorkTask, ...] | None = None,
    capabilities: tuple[Capability, ...] | None = None,
    task_links: tuple[TaskCapabilityLink, ...] | None = None,
    collaborators: tuple[Collaborator, ...] | None = None,
    conditions: tuple[JobCondition, ...] | None = None,
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
    if capabilities is not None:
        await capability_persistence.select_capabilities(
            session, job_file_id, revision.revision_id, capabilities
        )
    elif parent_revision_id is not None:
        await capability_persistence.copy_capability_selection(
            session, job_file_id, parent_revision_id, revision.revision_id
        )
    if task_links is not None:
        await capability_persistence.select_task_links(
            session, job_file_id, revision.revision_id, task_links
        )
    elif parent_revision_id is not None:
        await capability_persistence.copy_task_links(
            session, job_file_id, parent_revision_id, revision.revision_id
        )
    if collaborators is not None:
        await collaborator_persistence.select_collaborators(
            session, job_file_id, revision.revision_id, collaborators
        )
    elif parent_revision_id is not None:
        await collaborator_persistence.copy_collaborator_selection(
            session, job_file_id, parent_revision_id, revision.revision_id
        )
    if conditions is not None:
        await condition_persistence.select_conditions(
            session, job_file_id, revision.revision_id, conditions
        )
    elif parent_revision_id is not None:
        await condition_persistence.copy_condition_selection(
            session, job_file_id, parent_revision_id, revision.revision_id
        )
