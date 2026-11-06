"""建立 Workspace 初始資料表與完整性約束。"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_create_workspaces"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workspaces",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("interviewee_name", sa.Text(), nullable=False),
        sa.CheckConstraint(
            # 歷史 migration 固定當時集合，不從之後的業務程式重新計算。
            "length(btrim(interviewee_name, U&'"
            "\\0009\\000A\\000B\\000C\\000D\\001C\\001D\\001E\\001F\\0020"
            "\\0085\\00A0\\1680\\2000\\2001\\2002\\2003\\2004\\2005\\2006"
            "\\2007\\2008\\2009\\200A\\2028\\2029\\202F\\205F\\3000')) > 0",
            name="ck_workspaces_interviewee_name_not_blank",
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("workspaces")
