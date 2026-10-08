"""Fixed area content and each JD revision's ordered selection; no mutable mirror."""

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
from caliburn.features.job_description.areas import ResponsibilityArea


class AreaRevisionRecord(Base):
    __tablename__ = "jd_area_revisions"
    __table_args__ = (
        CheckConstraint("title IS NOT NULL OR scope_text IS NOT NULL", name="has_content"),
        CheckConstraint("title IS NULL OR length(btrim(title)) > 0", name="title_content"),
        CheckConstraint(
            "scope_text IS NULL OR length(btrim(scope_text)) > 0", name="scope_content"
        ),
    )

    job_file_id: Mapped[UUID] = mapped_column(
        ForeignKey("job_files.job_file_id", ondelete="CASCADE"), primary_key=True
    )
    area_id: Mapped[UUID] = mapped_column(primary_key=True)
    content_revision_id: Mapped[UUID] = mapped_column(primary_key=True)
    title: Mapped[str | None] = mapped_column(Text)
    scope_text: Mapped[str | None] = mapped_column(Text)


class AreaSelectionRecord(Base):
    __tablename__ = "jd_area_selections"
    __table_args__ = (
        ForeignKeyConstraint(
            ["job_file_id", "revision_id"],
            ["jd_revisions.job_file_id", "jd_revisions.revision_id"],
            name="fk_jd_area_selections_revision",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["job_file_id", "area_id", "content_revision_id"],
            [
                "jd_area_revisions.job_file_id",
                "jd_area_revisions.area_id",
                "jd_area_revisions.content_revision_id",
            ],
            name="fk_jd_area_selections_content",
            ondelete="CASCADE",
        ),
        UniqueConstraint("job_file_id", "revision_id", "position"),
        CheckConstraint("position >= 0", name="position"),
    )

    job_file_id: Mapped[UUID] = mapped_column(primary_key=True)
    revision_id: Mapped[UUID] = mapped_column(primary_key=True)
    area_id: Mapped[UUID] = mapped_column(primary_key=True)
    content_revision_id: Mapped[UUID]
    position: Mapped[int] = mapped_column(Integer)


async def read_areas(
    session: AsyncSession, job_file_id: UUID, revision_id: UUID
) -> tuple[ResponsibilityArea, ...]:
    records = await session.scalars(
        select(AreaRevisionRecord)
        .join(AreaSelectionRecord)
        .where(
            AreaSelectionRecord.job_file_id == job_file_id,
            AreaSelectionRecord.revision_id == revision_id,
        )
        .order_by(AreaSelectionRecord.position)
    )
    return tuple(
        ResponsibilityArea(row.area_id, row.content_revision_id, row.title, row.scope_text)
        for row in records
    )


async def insert_area_content(
    session: AsyncSession, job_file_id: UUID, area: ResponsibilityArea
) -> None:
    session.add(
        AreaRevisionRecord(
            job_file_id=job_file_id,
            area_id=area.area_id,
            content_revision_id=area.content_revision_id,
            title=area.title,
            scope_text=area.scope_text,
        )
    )
    await session.flush()


async def select_areas(
    session: AsyncSession,
    job_file_id: UUID,
    revision_id: UUID,
    areas: tuple[ResponsibilityArea, ...],
) -> None:
    session.add_all(
        [
            AreaSelectionRecord(
                job_file_id=job_file_id,
                revision_id=revision_id,
                area_id=area.area_id,
                content_revision_id=area.content_revision_id,
                position=position,
            )
            for position, area in enumerate(areas)
        ]
    )
    await session.flush()


async def copy_area_selection(
    session: AsyncSession, job_file_id: UUID, source_revision_id: UUID, target_revision_id: UUID
) -> None:
    """Copy small membership keys/order, not repeated area text, before the new head is visible."""
    await session.execute(
        insert(AreaSelectionRecord).from_select(
            ["job_file_id", "revision_id", "area_id", "content_revision_id", "position"],
            select(
                AreaSelectionRecord.job_file_id,
                literal(target_revision_id),
                AreaSelectionRecord.area_id,
                AreaSelectionRecord.content_revision_id,
                AreaSelectionRecord.position,
            ).where(
                AreaSelectionRecord.job_file_id == job_file_id,
                AreaSelectionRecord.revision_id == source_revision_id,
            ),
        )
    )
