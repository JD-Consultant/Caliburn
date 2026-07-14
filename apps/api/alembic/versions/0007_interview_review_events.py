"""interview_review_events(ADR 0030 T2:✓/✗/批量拒絕無聲記帳)

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-13

追蹤修訂載體(_pending)之審閱事件:UI 端安靜、不觸發 AI;事件供 ledger 讀成
「上輪被拒清單」(下回合不重提、可追問)與 trace/evals 分析。
decision ∈ accepted | rejected | batch_rejected;op_meta 存 op 摘要(op/turn_id/value…)。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "interview_review_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("seq", sa.BigInteger(), sa.Identity(), nullable=False),  # 批量同刻的穩定序
        sa.Column("session_id", UUID(as_uuid=True),
                  sa.ForeignKey("interview_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("doc_path", sa.Text(), nullable=False),
        sa.Column("decision", sa.Text(), nullable=False),
        sa.Column("op_meta", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_interview_review_events_session", "interview_review_events",
                    ["session_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_interview_review_events_session", table_name="interview_review_events")
    op.drop_table("interview_review_events")
