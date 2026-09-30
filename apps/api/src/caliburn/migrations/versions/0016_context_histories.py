"""Track adopted native checkpoint references without copying context payloads."""

import sqlalchemy as sa
from alembic import op

revision = "0016_context_histories"
down_revision = "0015_outbound_failures"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "context_history_heads",
        sa.Column(
            "job_file_id", sa.Uuid(), sa.ForeignKey("job_files.job_file_id"), primary_key=True
        ),
        sa.Column("role", sa.Text(), primary_key=True),
        sa.Column("thread_id", sa.Text()),
        sa.Column("checkpoint_id", sa.Text()),
        sa.Column("kind", sa.Text()),
        sa.CheckConstraint(
            "role IN ('job_consultant', 'work_situation_analyst', 'work_understanding_analyst')",
            name="role",
        ),
        sa.CheckConstraint(
            "(thread_id IS NULL AND checkpoint_id IS NULL AND kind IS NULL) OR "
            "(thread_id IS NOT NULL AND checkpoint_id IS NOT NULL AND kind IS NOT NULL "
            "AND length(btrim(thread_id)) > 0 AND length(btrim(checkpoint_id)) > 0 "
            "AND kind IN ('prepared_history', 'completed_work'))",
            name="position",
        ),
    )
    op.create_table(
        "context_history_bindings",
        sa.Column("execution_id", sa.Uuid(), primary_key=True),
        sa.Column("role", sa.Text(), primary_key=True),
        sa.Column("job_file_id", sa.Uuid(), nullable=False),
        sa.Column("base_thread_id", sa.Text()),
        sa.Column("base_checkpoint_id", sa.Text()),
        sa.Column("base_kind", sa.Text()),
        sa.Column("prepared_thread_id", sa.Text()),
        sa.Column("prepared_checkpoint_id", sa.Text()),
        sa.Column("completed_thread_id", sa.Text()),
        sa.Column("completed_checkpoint_id", sa.Text()),
        sa.ForeignKeyConstraint(
            ["job_file_id", "execution_id"], ["executions.job_file_id", "executions.execution_id"]
        ),
        sa.ForeignKeyConstraint(
            ["job_file_id", "role"],
            ["context_history_heads.job_file_id", "context_history_heads.role"],
        ),
        sa.CheckConstraint(
            "role IN ('job_consultant', 'work_situation_analyst', 'work_understanding_analyst')",
            name="role",
        ),
        sa.CheckConstraint(
            "(base_thread_id IS NULL AND base_checkpoint_id IS NULL AND base_kind IS NULL) OR "
            "(base_thread_id IS NOT NULL AND base_checkpoint_id IS NOT NULL "
            "AND base_kind IS NOT NULL AND length(btrim(base_thread_id)) > 0 "
            "AND length(btrim(base_checkpoint_id)) > 0 "
            "AND base_kind IN ('prepared_history', 'completed_work'))",
            name="base_position",
        ),
        sa.CheckConstraint(
            "(prepared_thread_id IS NULL AND prepared_checkpoint_id IS NULL) OR "
            "(prepared_thread_id IS NOT NULL AND prepared_checkpoint_id IS NOT NULL "
            "AND length(btrim(prepared_thread_id)) > 0 "
            "AND length(btrim(prepared_checkpoint_id)) > 0)",
            name="prepared_position",
        ),
        sa.CheckConstraint(
            "(completed_thread_id IS NULL AND completed_checkpoint_id IS NULL) OR "
            "(completed_thread_id IS NOT NULL AND completed_checkpoint_id IS NOT NULL "
            "AND length(btrim(completed_thread_id)) > 0 "
            "AND length(btrim(completed_checkpoint_id)) > 0 AND prepared_thread_id IS NOT NULL)",
            name="completed_position",
        ),
    )


def downgrade() -> None:
    raise RuntimeError("Adopted context references cannot be discarded by a destructive downgrade")
