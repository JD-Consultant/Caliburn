"""SQL for original messages and formal source membership; pending is not formal."""

from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Select,
    Text,
    UniqueConstraint,
    func,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, aliased, mapped_column

from caliburn.adapters.database import Base
from caliburn.features.interviews.models import (
    FormalExchangePosition,
    InterviewHistoryEntry,
    InterviewMessage,
    InterviewSpeaker,
)


class InterviewTextRecord(Base):
    __tablename__ = "interview_texts"
    __table_args__ = (
        UniqueConstraint("job_file_id", "source_id"),
        CheckConstraint("speaker IN ('app', 'employee', 'consultant')", name="speaker"),
        CheckConstraint("length(interview_text) > 0", name="nonempty_text"),
    )

    source_id: Mapped[UUID] = mapped_column(primary_key=True)
    job_file_id: Mapped[UUID] = mapped_column(
        ForeignKey("job_files.job_file_id", ondelete="CASCADE")
    )
    speaker: Mapped[str] = mapped_column(Text)
    interview_text: Mapped[str] = mapped_column(Text)


class FormalInterviewRecord(Base):
    __tablename__ = "formal_interviews"
    __table_args__ = (
        ForeignKeyConstraint(
            ["job_file_id", "source_id"],
            ["interview_texts.job_file_id", "interview_texts.source_id"],
            ondelete="CASCADE",
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
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["job_file_id", "execution_id"],
            ["executions.job_file_id", "executions.execution_id"],
            ondelete="CASCADE",
        ),
        UniqueConstraint("source_id"),
        UniqueConstraint("execution_id"),
        UniqueConstraint(
            "job_file_id", "execution_id", name="uq_interview_inputs_job_file_id_execution_id"
        ),
    )

    job_file_id: Mapped[UUID] = mapped_column(primary_key=True)
    command_id: Mapped[UUID] = mapped_column(primary_key=True)
    source_id: Mapped[UUID] = mapped_column()
    execution_id: Mapped[UUID] = mapped_column()


