"""document_versions add revision

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # document_versions.revision — 單一列的編輯回合計數（ADR 0015 精化；
    # 與既有 version「文件世系」語意分開）。SQLAlchemy version_id_col 樂觀鎖用（2a Task A）。
    # 加欄不動既有資料：server_default=1 讓既有列補值。
    # ------------------------------------------------------------------
    op.add_column(
        "document_versions",
        sa.Column("revision", sa.Integer(), server_default=sa.text("1"), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("document_versions", "revision")
