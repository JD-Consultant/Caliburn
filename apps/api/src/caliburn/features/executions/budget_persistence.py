"""Execution-owned budget storage; callers lock the execution before changing accounting."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    Text,
    case,
    func,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from caliburn.adapters.database import Base
from caliburn.features.executions.budget_models import BudgetUsage, OutboundKind


class ExecutionBudgetRecord(Base):
    __tablename__ = "execution_budgets"
    __table_args__ = (
        CheckConstraint(
            "max_model_steps > 0 AND max_compactions > 0 AND max_outbound_attempts > 0 "
            "AND max_attempts_per_request > 0",
            name="positive_limits",
        ),
        CheckConstraint("max_cost_usd > 0 AND max_cost_usd < 1000000000", name="positive_cost"),
        CheckConstraint("btrim(cost_basis) <> ''", name="cost_basis"),
    )

    execution_id: Mapped[UUID] = mapped_column(
        ForeignKey("executions.execution_id"), primary_key=True
    )
    max_model_steps: Mapped[int] = mapped_column()
    max_compactions: Mapped[int] = mapped_column()
    max_outbound_attempts: Mapped[int] = mapped_column()
    max_attempts_per_request: Mapped[int] = mapped_column()
    deadline_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    max_cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(18, 9))
    cost_basis: Mapped[str] = mapped_column(Text)


class OutboundAttemptRecord(Base):
    __tablename__ = "execution_outbound_attempts"
    __table_args__ = (
        CheckConstraint("kind IN ('model', 'compaction', 'token_count')", name="kind"),
        CheckConstraint("fingerprint ~ '^[0-9a-f]{64}$'", name="fingerprint"),
        CheckConstraint(
            "reserved_cost_usd > 0 AND reserved_cost_usd < 1000000000", name="reserved_cost"
        ),
        CheckConstraint(
            "reported_cost_usd IS NULL OR "
            "(reported_cost_usd >= 0 AND reported_cost_usd < 1000000000)",
            name="reported_cost",
        ),
        CheckConstraint(
            "failure_code IS NULL OR failure_code IN ('remote_result_unknown', "
            "'transient_service', 'rate_limited', 'access_blocked', 'capacity_exceeded', "
            "'request_rejected', 'response_protocol')",
            name="failure_code",
        ),
        CheckConstraint(
            "retry_not_before IS NULL OR (failure_code IS NOT NULL AND "
            "failure_code IN ('remote_result_unknown', 'transient_service', 'rate_limited'))",
            name="failure_retry",
        ),
        Index("ix_execution_outbound_attempts_request", "execution_id", "request_id"),
    )

    execution_id: Mapped[UUID] = mapped_column(
        ForeignKey("execution_budgets.execution_id"), primary_key=True
    )
    attempt_id: Mapped[UUID] = mapped_column(primary_key=True)
    request_id: Mapped[UUID] = mapped_column()
    kind: Mapped[str] = mapped_column(Text)
    fingerprint: Mapped[str] = mapped_column(Text)
    writer_id: Mapped[UUID] = mapped_column()
    reserved_cost_usd: Mapped[Decimal] = mapped_column(Numeric(18, 9))
    reported_cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(18, 9))
    failure_code: Mapped[str | None] = mapped_column(Text)
    retry_not_before: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    admitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp()
    )


async def read_budget(session: AsyncSession, execution_id: UUID) -> ExecutionBudgetRecord | None:
    return await session.get(ExecutionBudgetRecord, execution_id, populate_existing=True)


async def read_attempt(
    session: AsyncSession, execution_id: UUID, attempt_id: UUID
) -> OutboundAttemptRecord | None:
    return await session.get(
        OutboundAttemptRecord, (execution_id, attempt_id), populate_existing=True
    )


async def read_request_attempts(
    session: AsyncSession, execution_id: UUID, request_id: UUID
) -> list[OutboundAttemptRecord]:
    return list(
        await session.scalars(
            select(OutboundAttemptRecord).where(
                OutboundAttemptRecord.execution_id == execution_id,
                OutboundAttemptRecord.request_id == request_id,
            )
        )
    )


async def read_usage(session: AsyncSession, execution_id: UUID) -> BudgetUsage:
    row = (
        await session.execute(
            select(
                func.count(),
                func.count(
                    func.distinct(
                        case(
                            (
                                OutboundAttemptRecord.kind == OutboundKind.MODEL.value,
                                OutboundAttemptRecord.request_id,
                            )
                        )
                    )
                ),
                func.count(
                    func.distinct(
                        case(
                            (
                                OutboundAttemptRecord.kind == OutboundKind.COMPACTION.value,
                                OutboundAttemptRecord.request_id,
                            )
                        )
                    )
                ),
                func.coalesce(
                    func.sum(
                        func.coalesce(
                            OutboundAttemptRecord.reported_cost_usd,
                            OutboundAttemptRecord.reserved_cost_usd,
                        )
                    ),
                    Decimal(0),
                ),
            ).where(OutboundAttemptRecord.execution_id == execution_id)
        )
    ).one()
    return BudgetUsage(row[0], row[1], row[2], row[3])


async def current_time(session: AsyncSession) -> datetime:
    return (await session.execute(select(func.clock_timestamp()))).scalar_one()
