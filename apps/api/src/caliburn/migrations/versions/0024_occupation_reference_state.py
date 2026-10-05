"""Persist Turn-scoped reference candidates and immutable original operation results."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0024_occupation_reference_state"
down_revision = "0023_jd_model_references"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "occupation_reference_operations",
        sa.Column("job_file_id", sa.Uuid(), nullable=False),
        sa.Column("operation_id", sa.Uuid(), nullable=False),
        sa.Column("execution_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("generation_id", sa.Uuid(), nullable=False),
        sa.Column("result_generation_id", sa.Uuid(), nullable=False),
        sa.Column("expected_revision_id", sa.Uuid(), nullable=True),
        sa.Column("parent_revision_id", sa.Uuid(), nullable=True),
        sa.Column("revision_id", sa.Uuid(), nullable=False),
        sa.Column("state", postgresql.JSONB(), nullable=False),
        sa.PrimaryKeyConstraint("job_file_id", "operation_id"),
        sa.UniqueConstraint(
            "job_file_id", "execution_id", "revision_id", name="uq_reference_revision"
        ),
        sa.ForeignKeyConstraint(
            ["job_file_id", "execution_id"],
            ["executions.job_file_id", "executions.execution_id"],
            name="fk_reference_operation_execution",
        ),
        sa.ForeignKeyConstraint(
            ["job_file_id", "execution_id", "expected_revision_id"],
            [
                "occupation_reference_operations.job_file_id",
                "occupation_reference_operations.execution_id",
                "occupation_reference_operations.revision_id",
            ],
            name="fk_reference_operation_expected",
        ),
        sa.ForeignKeyConstraint(
            ["job_file_id", "execution_id", "parent_revision_id"],
            [
                "occupation_reference_operations.job_file_id",
                "occupation_reference_operations.execution_id",
                "occupation_reference_operations.revision_id",
            ],
            name="fk_reference_operation_parent",
        ),
        sa.CheckConstraint(
            "kind IN ('start', 'apply', 'restore')", name="reference_operation_kind"
        ),
        sa.CheckConstraint(
            "(kind = 'start' AND expected_revision_id IS NULL AND parent_revision_id IS NULL) OR "
            "(kind <> 'start' AND expected_revision_id IS NOT NULL "
            "AND parent_revision_id IS NOT NULL)",
            name="reference_operation_ancestry",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(state) = 'object' "
            "AND state ?& ARRAY['selected_reference_ids', 'excluded_work'] "
            "AND state - 'selected_reference_ids' - 'excluded_work' = '{}'::jsonb "
            "AND (state->'selected_reference_ids' = 'null'::jsonb "
            "OR jsonb_typeof(state->'selected_reference_ids') = 'array') "
            "AND jsonb_typeof(state->'excluded_work') = 'array'",
            name="reference_state_shape",
        ),
    )
    op.create_table(
        "occupation_reference_candidates",
        sa.Column("job_file_id", sa.Uuid(), nullable=False),
        sa.Column("execution_id", sa.Uuid(), nullable=False),
        sa.Column("generation_id", sa.Uuid(), nullable=False),
        sa.Column("base_revision_id", sa.Uuid(), nullable=False),
        sa.Column("current_revision_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("job_file_id", "execution_id"),
        sa.ForeignKeyConstraint(
            ["job_file_id", "execution_id"],
            ["executions.job_file_id", "executions.execution_id"],
            name="fk_reference_candidate_execution",
        ),
        sa.ForeignKeyConstraint(
            ["job_file_id", "execution_id", "base_revision_id"],
            [
                "occupation_reference_operations.job_file_id",
                "occupation_reference_operations.execution_id",
                "occupation_reference_operations.revision_id",
            ],
            name="fk_reference_candidate_base",
        ),
        sa.ForeignKeyConstraint(
            ["job_file_id", "execution_id", "current_revision_id"],
            [
                "occupation_reference_operations.job_file_id",
                "occupation_reference_operations.execution_id",
                "occupation_reference_operations.revision_id",
            ],
            name="fk_reference_candidate_current",
        ),
    )
    op.execute("""
        CREATE FUNCTION reject_reference_operation_mutation() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'Reference operation results are immutable' USING ERRCODE = '23514';
        END
        $$
    """)
    op.execute("""
        CREATE TRIGGER protect_reference_operations
        BEFORE UPDATE OR DELETE ON occupation_reference_operations
        FOR EACH ROW EXECUTE FUNCTION reject_reference_operation_mutation()
    """)


def downgrade() -> None:
    raise RuntimeError("Reference states may be used by later Turns; do not discard their history")
