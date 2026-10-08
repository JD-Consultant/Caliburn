"""Fixed shared content, revision membership and ordered task relations."""

from collections import defaultdict
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    Text,
    UniqueConstraint,
    insert,
    literal,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from caliburn.adapters.database import Base
from caliburn.features.job_description.capabilities import (
    Capability,
    CapabilityKind,
    TaskCapabilityLink,
)
from caliburn.features.job_description.task_persistence import TaskSelectionRecord


class CapabilityRevisionRecord(Base):
    __tablename__ = "jd_capability_revisions"
    __table_args__ = (
        CheckConstraint("kind IN ('knowledge', 'skill')", name="kind"),
        CheckConstraint("name IS NOT NULL OR description IS NOT NULL", name="has_content"),
        CheckConstraint("name IS NULL OR length(btrim(name)) > 0", name="name_content"),
        CheckConstraint(
            "description IS NULL OR length(btrim(description)) > 0", name="description_content"
        ),
    )

    job_file_id: Mapped[UUID] = mapped_column(
        ForeignKey("job_files.job_file_id", ondelete="CASCADE"), primary_key=True
    )
    capability_id: Mapped[UUID] = mapped_column(primary_key=True)
    content_revision_id: Mapped[UUID] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(Text)
    name: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)


class CapabilitySelectionRecord(Base):
    __tablename__ = "jd_capability_selections"
    __table_args__ = (
        ForeignKeyConstraint(
            ["job_file_id", "revision_id"],
            ["jd_revisions.job_file_id", "jd_revisions.revision_id"],
            name="fk_jd_capability_selections_revision",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["job_file_id", "capability_id", "content_revision_id"],
            [
                "jd_capability_revisions.job_file_id",
                "jd_capability_revisions.capability_id",
                "jd_capability_revisions.content_revision_id",
            ],
            name="fk_jd_capability_selections_content",
            ondelete="CASCADE",
        ),
        UniqueConstraint("job_file_id", "revision_id", "position"),
        CheckConstraint("position >= 0", name="position"),
    )

    job_file_id: Mapped[UUID] = mapped_column(primary_key=True)
    revision_id: Mapped[UUID] = mapped_column(primary_key=True)
    capability_id: Mapped[UUID] = mapped_column(primary_key=True)
    content_revision_id: Mapped[UUID]
    position: Mapped[int] = mapped_column(Integer)


class TaskCapabilityRecord(Base):
    __tablename__ = "jd_task_capabilities"
    __table_args__ = (
        ForeignKeyConstraint(
            ["job_file_id", "revision_id", "task_id"],
            [
                "jd_task_selections.job_file_id",
                "jd_task_selections.revision_id",
                "jd_task_selections.task_id",
            ],
            name="fk_jd_task_capabilities_task",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["job_file_id", "revision_id", "capability_id"],
            [
                "jd_capability_selections.job_file_id",
                "jd_capability_selections.revision_id",
                "jd_capability_selections.capability_id",
            ],
            name="fk_jd_task_capabilities_capability",
            ondelete="CASCADE",
        ),
        UniqueConstraint("job_file_id", "revision_id", "task_id", "position"),
        CheckConstraint("position >= 0", name="position"),
    )

    job_file_id: Mapped[UUID] = mapped_column(primary_key=True)
    revision_id: Mapped[UUID] = mapped_column(primary_key=True)
    task_id: Mapped[UUID] = mapped_column(primary_key=True)
    capability_id: Mapped[UUID] = mapped_column(primary_key=True)
    position: Mapped[int] = mapped_column(Integer)


async def read_capabilities(
    session: AsyncSession, job_file_id: UUID, revision_id: UUID
) -> tuple[Capability, ...]:
    records = await session.scalars(
        select(CapabilityRevisionRecord)
        .join(CapabilitySelectionRecord)
        .where(
            CapabilitySelectionRecord.job_file_id == job_file_id,
            CapabilitySelectionRecord.revision_id == revision_id,
        )
        .order_by(CapabilitySelectionRecord.position)
    )
    return tuple(
        Capability(
            row.capability_id,
            row.content_revision_id,
            CapabilityKind(row.kind),
            row.name,
            row.description,
        )
        for row in records
    )


