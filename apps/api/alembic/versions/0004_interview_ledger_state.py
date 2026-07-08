"""interview sessions add ledger_state (v2 覆蓋帳本;ADR 0027 T2)

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-08

訪談引擎 v2:sessions 加 ledger_state(僅存不可重算的帳本狀態——
attempts 計數/tier_override/probe 設定;其餘由 doc 重算,12-Factor F5/F12)。
additive、有 server_default,既有列自動填 '{}'。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "interview_sessions",
        sa.Column("ledger_state", JSONB(), nullable=False,
                  server_default=sa.text("'{}'::jsonb")),
    )


def downgrade() -> None:
    op.drop_column("interview_sessions", "ledger_state")
