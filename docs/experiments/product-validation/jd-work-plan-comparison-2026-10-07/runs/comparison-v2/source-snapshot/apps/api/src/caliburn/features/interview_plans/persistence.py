"""Only plan-owned SQL: nullable full bodies, immutable operations and candidate pointers."""

from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    ForeignKeyConstraint,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    Uuid,
    column,
    select,
    values,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from caliburn.adapters.database import Base
from caliburn.features.interview_plans.models import QualifiedPlanTurn


class PlanOperationRecord(Base):
    __tablename__ = "interview_plan_operations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["job_file_id", "execution_id"],
            ["executions.job_file_id", "executions.execution_id"],
            name="fk_plan_operation_execution",
            ondelete="CASCADE",
        ),
        UniqueConstraint("job_file_id", "execution_id", "revision_id", name="uq_plan_revision"),
        ForeignKeyConstraint(
            ["job_file_id", "execution_id", "expected_revision_id"],
            [
                "interview_plan_operations.job_file_id",
                "interview_plan_operations.execution_id",
                "interview_plan_operations.revision_id",
            ],
            name="fk_plan_operation_expected",
            ondelete="CASCADE",
        ),
        CheckConstraint("kind IN ('start', 'apply')", name="plan_operation_kind"),
        CheckConstraint(
            "(kind = 'start' AND expected_revision_id IS NULL "
            "AND intent_digest IS NULL AND result_text IS NULL) OR "
            "(kind = 'apply' AND expected_revision_id IS NOT NULL "
            "AND intent_digest IS NOT NULL AND result_text IS NOT NULL)",
            name="plan_operation_shape",
        ),
        CheckConstraint("expected_revision_id <> revision_id", name="plan_operation_predecessor"),
        Index(
            "ix_interview_plan_operations_expected",
            "job_file_id",
            "execution_id",
            "expected_revision_id",
        ),
    )

    job_file_id: Mapped[UUID] = mapped_column(primary_key=True)
    operation_id: Mapped[UUID] = mapped_column(primary_key=True)
    execution_id: Mapped[UUID]
    kind: Mapped[str] = mapped_column(Text)
    expected_revision_id: Mapped[UUID | None]
    revision_id: Mapped[UUID]
    body: Mapped[str | None] = mapped_column(Text)
    intent_digest: Mapped[str | None] = mapped_column(Text)
    result_text: Mapped[str | None] = mapped_column(Text)


class PlanCandidateRecord(Base):
    __tablename__ = "interview_plan_candidates"
    __table_args__ = (
        ForeignKeyConstraint(
            ["job_file_id", "execution_id"],
            ["executions.job_file_id", "executions.execution_id"],
            name="fk_plan_candidate_execution",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["job_file_id", "execution_id", "base_revision_id"],
            [
                "interview_plan_operations.job_file_id",
                "interview_plan_operations.execution_id",
                "interview_plan_operations.revision_id",
            ],
            name="fk_plan_candidate_base",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["job_file_id", "execution_id", "current_revision_id"],
            [
                "interview_plan_operations.job_file_id",
                "interview_plan_operations.execution_id",
                "interview_plan_operations.revision_id",
            ],
            name="fk_plan_candidate_current",
            ondelete="CASCADE",
        ),
    )

    job_file_id: Mapped[UUID] = mapped_column(primary_key=True)
    execution_id: Mapped[UUID] = mapped_column(primary_key=True)
    base_revision_id: Mapped[UUID]
    current_revision_id: Mapped[UUID]


async def read_candidate(
    session: AsyncSession, job_file_id: UUID, execution_id: UUID
) -> PlanCandidateRecord | None:
    return await session.get(
        PlanCandidateRecord, (job_file_id, execution_id), populate_existing=True
    )


async def read_operation(
    session: AsyncSession, job_file_id: UUID, operation_id: UUID
) -> PlanOperationRecord | None:
    return await session.get(PlanOperationRecord, (job_file_id, operation_id))


async def read_revision(
    session: AsyncSession, job_file_id: UUID, execution_id: UUID, revision_id: UUID
) -> PlanOperationRecord | None:
    return await session.scalar(
        select(PlanOperationRecord).where(
            PlanOperationRecord.job_file_id == job_file_id,
            PlanOperationRecord.execution_id == execution_id,
            PlanOperationRecord.revision_id == revision_id,
        )
    )


async def read_qualified_operation(
    session: AsyncSession, job_file_id: UUID, qualified_turns: tuple[QualifiedPlanTurn, ...]
) -> PlanOperationRecord | None:
    """Join only our rows and parameterized owner-qualified metadata; return at most one body."""
    if not qualified_turns:
        return None
    qualified = (
        values(column("execution_id", Uuid), column("employee_input_sequence", Integer))
        .data([(turn.execution_id, turn.employee_input_sequence) for turn in qualified_turns])
        .cte("qualified_plan_turns")
    )
    return await session.scalar(
        select(PlanOperationRecord)
        .select_from(qualified)
        .join(
            PlanCandidateRecord,
            (PlanCandidateRecord.job_file_id == job_file_id)
            & (PlanCandidateRecord.execution_id == qualified.c.execution_id),
        )
        .join(
            PlanOperationRecord,
            (PlanOperationRecord.job_file_id == PlanCandidateRecord.job_file_id)
            & (PlanOperationRecord.execution_id == PlanCandidateRecord.execution_id)
            & (PlanOperationRecord.revision_id == PlanCandidateRecord.current_revision_id),
        )
        .order_by(qualified.c.employee_input_sequence.desc())
        .limit(1)
    )
