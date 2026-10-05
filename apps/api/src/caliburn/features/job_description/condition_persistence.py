"""Fixed condition content and each JD revision's ordered selection; no mutable mirror."""

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
from caliburn.features.job_description.conditions import ConditionKind, JobCondition


class ConditionRevisionRecord(Base):
    __tablename__ = "jd_condition_revisions"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('work_environment', 'schedule_travel', 'shared_authority', "
            "'shared_collaboration', 'qualification')",
            name="kind",
        ),
        CheckConstraint("length(btrim(text)) > 0", name="text_content"),
    )

    job_file_id: Mapped[UUID] = mapped_column(
        ForeignKey("job_files.job_file_id", ondelete="CASCADE"), primary_key=True
    )
    condition_id: Mapped[UUID] = mapped_column(primary_key=True)
    content_revision_id: Mapped[UUID] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(Text)
    text: Mapped[str] = mapped_column(Text)


class ConditionSelectionRecord(Base):
    __tablename__ = "jd_condition_selections"
    __table_args__ = (
        ForeignKeyConstraint(
            ["job_file_id", "revision_id"],
            ["jd_revisions.job_file_id", "jd_revisions.revision_id"],
            name="fk_jd_condition_selections_revision",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["job_file_id", "condition_id", "content_revision_id"],
            [
                "jd_condition_revisions.job_file_id",
                "jd_condition_revisions.condition_id",
                "jd_condition_revisions.content_revision_id",
            ],
            name="fk_jd_condition_selections_content",
            ondelete="CASCADE",
        ),
        UniqueConstraint("job_file_id", "revision_id", "position"),
        CheckConstraint("position >= 0", name="position"),
    )

    job_file_id: Mapped[UUID] = mapped_column(primary_key=True)
    revision_id: Mapped[UUID] = mapped_column(primary_key=True)
    condition_id: Mapped[UUID] = mapped_column(primary_key=True)
    content_revision_id: Mapped[UUID]
    position: Mapped[int] = mapped_column(Integer)


async def read_conditions(
    session: AsyncSession, job_file_id: UUID, revision_id: UUID
) -> tuple[JobCondition, ...]:
    records = await session.scalars(
        select(ConditionRevisionRecord)
        .join(ConditionSelectionRecord)
        .where(
            ConditionSelectionRecord.job_file_id == job_file_id,
            ConditionSelectionRecord.revision_id == revision_id,
        )
        .order_by(ConditionSelectionRecord.position)
    )
    return tuple(
        JobCondition(row.condition_id, row.content_revision_id, ConditionKind(row.kind), row.text)
        for row in records
    )


async def insert_condition_content(
    session: AsyncSession, job_file_id: UUID, condition: JobCondition
) -> None:
    session.add(
        ConditionRevisionRecord(
            job_file_id=job_file_id,
            condition_id=condition.condition_id,
            content_revision_id=condition.content_revision_id,
            kind=condition.kind.value,
            text=condition.text,
        )
    )
    await session.flush()


async def select_conditions(
    session: AsyncSession,
    job_file_id: UUID,
    revision_id: UUID,
    conditions: tuple[JobCondition, ...],
) -> None:
    session.add_all(
        [
            ConditionSelectionRecord(
                job_file_id=job_file_id,
                revision_id=revision_id,
                condition_id=condition.condition_id,
                content_revision_id=condition.content_revision_id,
                position=position,
            )
            for position, condition in enumerate(conditions)
        ]
    )
    await session.flush()


async def copy_condition_selection(
    session: AsyncSession, job_file_id: UUID, source_revision_id: UUID, target_revision_id: UUID
) -> None:
    """Copy keys/order, not condition text, before adopting the new head."""
    await session.execute(
        insert(ConditionSelectionRecord).from_select(
            ["job_file_id", "revision_id", "condition_id", "content_revision_id", "position"],
            select(
                ConditionSelectionRecord.job_file_id,
                literal(target_revision_id),
                ConditionSelectionRecord.condition_id,
                ConditionSelectionRecord.content_revision_id,
                ConditionSelectionRecord.position,
            ).where(
                ConditionSelectionRecord.job_file_id == job_file_id,
                ConditionSelectionRecord.revision_id == source_revision_id,
            ),
        )
    )
