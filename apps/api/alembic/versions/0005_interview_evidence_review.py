"""interview evidence add review (v2 風險分流;ADR 0027 T5)

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-08

訪談引擎 v2 風險分層(ADR 0027 §9.5;spec §11.3):低風險直寫的 evidence 標 review
供批次審(pending→accepted/reverted);既有列與 suggestion 路由的 evidence = 'auto'。
additive、有 server_default。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "interview_evidence",
        sa.Column("review", sa.Text(), nullable=False, server_default=sa.text("'auto'")),
    )


def downgrade() -> None:
    op.drop_column("interview_evidence", "review")
