"""Scoped Memory batch coordinates and original results, with caller-owned transactions."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Text,
    UniqueConstraint,
    func,
    select,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from caliburn.adapters.database import Base


class MemoryBatchRecord(Base):
    __tablename__ = "memory_batches"
    __table_args__ = (
        ForeignKeyConstraint(
            ["job_file_id", "execution_id"],
            ["executions.job_file_id", "executions.execution_id"],
            name="fk_memory_batches_execution",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["job_file_id", "base_snapshot_id"],
            ["memory_snapshots.job_file_id", "memory_snapshots.snapshot_id"],
            name="fk_memory_batches_base_snapshot",
            use_alter=True,
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["job_file_id", "base_position_id"],
            ["memory_positions.job_file_id", "memory_positions.position_id"],
            name="fk_memory_batches_base_position",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["job_file_id", "current_position_id"],
            ["memory_positions.job_file_id", "memory_positions.position_id"],
            name="fk_memory_batches_current_position",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["job_file_id", "through_source_id"],
            ["interview_texts.job_file_id", "interview_texts.source_id"],
            name="fk_memory_batches_source_file",
            ondelete="CASCADE",
        ),
        CheckConstraint("phase IN ('work_situation', 'work_understanding')", name="phase"),
        CheckConstraint("status IN ('open', 'published', 'discarded')", name="status"),
        CheckConstraint(
            "0 <= covered_through_sequence AND covered_through_sequence < through_sequence",
            name="source_window",
        ),
    )

    job_file_id: Mapped[UUID] = mapped_column(primary_key=True)
    execution_id: Mapped[UUID] = mapped_column(primary_key=True)
    base_snapshot_id: Mapped[UUID | None]
    base_position_id: Mapped[UUID]
    current_position_id: Mapped[UUID]
    generation_id: Mapped[UUID]
    stage_id: Mapped[UUID]
    phase: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    through_source_id: Mapped[UUID] = mapped_column(
        ForeignKey("formal_interviews.source_id", ondelete="CASCADE")
    )
    covered_through_sequence: Mapped[int]
    through_sequence: Mapped[int]


class MemorySnapshotRecord(Base):
    __tablename__ = "memory_snapshots"
    __table_args__ = (
        ForeignKeyConstraint(
            ["job_file_id", "position_id"],
            ["memory_positions.job_file_id", "memory_positions.position_id"],
            name="fk_memory_snapshots_position",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["job_file_id", "execution_id"],
            ["memory_batches.job_file_id", "memory_batches.execution_id"],
            name="fk_memory_snapshots_batch",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["job_file_id", "through_source_id"],
            ["interview_texts.job_file_id", "interview_texts.source_id"],
            name="fk_memory_snapshots_source_file",
            ondelete="CASCADE",
        ),
        UniqueConstraint("job_file_id", "execution_id", name="uq_memory_snapshots_batch"),
        CheckConstraint("covered_through_sequence > 0", name="coverage"),
    )

    job_file_id: Mapped[UUID] = mapped_column(primary_key=True)
    snapshot_id: Mapped[UUID] = mapped_column(primary_key=True)
    position_id: Mapped[UUID]
    execution_id: Mapped[UUID]
    through_source_id: Mapped[UUID] = mapped_column(
        ForeignKey("formal_interviews.source_id", ondelete="CASCADE")
    )
    covered_through_sequence: Mapped[int]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MemoryHeadRecord(Base):
    __tablename__ = "memory_heads"
    __table_args__ = (
        ForeignKeyConstraint(
            ["job_file_id", "snapshot_id"],
            ["memory_snapshots.job_file_id", "memory_snapshots.snapshot_id"],
            name="fk_memory_heads_snapshot",
            ondelete="CASCADE",
        ),
    )

    job_file_id: Mapped[UUID] = mapped_column(
        ForeignKey("job_files.job_file_id", ondelete="CASCADE"), primary_key=True
    )
    snapshot_id: Mapped[UUID]


class MemoryOperationRecord(Base):
    __tablename__ = "memory_operations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["job_file_id", "execution_id"],
            ["executions.job_file_id", "executions.execution_id"],
            name="fk_memory_operations_execution",
            ondelete="CASCADE",
        ),
    )

    job_file_id: Mapped[UUID] = mapped_column(primary_key=True)
    command_id: Mapped[UUID] = mapped_column(primary_key=True)
    execution_id: Mapped[UUID]
    kind: Mapped[str] = mapped_column(Text)
    request_payload: Mapped[object] = mapped_column(JSONB)
    result_payload: Mapped[object] = mapped_column(JSONB)


async def read_batch(
    session: AsyncSession, job_file_id: UUID, execution_id: UUID
) -> MemoryBatchRecord | None:
    """Refresh coordinates after callers acquire the existing file/execution locks."""
    return await session.get(MemoryBatchRecord, (job_file_id, execution_id), populate_existing=True)


async def read_snapshot(
    session: AsyncSession, job_file_id: UUID, snapshot_id: UUID
) -> MemorySnapshotRecord | None:
    return await session.get(MemorySnapshotRecord, (job_file_id, snapshot_id))


async def read_head(session: AsyncSession, job_file_id: UUID) -> MemorySnapshotRecord | None:
    """Capture the currently published snapshot; a file may have no head yet."""
    return await session.scalar(
        select(MemorySnapshotRecord)
        .join(MemoryHeadRecord)
        .where(MemoryHeadRecord.job_file_id == job_file_id)
    )


async def set_head(session: AsyncSession, job_file_id: UUID, snapshot_id: UUID) -> None:
    """Adopt a snapshot after the caller locks the job file; never commit here."""
    head = await session.get(MemoryHeadRecord, job_file_id, populate_existing=True)
    if head is None:
        session.add(MemoryHeadRecord(job_file_id=job_file_id, snapshot_id=snapshot_id))
    else:
        head.snapshot_id = snapshot_id
    await session.flush()


async def read_operation(
    session: AsyncSession, job_file_id: UUID, command_id: UUID
) -> MemoryOperationRecord | None:
    return await session.get(MemoryOperationRecord, (job_file_id, command_id))


async def has_recorded_position(
    session: AsyncSession,
    job_file_id: UUID,
    execution_id: UUID,
    result_fields: dict[str, str],
) -> bool:
    """Require an original result with all six coordinates; extra result fields are allowed."""
    if (
        set(result_fields)
        != {"job_file_id", "execution_id", "generation_id", "stage_id", "phase", "position_id"}
        or result_fields["job_file_id"] != str(job_file_id)
        or result_fields["execution_id"] != str(execution_id)
    ):
        return False
    return bool(
        await session.scalar(
            select(
                select(MemoryOperationRecord.command_id)
                .where(
                    MemoryOperationRecord.job_file_id == job_file_id,
                    MemoryOperationRecord.execution_id == execution_id,
                    MemoryOperationRecord.result_payload.contains(result_fields),
                )
                .exists()
            )
        )
    )
