"""輪次擁有逐則原文；結構化答案只能指向同輪訊息。"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Identity,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from caliburn.shared.infrastructure.persistence.orm_base import OrmBase


class InterviewTurnRow(OrmBase):
    __tablename__ = "interview_turns"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('conversation', 'opening')", name="ck_interview_turns_kind"
        ),
        UniqueConstraint("sequence", name="uq_interview_turns_sequence"),
        Index(
            "uq_interview_turns_opening",
            "workspace_id",
            unique=True,
            postgresql_where=text("kind = 'opening'"),
        ),
    )

    workspace_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey(
            "workspaces.id", name="fk_interview_turns_workspace", ondelete="CASCADE"
        ),
        primary_key=True,
    )
    turn_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    sequence: Mapped[int] = mapped_column(BigInteger, Identity(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class InterviewMessageRow(OrmBase):
    __tablename__ = "interview_messages"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "turn_id"],
            ["interview_turns.workspace_id", "interview_turns.turn_id"],
            name="fk_interview_messages_turn",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "workspace_id", "turn_id", "position", name="uq_interview_messages_position"
        ),
        UniqueConstraint(
            "id", "workspace_id", "turn_id", name="uq_interview_messages_scoped_id"
        ),
        ForeignKeyConstraint(
            ["reply_to_message_id", "workspace_id", "turn_id"],
            [
                "interview_messages.id",
                "interview_messages.workspace_id",
                "interview_messages.turn_id",
            ],
            name="fk_interview_messages_reply",
        ),
        UniqueConstraint("reply_to_message_id", name="uq_interview_messages_reply"),
        CheckConstraint("position >= 0", name="ck_interview_messages_position"),
        CheckConstraint(
            "(kind = 'text' AND speaker IN ('app', 'employee', 'consultant')) OR "
            "(kind = 'question' AND speaker = 'consultant') OR "
            "(kind = 'answer' AND speaker = 'employee')",
            name="ck_interview_messages_kind_speaker",
        ),
        CheckConstraint(
            "(kind = 'answer') = (reply_to_message_id IS NOT NULL)",
            name="ck_interview_messages_reply",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    workspace_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    turn_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    speaker: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    reply_to_message_id: Mapped[UUID | None] = mapped_column(Uuid)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