class InterviewReplyRecord(Base):
    __tablename__ = "interview_replies"
    __table_args__ = (
        ForeignKeyConstraint(
            ["job_file_id", "execution_id"],
            ["interview_inputs.job_file_id", "interview_inputs.execution_id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["job_file_id", "source_id"],
            ["interview_texts.job_file_id", "interview_texts.source_id"],
            ondelete="CASCADE",
        ),
        UniqueConstraint("source_id"),
    )

    job_file_id: Mapped[UUID] = mapped_column(primary_key=True)
    execution_id: Mapped[UUID] = mapped_column(primary_key=True)
    source_id: Mapped[UUID] = mapped_column()


async def read_execution_input(
    session: AsyncSession, *, job_file_id: UUID, execution_id: UUID
) -> InterviewTextRecord | None:
    return (
        await session.scalars(
            select(InterviewTextRecord)
            .join(InterviewInputRecord)
            .where(
                InterviewInputRecord.job_file_id == job_file_id,
                InterviewInputRecord.execution_id == execution_id,
            )
        )
    ).one_or_none()


async def read_reply_source_id(
    session: AsyncSession, *, job_file_id: UUID, execution_id: UUID
) -> UUID | None:
    return await session.scalar(
        select(InterviewReplyRecord.source_id).where(
            InterviewReplyRecord.job_file_id == job_file_id,
            InterviewReplyRecord.execution_id == execution_id,
        )
    )


async def read_formal_frontier(session: AsyncSession, job_file_id: UUID) -> int:
    return (
        await session.scalar(
            select(func.max(FormalInterviewRecord.interview_sequence)).where(
                FormalInterviewRecord.job_file_id == job_file_id
            )
        )
    ) or 0


async def list_formal_exchange_positions(
    session: AsyncSession, job_file_id: UUID, through_sequence: int
) -> tuple[FormalExchangePosition, ...]:
    """Select metadata only; pending inputs and incomplete/mismatched exchanges are excluded."""
    rows = await session.execute(
        formal_exchange_positions_projection(job_file_id, through_sequence).order_by(
            "employee_input_sequence"
        )
    )
    return tuple(FormalExchangePosition(execution_id, sequence) for execution_id, sequence in rows)


def formal_exchange_positions_projection(
    job_file_id: UUID, through_sequence: int
) -> Select[UUID, int]:
    """正式配對及員工輸入上界由訪談 owner 維護，供具名跨域讀取組合。"""
    employee = aliased(FormalInterviewRecord)
    reply = aliased(FormalInterviewRecord)
    employee_text = aliased(InterviewTextRecord)
    reply_text = aliased(InterviewTextRecord)
    return (
        select(
            InterviewInputRecord.execution_id,
            employee.interview_sequence.label("employee_input_sequence"),
        )
        .join(
            InterviewReplyRecord,
            (InterviewReplyRecord.job_file_id == InterviewInputRecord.job_file_id)
            & (InterviewReplyRecord.execution_id == InterviewInputRecord.execution_id),
        )
        .join(
            employee,
            (employee.job_file_id == InterviewInputRecord.job_file_id)
            & (employee.source_id == InterviewInputRecord.source_id),
        )
        .join(
            reply,
            (reply.job_file_id == InterviewReplyRecord.job_file_id)
            & (reply.source_id == InterviewReplyRecord.source_id),
        )
        .join(employee_text, employee_text.source_id == employee.source_id)
        .join(reply_text, reply_text.source_id == reply.source_id)
        .where(
            InterviewInputRecord.job_file_id == job_file_id,
            employee.interview_sequence <= through_sequence,
            reply.interview_sequence > employee.interview_sequence,
            employee_text.speaker == InterviewSpeaker.EMPLOYEE.value,
            reply_text.speaker == InterviewSpeaker.CONSULTANT.value,
        )
    )


async def insert_formal_exchange(
    session: AsyncSession,
    *,
    job_file_id: UUID,
    execution_id: UUID,
    input_source_id: UUID,
    reply_source_id: UUID,
    reply_text: str,
    input_sequence: int,
) -> None:
    session.add(
        InterviewTextRecord(
            source_id=reply_source_id,
            job_file_id=job_file_id,
            speaker=InterviewSpeaker.CONSULTANT.value,
            interview_text=reply_text,
        )
    )
    await session.flush()
    session.add_all(
        [
            FormalInterviewRecord(
                job_file_id=job_file_id,
                interview_sequence=input_sequence,
                source_id=input_source_id,
            ),
            FormalInterviewRecord(
                job_file_id=job_file_id,
                interview_sequence=input_sequence + 1,
                source_id=reply_source_id,
            ),
            InterviewReplyRecord(
                job_file_id=job_file_id, execution_id=execution_id, source_id=reply_source_id
            ),
        ]
    )
    await session.flush()


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
    session: AsyncSession,
    job_file_id: UUID,
    *,
    sequences: tuple[int, ...] | None = None,
    start_sequence: int | None = None,
    end_sequence: int | None = None,
    source_ids: tuple[UUID, ...] | None = None,
) -> list[InterviewMessage]:
    statement = (
        select(FormalInterviewRecord, InterviewTextRecord)
        .join(InterviewTextRecord)
        .where(FormalInterviewRecord.job_file_id == job_file_id)
        .order_by(FormalInterviewRecord.interview_sequence)
    )
    if sequences is not None:
        statement = statement.where(FormalInterviewRecord.interview_sequence.in_(sequences))
    if start_sequence is not None:
        statement = statement.where(FormalInterviewRecord.interview_sequence >= start_sequence)
    if end_sequence is not None:
        statement = statement.where(FormalInterviewRecord.interview_sequence <= end_sequence)
    if source_ids is not None:
        statement = statement.where(FormalInterviewRecord.source_id.in_(source_ids))
    rows = await session.execute(statement)
    return [
        InterviewMessage(
            source_id=original.source_id,
            interview_sequence=formal.interview_sequence,
            speaker=InterviewSpeaker(original.speaker),
            interview_text=original.interview_text,
        )
        for formal, original in rows
    ]


async def list_public_interview_history(
    session: AsyncSession, job_file_id: UUID
) -> list[InterviewHistoryEntry]:
    """One scoped read from formal membership and its existing immutable reply relation."""
    rows = await session.execute(
        select(FormalInterviewRecord, InterviewTextRecord, InterviewReplyRecord.execution_id)
        .select_from(FormalInterviewRecord)
        .join(InterviewTextRecord)
        .outerjoin(
            InterviewReplyRecord,
            (InterviewReplyRecord.job_file_id == FormalInterviewRecord.job_file_id)
            & (InterviewReplyRecord.source_id == FormalInterviewRecord.source_id)
            & (InterviewTextRecord.speaker == InterviewSpeaker.CONSULTANT.value),
        )
        .where(FormalInterviewRecord.job_file_id == job_file_id)
        .order_by(FormalInterviewRecord.interview_sequence)
    )
    return [
        InterviewHistoryEntry(
            message=InterviewMessage(
                source_id=original.source_id,
                interview_sequence=formal.interview_sequence,
                speaker=InterviewSpeaker(original.speaker),
                interview_text=original.interview_text,
            ),
            execution_id=execution_id,
        )
        for formal, original, execution_id in rows
    ]


async def read_preceding_guidance_sequence(
    session: AsyncSession, *, job_file_id: UUID, before_sequence: int
) -> int | None:
    return await session.scalar(
        select(FormalInterviewRecord.interview_sequence)
        .join(InterviewTextRecord)
        .where(
            FormalInterviewRecord.job_file_id == job_file_id,
            FormalInterviewRecord.interview_sequence < before_sequence,
            InterviewTextRecord.speaker.in_((InterviewSpeaker.APP, InterviewSpeaker.CONSULTANT)),
        )
        .order_by(FormalInterviewRecord.interview_sequence.desc())
        .limit(1)
    )
