"""Keep Turn-local plan bases and immutable full effects, including original tool results."""

import sqlalchemy as sa
from alembic import op

revision = "0026_interview_plans"
down_revision = "0025_job_file_deletion"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "interview_plan_operations",
        sa.Column("job_file_id", sa.Uuid(), nullable=False),
        sa.Column("operation_id", sa.Uuid(), nullable=False),
        sa.Column("execution_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("expected_revision_id", sa.Uuid(), nullable=True),
        sa.Column("revision_id", sa.Uuid(), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("intent_digest", sa.Text(), nullable=True),
        sa.Column("result_text", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("job_file_id", "operation_id"),
        sa.UniqueConstraint("job_file_id", "execution_id", "revision_id", name="uq_plan_revision"),
        sa.ForeignKeyConstraint(
            ["job_file_id", "execution_id"],
            ["executions.job_file_id", "executions.execution_id"],
            name="fk_plan_operation_execution",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["job_file_id", "execution_id", "expected_revision_id"],
            [
                "interview_plan_operations.job_file_id",
                "interview_plan_operations.execution_id",
                "interview_plan_operations.revision_id",
            ],
            name="fk_plan_operation_expected",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint("kind IN ('start', 'apply')", name="plan_operation_kind"),
        sa.CheckConstraint(
            "(kind = 'start' AND expected_revision_id IS NULL "
            "AND intent_digest IS NULL AND result_text IS NULL) OR "
            "(kind = 'apply' AND expected_revision_id IS NOT NULL "
            "AND intent_digest IS NOT NULL AND result_text IS NOT NULL)",
            name="plan_operation_shape",
        ),
        sa.CheckConstraint(
            "expected_revision_id <> revision_id", name="plan_operation_predecessor"
        ),
    )
    op.create_index(
        "ix_interview_plan_operations_expected",
        "interview_plan_operations",
        ["job_file_id", "execution_id", "expected_revision_id"],
    )
    op.create_table(
        "interview_plan_candidates",
        sa.Column("job_file_id", sa.Uuid(), nullable=False),
        sa.Column("execution_id", sa.Uuid(), nullable=False),
        sa.Column("base_revision_id", sa.Uuid(), nullable=False),
        sa.Column("current_revision_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("job_file_id", "execution_id"),
        sa.ForeignKeyConstraint(
            ["job_file_id", "execution_id"],
            ["executions.job_file_id", "executions.execution_id"],
            name="fk_plan_candidate_execution",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["job_file_id", "execution_id", "base_revision_id"],
            [
                "interview_plan_operations.job_file_id",
                "interview_plan_operations.execution_id",
                "interview_plan_operations.revision_id",
            ],
            name="fk_plan_candidate_base",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["job_file_id", "execution_id", "current_revision_id"],
            [
                "interview_plan_operations.job_file_id",
                "interview_plan_operations.execution_id",
                "interview_plan_operations.revision_id",
            ],
            name="fk_plan_candidate_current",
            ondelete="CASCADE",
        ),
    )
    op.execute("""
        CREATE FUNCTION reject_plan_operation_mutation() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'Plan operation results are immutable' USING ERRCODE = '23514';
        END $$;
        CREATE TRIGGER protect_plan_operations
        BEFORE UPDATE OR DELETE ON interview_plan_operations
        FOR EACH ROW WHEN (job_file_row_is_present(to_jsonb(OLD)))
        EXECUTE FUNCTION reject_plan_operation_mutation();
    """)


def downgrade() -> None:
    raise RuntimeError("Plan positions may be retained by later requests; do not discard history")
