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
from caliburn.features.executions.models import ExecutionScope, ExecutionStatus


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
    job_file_id: Mapped[UUID] = mapped_column(ForeignKey("job_files.job_file_id"))
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
