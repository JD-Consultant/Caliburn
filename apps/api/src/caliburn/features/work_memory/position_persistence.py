"""Fixed Memory selections; callers own candidate authority and the short transaction."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, ForeignKeyConstraint, false, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from caliburn.adapters.database import Base
from caliburn.features.work_memory.models import MemoryMapEntry
from caliburn.features.work_memory.revision_persistence import (
    MemoryObjectRecord,
    MemoryObjectRevisionRecord,
)
from caliburn.features.work_memory.revisions import MemoryLayer, MemoryRevisionReference


class MemoryPositionRecord(Base):
    __tablename__ = "memory_positions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["job_file_id", "parent_position_id"],
            ["memory_positions.job_file_id", "memory_positions.position_id"],
            name="fk_memory_positions_parent",
        ),
    )

    job_file_id: Mapped[UUID] = mapped_column(ForeignKey("job_files.job_file_id"), primary_key=True)
    position_id: Mapped[UUID] = mapped_column(primary_key=True)
    parent_position_id: Mapped[UUID | None]
    is_sealed: Mapped[bool] = mapped_column(Boolean, server_default=false())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MemoryPositionMemberRecord(Base):
    __tablename__ = "memory_position_members"
    __table_args__ = (
        ForeignKeyConstraint(
            ["job_file_id", "position_id"],
            ["memory_positions.job_file_id", "memory_positions.position_id"],
            name="fk_memory_position_members_position",
        ),
        ForeignKeyConstraint(
            ["job_file_id", "object_id", "revision_id"],
            [
                "memory_object_revisions.job_file_id",
                "memory_object_revisions.object_id",
                "memory_object_revisions.revision_id",
            ],
            name="fk_memory_position_members_revision",
        ),
    )

    job_file_id: Mapped[UUID] = mapped_column(primary_key=True)
    position_id: Mapped[UUID] = mapped_column(primary_key=True)
    object_id: Mapped[UUID] = mapped_column(primary_key=True)
    revision_id: Mapped[UUID]


async def insert_position(
    session: AsyncSession,
    job_file_id: UUID,
    position_id: UUID,
    parent_position_id: UUID | None,
    references: tuple[MemoryRevisionReference, ...],
) -> None:
    """Assemble then seal one selection; sealing does not mean B2 completion/publication."""
    record = MemoryPositionRecord(
        job_file_id=job_file_id,
        position_id=position_id,
        parent_position_id=parent_position_id,
        is_sealed=False,
    )
    session.add(record)
    await session.flush()
    session.add_all(
        MemoryPositionMemberRecord(
            job_file_id=job_file_id,
            position_id=position_id,
            object_id=reference.object_id,
            revision_id=reference.revision_id,
        )
        for reference in references
    )
    await session.flush()
    record.is_sealed = True
    await session.flush()


async def read_position_members(
    session: AsyncSession, job_file_id: UUID, position_id: UUID
) -> tuple[MemoryRevisionReference, ...] | None:
    """None denotes missing/unsealed; an empty sealed position is a valid selection."""
    exists = await session.scalar(
        select(MemoryPositionRecord.position_id).where(
            MemoryPositionRecord.job_file_id == job_file_id,
            MemoryPositionRecord.position_id == position_id,
            MemoryPositionRecord.is_sealed.is_(True),
        )
    )
    if exists is None:
        return None
    rows = await session.execute(
        select(MemoryPositionMemberRecord.object_id, MemoryPositionMemberRecord.revision_id)
        .where(
            MemoryPositionMemberRecord.job_file_id == job_file_id,
            MemoryPositionMemberRecord.position_id == position_id,
        )
        .order_by(MemoryPositionMemberRecord.object_id)
    )
    return tuple(MemoryRevisionReference(object_id, revision_id) for object_id, revision_id in rows)


async def read_position_map(
    session: AsyncSession, job_file_id: UUID, position_id: UUID, layer: MemoryLayer
) -> tuple[MemoryMapEntry, ...]:
    """Project a single layer without loading bodies; callers verify position existence."""
    rows = await session.execute(
        select(
            MemoryPositionMemberRecord.object_id,
            MemoryObjectRevisionRecord.title,
            MemoryObjectRevisionRecord.description,
        )
        .select_from(MemoryPositionMemberRecord)
        .join(MemoryPositionRecord)
        .join(MemoryObjectRevisionRecord)
        .join(
            MemoryObjectRecord,
            (MemoryObjectRecord.job_file_id == MemoryPositionMemberRecord.job_file_id)
            & (MemoryObjectRecord.object_id == MemoryPositionMemberRecord.object_id),
        )
        .where(
            MemoryPositionMemberRecord.job_file_id == job_file_id,
            MemoryPositionMemberRecord.position_id == position_id,
            MemoryPositionRecord.is_sealed.is_(True),
            MemoryObjectRecord.layer == layer.value,
        )
        .order_by(MemoryPositionMemberRecord.object_id)
    )
    return tuple(
        MemoryMapEntry(object_id, title, description) for object_id, title, description in rows
    )


async def is_position_ancestor(
    session: AsyncSession,
    job_file_id: UUID,
    ancestor: UUID,
    descendant: UUID,
    boundary: UUID,
) -> bool:
    """Inclusive ancestry within a sealed same-file chain ending at the batch boundary.

    An unrelated/missing boundary fails closed, even if ancestor equals descendant.
    The recursive query never traverses the boundary's parent.
    """
    positions = MemoryPositionRecord
    chain = (
        select(positions.position_id, positions.parent_position_id)
        .where(
            positions.job_file_id == job_file_id,
            positions.position_id == descendant,
            positions.is_sealed.is_(True),
        )
        .cte("memory_position_chain", recursive=True)
    )
    chain = chain.union(
        select(positions.position_id, positions.parent_position_id)
        .join(chain, positions.position_id == chain.c.parent_position_id)
        .where(
            positions.job_file_id == job_file_id,
            positions.is_sealed.is_(True),
            chain.c.position_id != boundary,
        )
    )
    return bool(
        await session.scalar(
            select(
                select(chain.c.position_id).where(chain.c.position_id == ancestor).exists()
                & select(chain.c.position_id).where(chain.c.position_id == boundary).exists()
            )
        )
    )
