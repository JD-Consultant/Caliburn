"""SQL for original messages and formal source membership; pending is not formal."""

from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Text,
    UniqueConstraint,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from caliburn.adapters.database import Base
from caliburn.features.interviews.models import InterviewMessage, InterviewSpeaker


class InterviewTextRecord(Base):
    __tablename__ = "interview_texts"
    __table_args__ = (
        UniqueConstraint("job_file_id", "source_id"),
        CheckConstraint("speaker IN ('app', 'employee', 'consultant')", name="speaker"),
        CheckConstraint("length(interview_text) > 0", name="nonempty_text"),
    )

    source_id: Mapped[UUID] = mapped_column(primary_key=True)
    job_file_id: Mapped[UUID] = mapped_column(ForeignKey("job_files.job_file_id"))
    speaker: Mapped[str] = mapped_column(Text)
    interview_text: Mapped[str] = mapped_column(Text)


class FormalInterviewRecord(Base):
    __tablename__ = "formal_interviews"
    __table_args__ = (
        ForeignKeyConstraint(
            ["job_file_id", "source_id"],
            ["interview_texts.job_file_id", "interview_texts.source_id"],
        ),
        UniqueConstraint("source_id"),
        CheckConstraint("interview_sequence > 0", name="positive_sequence"),
    )

    job_file_id: Mapped[UUID] = mapped_column(primary_key=True)
    interview_sequence: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[UUID] = mapped_column()


class InterviewInputRecord(Base):
    __tablename__ = "interview_inputs"
    __table_args__ = (
        ForeignKeyConstraint(
            ["job_file_id", "source_id"],
            ["interview_texts.job_file_id", "interview_texts.source_id"],
        ),
        ForeignKeyConstraint(
            ["job_file_id", "execution_id"],
            ["executions.job_file_id", "executions.execution_id"],
        ),
        UniqueConstraint("source_id"),
        UniqueConstraint("execution_id"),
    )

    job_file_id: Mapped[UUID] = mapped_column(primary_key=True)
    command_id: Mapped[UUID] = mapped_column(primary_key=True)
    source_id: Mapped[UUID] = mapped_column()
    execution_id: Mapped[UUID] = mapped_column()


async def read_input_submission(
    session: AsyncSession, *, job_file_id: UUID, command_id: UUID
) -> tuple[InterviewInputRecord, InterviewTextRecord] | None:
    row = (
        await session.execute(
            select(InterviewInputRecord, InterviewTextRecord)
            .join(InterviewTextRecord)
            .where(
                InterviewInputRecord.job_file_id == job_file_id,
                InterviewInputRecord.command_id == command_id,
            )
        )
    ).one_or_none()
    if row is None:
        return None
    return row[0], row[1]


async def insert_input(
    session: AsyncSession,
    *,
    job_file_id: UUID,
    command_id: UUID,
    source_id: UUID,
    execution_id: UUID,
    interview_text: str,
) -> None:
    session.add(
        InterviewTextRecord(
            source_id=source_id,
            job_file_id=job_file_id,
            speaker=InterviewSpeaker.EMPLOYEE.value,
            interview_text=interview_text,
        )
    )
    await session.flush()
    session.add(
        InterviewInputRecord(
            job_file_id=job_file_id,
            command_id=command_id,
            source_id=source_id,
            execution_id=execution_id,
        )
    )
    await session.flush()


async def insert_opening(
    session: AsyncSession, *, job_file_id: UUID, source_id: UUID, interview_text: str
) -> None:
    session.add(
        InterviewTextRecord(
            source_id=source_id,
            job_file_id=job_file_id,
            speaker=InterviewSpeaker.APP.value,
            interview_text=interview_text,
        )
    )
    await session.flush()
    session.add(
        FormalInterviewRecord(job_file_id=job_file_id, interview_sequence=1, source_id=source_id)
    )
    await session.flush()


async def list_formal_interviews(
    session: AsyncSession, job_file_id: UUID
) -> list[InterviewMessage]:
    rows = await session.execute(
        select(FormalInterviewRecord, InterviewTextRecord)
        .join(InterviewTextRecord)
        .where(FormalInterviewRecord.job_file_id == job_file_id)
        .order_by(FormalInterviewRecord.interview_sequence)
    )
    return [
        InterviewMessage(
            source_id=original.source_id,
            interview_sequence=formal.interview_sequence,
            speaker=InterviewSpeaker(original.speaker),
            interview_text=original.interview_text,
        )
        for formal, original in rows
    ]
