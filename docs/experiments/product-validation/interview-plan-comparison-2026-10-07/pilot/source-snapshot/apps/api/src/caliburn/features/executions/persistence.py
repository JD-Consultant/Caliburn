"""PostgreSQL admission constraints and transaction-scoped execution row locks."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Text,
    UniqueConstraint,
    func,
    select,
    text,
)
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from caliburn.adapters.database import Base
from caliburn.features.executions.models import ExecutionKind, ExecutionScope, ExecutionStatus


class ExecutionRecord(Base):
    __tablename__ = "executions"
    __table_args__ = (
        UniqueConstraint("job_file_id", "execution_id"),
        CheckConstraint("kind IN ('consultant_turn', 'memory_batch')", name="kind"),
        CheckConstraint(
            "status IN ('active', 'paused', 'completed', 'cancelled', 'failed')", name="status"
        ),
        CheckConstraint(
            "kind = 'consultant_turn' OR status NOT IN ('paused', 'cancelled')",
            name="memory_control",
        ),
        CheckConstraint(
            "NOT pause_requested OR (kind = 'consultant_turn' AND status IN ('active', 'paused'))",
            name="pause_request_control",
        ),
        Index(
            "uq_executions_active_kind",
            "job_file_id",
            "kind",
            unique=True,
            postgresql_where=text("status IN ('active', 'paused')"),
        ),
    )

    execution_id: Mapped[UUID] = mapped_column(primary_key=True)
    job_file_id: Mapped[UUID] = mapped_column(
        ForeignKey("job_files.job_file_id", ondelete="CASCADE")
    )
    kind: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    writer_id: Mapped[UUID | None] = mapped_column()
    pause_requested: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


async def insert_execution(session: AsyncSession, scope: ExecutionScope) -> ExecutionRecord | None:
    return (
        await session.scalars(
            insert(ExecutionRecord)
            .values(
                execution_id=scope.execution_id,
                job_file_id=scope.job_file_id,
                kind=scope.kind.value,
                status=ExecutionStatus.ACTIVE.value,
            )
            .on_conflict_do_nothing()
            .returning(ExecutionRecord)
        )
    ).one_or_none()


async def read_execution(
    session: AsyncSession, scope: ExecutionScope, *, lock: bool = False
) -> ExecutionRecord | None:
    statement = (
        select(ExecutionRecord)
        .where(
            ExecutionRecord.execution_id == scope.execution_id,
            ExecutionRecord.job_file_id == scope.job_file_id,
            ExecutionRecord.kind == scope.kind.value,
        )
        .execution_options(populate_existing=True)
    )
    if lock:
        statement = statement.with_for_update()
    return (await session.scalars(statement)).one_or_none()


async def has_active_consultant(session: AsyncSession, job_file_id: UUID) -> bool:
    return (
        await session.scalar(
            select(ExecutionRecord.execution_id)
            .where(
                ExecutionRecord.job_file_id == job_file_id,
                ExecutionRecord.kind == "consultant_turn",
                ExecutionRecord.status.in_(("active", "paused")),
            )
            .limit(1)
        )
    ) is not None


async def has_live_work(session: AsyncSession, job_file_id: UUID) -> bool:
    """Whole-file deletion must wait for both consultant and Memory work."""
    return (
        await session.scalar(
            select(ExecutionRecord.execution_id)
            .where(
                ExecutionRecord.job_file_id == job_file_id,
                ExecutionRecord.status.in_(("active", "paused")),
            )
            .limit(1)
        )
    ) is not None


async def read_current_consultant(
    session: AsyncSession, job_file_id: UUID
) -> ExecutionRecord | None:
    """The admission index allows at most one active/paused A per file; no writer claim."""
    return (
        await session.scalars(
            select(ExecutionRecord)
            .where(
                ExecutionRecord.job_file_id == job_file_id,
                ExecutionRecord.kind == "consultant_turn",
                ExecutionRecord.status.in_((ExecutionStatus.ACTIVE, ExecutionStatus.PAUSED)),
            )
            .execution_options(populate_existing=True)
        )
    ).one_or_none()


async def list_active_consultants(session: AsyncSession) -> tuple[ExecutionRecord, ...]:
    records = await session.scalars(
        select(ExecutionRecord)
        .where(ExecutionRecord.kind == "consultant_turn", ExecutionRecord.status == "active")
        .order_by(ExecutionRecord.created_at, ExecutionRecord.execution_id)
    )
    return tuple(records)


async def read_completed_consultant_execution_ids(
    session: AsyncSession, job_file_id: UUID, execution_ids: tuple[UUID, ...]
) -> frozenset[UUID]:
    if not execution_ids:
        return frozenset()
    found = await session.scalars(
        select(ExecutionRecord.execution_id).where(
            ExecutionRecord.job_file_id == job_file_id,
            ExecutionRecord.execution_id.in_(execution_ids),
            ExecutionRecord.kind == ExecutionKind.CONSULTANT_TURN.value,
            ExecutionRecord.status == ExecutionStatus.COMPLETED.value,
        )
    )
    return frozenset(found)
