"""Pin ordered direct sources and their reviewed JD baseline to each fixed revision."""

import sqlalchemy as sa
from alembic import op

revision = "0017_jd_source_references"
down_revision = "0016_context_histories"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "jd_source_references",
        sa.Column("job_file_id", sa.Uuid(), nullable=False),
        sa.Column("revision_id", sa.Uuid(), nullable=False),
        sa.Column("citation_id", sa.Uuid(), nullable=False),
        sa.Column("target_kind", sa.Text(), nullable=False),
        sa.Column("target_field", sa.Text()),
        sa.Column("target_item_id", sa.Uuid()),
        sa.Column("target_task_id", sa.Uuid()),
        sa.Column("source_kind", sa.Text(), nullable=False),
        sa.Column("interview_source_id", sa.Uuid()),
        sa.Column("memory_layer", sa.Text()),
        sa.Column("memory_snapshot_id", sa.Uuid()),
        sa.Column("memory_object_id", sa.Uuid()),
        sa.Column("memory_revision_id", sa.Uuid()),
        sa.Column("needs_review", sa.Boolean(), nullable=False),
        sa.Column("reviewed_revision_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("job_file_id", "revision_id", "citation_id"),
        sa.ForeignKeyConstraint(
            ["job_file_id", "revision_id"],
            ["jd_revisions.job_file_id", "jd_revisions.revision_id"],
            name="fk_jd_source_references_revision",
        ),
        sa.ForeignKeyConstraint(
            ["job_file_id", "reviewed_revision_id"],
            ["jd_revisions.job_file_id", "jd_revisions.revision_id"],
            name="fk_jd_source_references_reviewed_revision",
        ),
        sa.ForeignKeyConstraint(
            ["job_file_id", "interview_source_id"],
            ["interview_texts.job_file_id", "interview_texts.source_id"],
            name="fk_jd_source_references_interview",
        ),
        sa.ForeignKeyConstraint(
            ["job_file_id", "memory_snapshot_id"],
            ["memory_snapshots.job_file_id", "memory_snapshots.snapshot_id"],
            name="fk_jd_source_references_memory_snapshot",
        ),
        sa.ForeignKeyConstraint(
            ["job_file_id", "memory_object_id", "memory_revision_id"],
            [
                "memory_object_revisions.job_file_id",
                "memory_object_revisions.object_id",
                "memory_object_revisions.revision_id",
            ],
            name="fk_jd_source_references_memory_revision",
        ),
        sa.CheckConstraint(
            "(target_kind = 'profile_field' AND target_field IS NOT NULL "
            "AND target_field IN ('job_title', 'organization_unit', 'reports_to', 'purpose') "
            "AND target_item_id IS NULL AND target_task_id IS NULL) OR "
            "(target_kind IN ('area', 'task', 'capability', 'collaborator', 'condition') "
            "AND target_field IS NULL AND target_item_id IS NOT NULL "
            "AND target_task_id IS NULL) OR "
            "(target_kind IN ('detail', 'task_capability') AND target_field IS NULL "
            "AND target_item_id IS NOT NULL AND target_task_id IS NOT NULL)",
            name=op.f("ck_jd_source_references_target_shape"),
        ),
        sa.CheckConstraint(
            "(source_kind = 'interview' AND interview_source_id IS NOT NULL "
            "AND memory_layer IS NULL AND memory_snapshot_id IS NULL "
            "AND memory_object_id IS NULL AND memory_revision_id IS NULL) OR "
            "(source_kind = 'memory' AND interview_source_id IS NULL "
            "AND memory_layer IS NOT NULL "
            "AND memory_layer IN ('work_situation', 'work_understanding') "
            "AND memory_snapshot_id IS NOT NULL AND memory_object_id IS NOT NULL "
            "AND memory_revision_id IS NOT NULL)",
            name=op.f("ck_jd_source_references_source_shape"),
        ),
        sa.CheckConstraint("position >= 0", name=op.f("ck_jd_source_references_position")),
        sa.UniqueConstraint(
            "job_file_id", "revision_id", "position", name="uq_jd_source_references_position"
        ),
        sa.UniqueConstraint(
            "job_file_id",
            "revision_id",
            "target_kind",
            "target_field",
            "target_item_id",
            "target_task_id",
            "source_kind",
            "interview_source_id",
            "memory_layer",
            "memory_object_id",
            name="uq_jd_source_references_identity",
            postgresql_nulls_not_distinct=True,
        ),
    )
    op.execute(
        "CREATE TRIGGER protect_jd_source_references "
        "BEFORE UPDATE OR DELETE ON jd_source_references "
        "FOR EACH ROW EXECUTE FUNCTION reject_fixed_jd_mutation()"
    )
    op.execute(
        "CREATE TRIGGER protect_jd_source_references_insert "
        "BEFORE INSERT ON jd_source_references "
        "FOR EACH ROW EXECUTE FUNCTION protect_jd_area_selection_insert()"
    )
    op.drop_constraint(op.f("ck_jd_operations_kind"), "jd_operations", type_="check")
    op.create_check_constraint(
        op.f("ck_jd_operations_kind"),
        "jd_operations",
        "kind IN ('revise_profile', 'edit_areas', 'edit_tasks', 'edit_capabilities', "
        "'edit_collaborators', 'edit_conditions', 'restore_candidate', "
        "'discard_candidate', 'adopt_candidate', 'edit_sources')",
    )


def downgrade() -> None:
    raise RuntimeError("Fixed JD sources and reviewed baselines must remain recoverable")
