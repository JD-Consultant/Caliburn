"""Add execution-scoped JD candidate pointers and extend the existing operation history."""

import sqlalchemy as sa
from alembic import op

revision = "0010_jd_candidates"
down_revision = "0009_jd_collaborators_conditions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "jd_candidates",
        sa.Column("job_file_id", sa.Uuid(), nullable=False),
        sa.Column("execution_id", sa.Uuid(), nullable=False),
        sa.Column("base_revision_id", sa.Uuid(), nullable=False),
        sa.Column("current_revision_id", sa.Uuid(), nullable=False),
        sa.Column("generation_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("job_file_id", "execution_id"),
        sa.ForeignKeyConstraint(
            ["job_file_id", "execution_id"],
            ["executions.job_file_id", "executions.execution_id"],
            name="fk_jd_candidates_execution",
        ),
        sa.ForeignKeyConstraint(
            ["job_file_id", "base_revision_id"],
            ["jd_revisions.job_file_id", "jd_revisions.revision_id"],
            name="fk_jd_candidates_base_revision",
        ),
        sa.ForeignKeyConstraint(
            ["job_file_id", "current_revision_id"],
            ["jd_revisions.job_file_id", "jd_revisions.revision_id"],
            name="fk_jd_candidates_current_revision",
        ),
        sa.CheckConstraint(
            "status IN ('open', 'adopted', 'discarded')", name=op.f("ck_jd_candidates_status")
        ),
    )
    op.add_column("jd_operations", sa.Column("candidate_execution_id", sa.Uuid(), nullable=True))
    op.add_column("jd_operations", sa.Column("candidate_generation_id", sa.Uuid(), nullable=True))
    op.create_check_constraint(
        op.f("ck_jd_operations_candidate_scope"),
        "jd_operations",
        "(candidate_execution_id IS NULL) = (candidate_generation_id IS NULL)",
    )
    op.create_foreign_key(
        "fk_jd_operations_candidate",
        "jd_operations",
        "jd_candidates",
        ["job_file_id", "candidate_execution_id"],
        ["job_file_id", "execution_id"],
    )
    op.drop_constraint(op.f("ck_jd_operations_kind"), "jd_operations", type_="check")
    op.create_check_constraint(
        op.f("ck_jd_operations_kind"),
        "jd_operations",
        "kind IN ('revise_profile', 'edit_areas', 'edit_tasks', 'edit_capabilities', "
        "'edit_collaborators', 'edit_conditions', 'restore_candidate', "
        "'discard_candidate', 'adopt_candidate')",
    )
    # Existing immutable-operation and selection-insert triggers already seal every
    # operation result, including candidates that never become the formal head.


def downgrade() -> None:
    raise RuntimeError("JD candidate positions and original results must remain recoverable")
