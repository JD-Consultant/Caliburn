"""Scoped reference candidate coordinates and immutable operation state snapshots."""

from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Text, UniqueConstraint, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from caliburn.adapters.database import Base
from caliburn.features.occupation_references.models import (
    OccupationReferenceState,
    ReferenceStateError,
)


class ReferenceOperationRecord(Base):
    __tablename__ = "occupation_reference_operations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["job_file_id", "execution_id"],
            ["executions.job_file_id", "executions.execution_id"],
            name="fk_reference_operation_execution",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "job_file_id", "execution_id", "revision_id", name="uq_reference_revision"
        ),
        ForeignKeyConstraint(
            ["job_file_id", "execution_id", "expected_revision_id"],
            [
                "occupation_reference_operations.job_file_id",
                "occupation_reference_operations.execution_id",
                "occupation_reference_operations.revision_id",
            ],
            name="fk_reference_operation_expected",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["job_file_id", "execution_id", "parent_revision_id"],
            [
                "occupation_reference_operations.job_file_id",
                "occupation_reference_operations.execution_id",
                "occupation_reference_operations.revision_id",
            ],
            name="fk_reference_operation_parent",
            ondelete="CASCADE",
        ),
        CheckConstraint("kind IN ('start', 'apply', 'restore')", name="reference_operation_kind"),
        CheckConstraint(
            "(kind = 'start' AND expected_revision_id IS NULL AND parent_revision_id IS NULL) OR "
            "(kind <> 'start' AND expected_revision_id IS NOT NULL "
            "AND parent_revision_id IS NOT NULL)",
            name="reference_operation_ancestry",
        ),
        CheckConstraint(
            "jsonb_typeof(state) = 'object' "
            "AND state ?& ARRAY['selected_reference_ids', 'excluded_work'] "
            "AND state - 'selected_reference_ids' - 'excluded_work' = '{}'::jsonb "
            "AND (state->'selected_reference_ids' = 'null'::jsonb "
            "OR jsonb_typeof(state->'selected_reference_ids') = 'array') "
            "AND jsonb_typeof(state->'excluded_work') = 'array'",
            name="reference_state_shape",
        ),
    )

    job_file_id: Mapped[UUID] = mapped_column(primary_key=True)
    operation_id: Mapped[UUID] = mapped_column(primary_key=True)
    execution_id: Mapped[UUID]
    kind: Mapped[str] = mapped_column(Text)
    generation_id: Mapped[UUID]
    result_generation_id: Mapped[UUID]
    expected_revision_id: Mapped[UUID | None]
    parent_revision_id: Mapped[UUID | None]
    revision_id: Mapped[UUID]
    state: Mapped[object] = mapped_column(JSONB)


class ReferenceCandidateRecord(Base):
    __tablename__ = "occupation_reference_candidates"
    __table_args__ = (
        ForeignKeyConstraint(
            ["job_file_id", "execution_id"],
            ["executions.job_file_id", "executions.execution_id"],
            name="fk_reference_candidate_execution",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["job_file_id", "execution_id", "base_revision_id"],
            [
                "occupation_reference_operations.job_file_id",
                "occupation_reference_operations.execution_id",
                "occupation_reference_operations.revision_id",
            ],
            name="fk_reference_candidate_base",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["job_file_id", "execution_id", "current_revision_id"],
            [
                "occupation_reference_operations.job_file_id",
                "occupation_reference_operations.execution_id",
                "occupation_reference_operations.revision_id",
            ],
            name="fk_reference_candidate_current",
            ondelete="CASCADE",
        ),
    )

    job_file_id: Mapped[UUID] = mapped_column(primary_key=True)
    execution_id: Mapped[UUID] = mapped_column(primary_key=True)
    generation_id: Mapped[UUID]
    base_revision_id: Mapped[UUID]
    current_revision_id: Mapped[UUID]


async def read_candidate(
    session: AsyncSession, job_file_id: UUID, execution_id: UUID
) -> ReferenceCandidateRecord | None:
    return await session.get(
        ReferenceCandidateRecord, (job_file_id, execution_id), populate_existing=True
    )


async def list_candidates(
    session: AsyncSession, job_file_id: UUID
) -> tuple[ReferenceCandidateRecord, ...]:
    records = await session.scalars(
        select(ReferenceCandidateRecord)
        .where(ReferenceCandidateRecord.job_file_id == job_file_id)
        .order_by(ReferenceCandidateRecord.execution_id)
        .execution_options(populate_existing=True)
    )
    return tuple(records)


async def read_operation(
    session: AsyncSession, job_file_id: UUID, operation_id: UUID
) -> ReferenceOperationRecord | None:
    return await session.get(ReferenceOperationRecord, (job_file_id, operation_id))


async def read_revision(
    session: AsyncSession, job_file_id: UUID, execution_id: UUID, revision_id: UUID
) -> ReferenceOperationRecord | None:
    return await session.scalar(
        select(ReferenceOperationRecord).where(
            ReferenceOperationRecord.job_file_id == job_file_id,
            ReferenceOperationRecord.execution_id == execution_id,
            ReferenceOperationRecord.revision_id == revision_id,
        )
    )


def state_payload(state: OccupationReferenceState) -> dict[str, object]:
    return {
        "selected_reference_ids": (
            list(state.selected_reference_ids) if state.selected_reference_ids is not None else None
        ),
        "excluded_work": list(state.excluded_work),
    }


def state_value(value: object) -> OccupationReferenceState:
    if not isinstance(value, dict) or set(value) != {"selected_reference_ids", "excluded_work"}:
        raise ReferenceStateError("The saved reference state shape is invalid")
    references = value["selected_reference_ids"]
    if references is not None and (
        not isinstance(references, list) or any(not isinstance(item, str) for item in references)
    ):
        raise ReferenceStateError("The saved reference selection is invalid")
    excluded_work = value["excluded_work"]
    if not isinstance(excluded_work, list) or any(
        not isinstance(item, str) for item in excluded_work
    ):
        raise ReferenceStateError("The saved excluded work is invalid")
    return OccupationReferenceState(
        tuple(references) if references is not None else None, tuple(excluded_work)
    )
