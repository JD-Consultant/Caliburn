"""新增訪談輪次與逐則原話，答案範圍由複合外鍵維護。"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0006_interviews"
down_revision = "0005_plans"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "interview_turns",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("turn_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("sequence", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("withdrawn_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("workspace_id", "turn_id"),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_interview_turns_workspace",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "kind IN ('conversation', 'opening')", name="ck_interview_turns_kind"
        ),
        sa.UniqueConstraint("sequence", name="uq_interview_turns_sequence"),
    )
    op.create_index(
        "uq_interview_turns_opening",
        "interview_turns",
        ["workspace_id"],
        unique=True,
        postgresql_where=sa.text("kind = 'opening'"),
    )
    op.create_table(
        "interview_messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("turn_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("speaker", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("content", postgresql.JSONB(), nullable=False),
        sa.Column("reply_to_message_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["workspace_id", "turn_id"],
            ["interview_turns.workspace_id", "interview_turns.turn_id"],
            name="fk_interview_messages_turn",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "workspace_id", "turn_id", "position", name="uq_interview_messages_position"
        ),
        sa.UniqueConstraint(
            "id", "workspace_id", "turn_id", name="uq_interview_messages_scoped_id"
        ),
        sa.ForeignKeyConstraint(
            ["reply_to_message_id", "workspace_id", "turn_id"],
            [
                "interview_messages.id",
                "interview_messages.workspace_id",
                "interview_messages.turn_id",
            ],
            name="fk_interview_messages_reply",
        ),
        sa.UniqueConstraint("reply_to_message_id", name="uq_interview_messages_reply"),
        sa.CheckConstraint("position >= 0", name="ck_interview_messages_position"),
        sa.CheckConstraint(
            "(kind = 'text' AND speaker IN ('app', 'employee', 'consultant')) OR "
            "(kind = 'question' AND speaker = 'consultant') OR "
            "(kind = 'answer' AND speaker = 'employee')",
            name="ck_interview_messages_kind_speaker",
        ),
        sa.CheckConstraint(
            "(kind = 'answer') = (reply_to_message_id IS NOT NULL)",
            name="ck_interview_messages_reply",
        ),
    )


def downgrade() -> None:
    op.drop_table("interview_messages")
    op.drop_table("interview_turns")
