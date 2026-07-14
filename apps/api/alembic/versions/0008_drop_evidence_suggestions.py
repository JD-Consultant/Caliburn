"""0008(T12;ADR 0030):落 interview_evidence / interview_suggestions。

v3 起溯源住文件 `_pending.src`、審閱住 interview_review_events;T4 後兩表無寫入方。
draft 期產品無存量包袱——歷史資料不搬,直刪(plan T12 裁決)。
downgrade 重建空表(結構同 0002/0005 時期),資料不可逆。
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table("interview_suggestions")
    op.drop_table("interview_evidence")


def downgrade() -> None:
    op.create_table(
        "interview_evidence",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", UUID(as_uuid=True),
                  sa.ForeignKey("interview_sessions.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("doc_path", sa.Text, nullable=False),
        sa.Column("quote", sa.Text, nullable=False),
        sa.Column("turn_seq", sa.Integer, nullable=False),
        sa.Column("verified", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("review", sa.Text, nullable=False, server_default=sa.text("'auto'")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "interview_suggestions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", UUID(as_uuid=True),
                  sa.ForeignKey("interview_sessions.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("doc_path", sa.Text, nullable=False),
        sa.Column("old_value", JSONB),
        sa.Column("new_value", JSONB, nullable=False),
        sa.Column("reason", sa.Text, nullable=False, server_default=sa.text("''")),
        sa.Column("status", sa.Text, nullable=False, server_default=sa.text("'pending'")),
        sa.Column("turn_seq", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_interview_suggestions_session_status",
                    "interview_suggestions", ["session_id", "status"])