async def read_task_links(
    session: AsyncSession, job_file_id: UUID, revision_id: UUID
) -> tuple[TaskCapabilityLink, ...]:
    records = await session.scalars(
        select(TaskCapabilityRecord)
        .where(
            TaskCapabilityRecord.job_file_id == job_file_id,
            TaskCapabilityRecord.revision_id == revision_id,
        )
        .order_by(TaskCapabilityRecord.task_id, TaskCapabilityRecord.position)
    )
    return tuple(TaskCapabilityLink(row.task_id, row.capability_id) for row in records)


async def insert_capability_content(
    session: AsyncSession, job_file_id: UUID, capability: Capability
) -> None:
    session.add(
        CapabilityRevisionRecord(
            job_file_id=job_file_id,
            capability_id=capability.capability_id,
            content_revision_id=capability.content_revision_id,
            kind=capability.kind.value,
            name=capability.name,
            description=capability.description,
        )
    )
    await session.flush()


async def select_capabilities(
    session: AsyncSession,
    job_file_id: UUID,
    revision_id: UUID,
    capabilities: tuple[Capability, ...],
) -> None:
    session.add_all(
        [
            CapabilitySelectionRecord(
                job_file_id=job_file_id,
                revision_id=revision_id,
                capability_id=item.capability_id,
                content_revision_id=item.content_revision_id,
                position=index,
            )
            for index, item in enumerate(capabilities)
        ]
    )
    await session.flush()


async def select_task_links(
    session: AsyncSession,
    job_file_id: UUID,
    revision_id: UUID,
    links: tuple[TaskCapabilityLink, ...],
) -> None:
    positions: dict[UUID, int] = defaultdict(int)
    for link in links:
        session.add(
            TaskCapabilityRecord(
                job_file_id=job_file_id,
                revision_id=revision_id,
                task_id=link.task_id,
                capability_id=link.capability_id,
                position=positions[link.task_id],
            )
        )
        positions[link.task_id] += 1
    await session.flush()


async def copy_capability_selection(
    session: AsyncSession, job_file_id: UUID, source_revision_id: UUID, target_revision_id: UUID
) -> None:
    await session.execute(
        insert(CapabilitySelectionRecord).from_select(
            ["job_file_id", "revision_id", "capability_id", "content_revision_id", "position"],
            select(
                CapabilitySelectionRecord.job_file_id,
                literal(target_revision_id),
                CapabilitySelectionRecord.capability_id,
                CapabilitySelectionRecord.content_revision_id,
                CapabilitySelectionRecord.position,
            ).where(
                CapabilitySelectionRecord.job_file_id == job_file_id,
                CapabilitySelectionRecord.revision_id == source_revision_id,
            ),
        )
    )


async def copy_task_links(
    session: AsyncSession, job_file_id: UUID, source_revision_id: UUID, target_revision_id: UUID
) -> None:
    """Only surviving tasks retain relations; deleted tasks never remove shared definitions."""
    await session.execute(
        insert(TaskCapabilityRecord).from_select(
            ["job_file_id", "revision_id", "task_id", "capability_id", "position"],
            select(
                TaskCapabilityRecord.job_file_id,
                literal(target_revision_id),
                TaskCapabilityRecord.task_id,
                TaskCapabilityRecord.capability_id,
                TaskCapabilityRecord.position,
            )
            .join(
                TaskSelectionRecord,
                (TaskSelectionRecord.job_file_id == TaskCapabilityRecord.job_file_id)
                & (TaskSelectionRecord.task_id == TaskCapabilityRecord.task_id)
                & (TaskSelectionRecord.revision_id == target_revision_id),
            )
            .where(
                TaskCapabilityRecord.job_file_id == job_file_id,
                TaskCapabilityRecord.revision_id == source_revision_id,
            ),
        )
    )
