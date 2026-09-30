"""Reference-only context heads and execution bindings; native windows stay in the saver."""

from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, ForeignKeyConstraint, Text, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from caliburn.adapters.database import Base
from caliburn.features.executions.history_models import (
    AgentRole,
    ContextPosition,
    HistoryWindowKind,
)
from caliburn.features.executions.models import ExecutionScope


class ContextHistoryHeadRecord(Base):
    __tablename__ = "context_history_heads"
    __table_args__ = (
        CheckConstraint(
            "role IN ('job_consultant', 'work_situation_analyst', 'work_understanding_analyst')",
            name="role",
        ),
        CheckConstraint(
            "(thread_id IS NULL AND checkpoint_id IS NULL AND kind IS NULL) OR "
            "(thread_id IS NOT NULL AND checkpoint_id IS NOT NULL AND kind IS NOT NULL "
            "AND length(btrim(thread_id)) > 0 AND length(btrim(checkpoint_id)) > 0 "
            "AND kind IN ('prepared_history', 'completed_work'))",
            name="position",
        ),
    )

    job_file_id: Mapped[UUID] = mapped_column(ForeignKey("job_files.job_file_id"), primary_key=True)
    role: Mapped[str] = mapped_column(Text, primary_key=True)
    thread_id: Mapped[str | None] = mapped_column(Text)
    checkpoint_id: Mapped[str | None] = mapped_column(Text)
    kind: Mapped[str | None] = mapped_column(Text)


class ContextHistoryBindingRecord(Base):
    __tablename__ = "context_history_bindings"
    __table_args__ = (
        ForeignKeyConstraint(
            ["job_file_id", "execution_id"], ["executions.job_file_id", "executions.execution_id"]
        ),
        ForeignKeyConstraint(
            ["job_file_id", "role"],
            ["context_history_heads.job_file_id", "context_history_heads.role"],
        ),
        CheckConstraint(
            "role IN ('job_consultant', 'work_situation_analyst', 'work_understanding_analyst')",
            name="role",
        ),
        CheckConstraint(
            "(base_thread_id IS NULL AND base_checkpoint_id IS NULL AND base_kind IS NULL) OR "
            "(base_thread_id IS NOT NULL AND base_checkpoint_id IS NOT NULL "
            "AND base_kind IS NOT NULL AND length(btrim(base_thread_id)) > 0 "
            "AND length(btrim(base_checkpoint_id)) > 0 "
            "AND base_kind IN ('prepared_history', 'completed_work'))",
            name="base_position",
        ),
        CheckConstraint(
            "(prepared_thread_id IS NULL AND prepared_checkpoint_id IS NULL) OR "
            "(prepared_thread_id IS NOT NULL AND prepared_checkpoint_id IS NOT NULL "
            "AND length(btrim(prepared_thread_id)) > 0 "
            "AND length(btrim(prepared_checkpoint_id)) > 0)",
            name="prepared_position",
        ),
        CheckConstraint(
            "(completed_thread_id IS NULL AND completed_checkpoint_id IS NULL) OR "
            "(completed_thread_id IS NOT NULL AND completed_checkpoint_id IS NOT NULL "
            "AND length(btrim(completed_thread_id)) > 0 "
            "AND length(btrim(completed_checkpoint_id)) > 0 AND prepared_thread_id IS NOT NULL)",
            name="completed_position",
        ),
    )

    execution_id: Mapped[UUID] = mapped_column(primary_key=True)
    role: Mapped[str] = mapped_column(Text, primary_key=True)
    job_file_id: Mapped[UUID] = mapped_column()
    base_thread_id: Mapped[str | None] = mapped_column(Text)
    base_checkpoint_id: Mapped[str | None] = mapped_column(Text)
    base_kind: Mapped[str | None] = mapped_column(Text)
    prepared_thread_id: Mapped[str | None] = mapped_column(Text)
    prepared_checkpoint_id: Mapped[str | None] = mapped_column(Text)
    completed_thread_id: Mapped[str | None] = mapped_column(Text)
    completed_checkpoint_id: Mapped[str | None] = mapped_column(Text)


async def read_binding(
    session: AsyncSession, scope: ExecutionScope, role: AgentRole
) -> ContextHistoryBindingRecord | None:
    return (
        await session.scalars(
            select(ContextHistoryBindingRecord)
            .where(
                ContextHistoryBindingRecord.job_file_id == scope.job_file_id,
                ContextHistoryBindingRecord.execution_id == scope.execution_id,
                ContextHistoryBindingRecord.role == role.value,
            )
            .execution_options(populate_existing=True)
        )
    ).one_or_none()


async def read_head(
    session: AsyncSession, job_file_id: UUID, role: AgentRole, *, lock: bool = False
) -> ContextHistoryHeadRecord | None:
    statement = (
        select(ContextHistoryHeadRecord)
        .where(
            ContextHistoryHeadRecord.job_file_id == job_file_id,
            ContextHistoryHeadRecord.role == role.value,
        )
        .execution_options(populate_existing=True)
    )
    if lock:
        statement = statement.with_for_update()
    return (await session.scalars(statement)).one_or_none()


async def lock_head(
    session: AsyncSession, job_file_id: UUID, role: AgentRole
) -> ContextHistoryHeadRecord:
    # An empty row gives the first adoption the same row lock as subsequent adoptions.
    await session.execute(
        insert(ContextHistoryHeadRecord)
        .values(job_file_id=job_file_id, role=role.value)
        .on_conflict_do_nothing()
    )
    record = await read_head(session, job_file_id, role, lock=True)
    if record is None:
        raise RuntimeError("The context head disappeared within its transaction")
    return record


async def read_position_origin(
    session: AsyncSession, job_file_id: UUID, role: AgentRole, position: ContextPosition
) -> ContextHistoryBindingRecord | None:
    """Resolve a saved reference by equality, not by decoding native thread identifiers.

    Cancelled Turns may reuse a prepared window. Their self-referential copies are
    not the producer; only the original binding has a different (possibly empty) base.
    """
    record = ContextHistoryBindingRecord
    statement = select(record).where(record.job_file_id == job_file_id, record.role == role.value)
    if position.kind == HistoryWindowKind.COMPLETED_WORK:
        statement = statement.where(
            record.completed_thread_id == position.thread_id,
            record.completed_checkpoint_id == position.checkpoint_id,
        )
    else:
        statement = statement.where(
            record.prepared_thread_id == position.thread_id,
            record.prepared_checkpoint_id == position.checkpoint_id,
            or_(
                record.base_thread_id.is_(None),
                record.base_thread_id != position.thread_id,
                record.base_checkpoint_id != position.checkpoint_id,
            ),
        )
    return (await session.scalars(statement)).one_or_none()
