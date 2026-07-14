"""interview_llm_calls audit (v2 稽核落庫;ADR 0027 T13、spec §2)

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-08

訪談引擎 v2 自建 observability(§13 收編5;多租戶 B2B 稽核+棄用 SDK tracing 的補償):
每回合每次 LLM 呼叫落一列(role/model/耗時/工具呼叫/守衛判定)。token 欄 nullable
(adapter 未回 usage 時留空)。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "interview_llm_calls",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", UUID(as_uuid=True),
                  sa.ForeignKey("interview_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("turn_seq", sa.Integer(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),          # interview | select | backstop
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("tool_calls", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("guard_verdicts", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_interview_llm_calls_session", "interview_llm_calls", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_interview_llm_calls_session", table_name="interview_llm_calls")
    op.drop_table("interview_llm_calls")
