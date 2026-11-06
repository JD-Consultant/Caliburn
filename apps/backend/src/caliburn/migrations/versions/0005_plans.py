"""新增目前 Plan 與取消恢復所需的完整版本。"""

import sqlalchemy as sa
from alembic import op

revision = "0005_plans"
down_revision = "0004_jd_name_length"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "plans",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.BigInteger(), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("workspace_id"),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_plans_workspace_id",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "version BETWEEN 1 AND 9007199254740991", name="ck_plans_version"
        ),
        sa.CheckConstraint("char_length(body) <= 16000", name="ck_plans_body_length"),
    )
    op.create_table(
        "plan_versions",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.BigInteger(), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("workspace_id", "version"),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["plans.workspace_id"],
            name="fk_plan_versions_workspace_id",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "version BETWEEN 1 AND 9007199254740991", name="ck_plan_versions_version"
        ),
        sa.CheckConstraint(
            "char_length(body) <= 16000", name="ck_plan_versions_body_length"
        ),
    )


def downgrade() -> None:
    op.drop_table("plan_versions")
    op.drop_table("plans")
