"""JD-owned candidate positions; execution qualification and transactions belong to callers."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKeyConstraint, Text, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from caliburn.adapters.database import Base


class JdCandidateRecord(Base):
    __tablename__ = "jd_candidates"
    __table_args__ = (
        ForeignKeyConstraint(
            ["job_file_id", "execution_id"],
            ["executions.job_file_id", "executions.execution_id"],
            name="fk_jd_candidates_execution",
        ),
        ForeignKeyConstraint(
            ["job_file_id", "base_revision_id"],
            ["jd_revisions.job_file_id", "jd_revisions.revision_id"],
            name="fk_jd_candidates_base_revision",
        ),
        ForeignKeyConstraint(
            ["job_file_id", "current_revision_id"],
            ["jd_revisions.job_file_id", "jd_revisions.revision_id"],
            name="fk_jd_candidates_current_revision",
        ),
        CheckConstraint("status IN ('open', 'adopted', 'discarded')", name="status"),
    )

    job_file_id: Mapped[UUID] = mapped_column(primary_key=True)
    execution_id: Mapped[UUID] = mapped_column(primary_key=True)
    base_revision_id: Mapped[UUID]
    current_revision_id: Mapped[UUID]
    generation_id: Mapped[UUID]
    status: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


async def read_candidate(
    session: AsyncSession, job_file_id: UUID, execution_id: UUID
) -> JdCandidateRecord | None:
    """Refresh a scoped position after the caller acquires file/execution locks."""
    return await session.get(JdCandidateRecord, (job_file_id, execution_id), populate_existing=True)
