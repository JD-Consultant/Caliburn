"""Schema registration for a disposable, opt-in inspection copy of native checkpoints."""

from datetime import datetime
from uuid import UUID

from pydantic import JsonValue
from sqlalchemy import CheckConstraint, DateTime, ForeignKeyConstraint, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from caliburn.adapters.database import Base


class DiagnosticExecutionSnapshot(Base):
    __tablename__ = "diagnostic_execution_snapshots"
    __table_args__ = (
        ForeignKeyConstraint(
            ["job_file_id", "execution_id"],
            ["executions.job_file_id", "executions.execution_id"],
            ondelete="CASCADE",
        ),
        CheckConstraint("jsonb_typeof(steps) = 'array'", name="steps_array"),
    )

    execution_id: Mapped[UUID] = mapped_column(primary_key=True)
    job_file_id: Mapped[UUID] = mapped_column()
    snapshot_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    execution_status: Mapped[str] = mapped_column(Text)
    employee_input: Mapped[str | None] = mapped_column(Text)
    final_reply: Mapped[str | None] = mapped_column(Text)
    steps: Mapped[list[JsonValue]] = mapped_column(JSONB)
    captured_initial_context: Mapped[dict[str, JsonValue] | None] = mapped_column(JSONB)
