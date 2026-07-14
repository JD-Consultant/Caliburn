"""interview tables (sessions/turns/evidence/suggestions)

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-05

訪談引擎 v1(ADR 0023;spec 2026-07-05 §2):
- sessions = 進度列(引擎唯一狀態;partial unique 守「同 profile 一個 active」)
- turns = 逐字稿(溯源真相;(session_id, seq) 唯一)
- evidence = 槽值↔員工原話對照(顧問稽核)
- suggestions = 建議層(ADR 0025;(session_id, status) 索引供 pending 查詢)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "interview_sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("job_profile_id", UUID(as_uuid=True),
                  sa.ForeignKey("job_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'active'")),
        sa.Column("phase", sa.Text(), nullable=False, server_default=sa.text("'survey'")),
        sa.Column("focus", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("counters", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("human_touched", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "uq_interview_sessions_one_active",
        "interview_sessions",
        ["job_profile_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )

    op.create_table(
        "interview_turns",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", UUID(as_uuid=True),
                  sa.ForeignKey("interview_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("commands", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("session_id", "seq", name="uq_interview_turns_session_seq"),
    )

    op.create_table(
        "interview_evidence",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", UUID(as_uuid=True),
                  sa.ForeignKey("interview_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("doc_path", sa.Text(), nullable=False),
        sa.Column("quote", sa.Text(), nullable=False),
        sa.Column("turn_seq", sa.Integer(), nullable=False),
        sa.Column("verified", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_interview_evidence_session_id", "interview_evidence", ["session_id"])

    op.create_table(
        "interview_suggestions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", UUID(as_uuid=True),
                  sa.ForeignKey("interview_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("doc_path", sa.Text(), nullable=False),
        sa.Column("old_value", JSONB(), nullable=True),
        sa.Column("new_value", JSONB(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("turn_seq", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_interview_suggestions_session_status",
                    "interview_suggestions", ["session_id", "status"])


def downgrade() -> None:
    op.drop_table("interview_suggestions")
    op.drop_table("interview_evidence")
    op.drop_table("interview_turns")
    op.drop_index("uq_interview_sessions_one_active", table_name="interview_sessions")
    op.drop_table("interview_sessions")
