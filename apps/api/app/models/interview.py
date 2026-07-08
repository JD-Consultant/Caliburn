"""訪談引擎 v1 資料模型(ADR 0023;spec 2026-07-05 §2)。

四張表:sessions(進度列=引擎唯一狀態)/ turns(逐字稿=溯源真相)/
evidence(槽值↔原話對照,顧問稽核)/ suggestions(建議層,ADR 0025)。
守則:同 profile 同時最多一個 active session——應用層檢查 + DB partial unique 雙保險。
"""
import uuid

from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey,
    Index, Integer, Text, UniqueConstraint, func,
)
from sqlalchemy import text as sa_text   # 別名:InterviewTurn.text 欄位會遮蔽同名函式
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.models.base import Base


class InterviewSession(Base):
    __tablename__ = "interview_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_profile_id = Column(
        UUID(as_uuid=True),
        ForeignKey("job_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    status = Column(Text, nullable=False, server_default=sa_text("'active'"))   # active/review/done
    phase = Column(Text, nullable=False, server_default=sa_text("'survey'"))    # survey/deep/review
    focus = Column(JSONB, nullable=False, server_default=sa_text("'{}'::jsonb"))
    counters = Column(JSONB, nullable=False, server_default=sa_text("'{}'::jsonb"))
    human_touched = Column(JSONB, nullable=False, server_default=sa_text("'[]'::jsonb"))
    # v2(ADR 0027;T2):覆蓋帳本不可重算的狀態(attempts/tier_override/probe);
    # 其餘一律由 doc 重算(12-Factor F5/F12)。
    ledger_state = Column(JSONB, nullable=False, server_default=sa_text("'{}'::jsonb"))

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        # 同 profile 最多一個 active(部分唯一索引;應用層先查,這裡兜同毫秒競態)
        Index(
            "uq_interview_sessions_one_active",
            "job_profile_id",
            unique=True,
            postgresql_where=sa_text("status = 'active'"),
        ),
    )


class InterviewTurn(Base):
    __tablename__ = "interview_turns"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(
        UUID(as_uuid=True),
        ForeignKey("interview_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    seq = Column(Integer, nullable=False)
    role = Column(Text, nullable=False)          # employee/consultant
    text = Column(Text, nullable=False)
    commands = Column(JSONB, nullable=False, server_default=sa_text("'[]'::jsonb"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("session_id", "seq", name="uq_interview_turns_session_seq"),
    )


class InterviewEvidence(Base):
    __tablename__ = "interview_evidence"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(
        UUID(as_uuid=True),
        ForeignKey("interview_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    doc_path = Column(Text, nullable=False)
    quote = Column(Text, nullable=False)
    turn_seq = Column(Integer, nullable=False)
    verified = Column(Boolean, nullable=False, server_default=sa_text("true"))
    # v2 風險分流(ADR 0027 T5):auto(v1/建議路由)/pending(低風險直寫待批)/accepted/reverted
    review = Column(Text, nullable=False, server_default=sa_text("'auto'"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class InterviewSuggestion(Base):
    __tablename__ = "interview_suggestions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(
        UUID(as_uuid=True),
        ForeignKey("interview_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    doc_path = Column(Text, nullable=False)
    old_value = Column(JSONB)
    new_value = Column(JSONB, nullable=False)
    reason = Column(Text, nullable=False, server_default=sa_text("''"))
    status = Column(Text, nullable=False, server_default=sa_text("'pending'"))  # pending/accepted/rejected
    turn_seq = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_interview_suggestions_session_status", "session_id", "status"),
    )
