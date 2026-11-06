"""共用模型短碼：Workspace 範圍的種類／UUID 持久映射。"""

import sqlalchemy as sa
from alembic import op

revision = "0008_model_references"
down_revision = "0007_memory"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "model_references",
        sa.Column(
            "reference_number",
            sa.BigInteger(),
            sa.Identity(always=True),
            primary_key=True,
        ),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("resource_kind", sa.Text(), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_model_references_workspace",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "workspace_id",
            "resource_kind",
            "resource_id",
            name="uq_model_references_target",
        ),
        sa.CheckConstraint(
            "resource_kind IN ('message', 'duty', 'task', 'outcome', 'requirement', "
            "'knowledge', 'skill', 'collaboration', 'condition', 'occupation', "
            "'citation')",
            name="ck_model_references_kind",
        ),
    )


def downgrade() -> None:
    op.drop_table("model_references")
