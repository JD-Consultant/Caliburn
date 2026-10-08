"""Add fixed collaborators and job-wide conditions to the existing JD revision boundary."""

import sqlalchemy as sa
from alembic import op

revision = "0009_jd_collaborators_conditions"
down_revision = "0008_jd_capability_relations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "jd_collaborator_revisions",
        sa.Column("job_file_id", sa.Uuid(), nullable=False),
        sa.Column("collaborator_id", sa.Uuid(), nullable=False),
        sa.Column("content_revision_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.Text()),
        sa.Column("scope_text", sa.Text()),
        sa.PrimaryKeyConstraint("job_file_id", "collaborator_id", "content_revision_id"),
        sa.ForeignKeyConstraint(["job_file_id"], ["job_files.job_file_id"]),
        sa.CheckConstraint(
            "name IS NOT NULL OR scope_text IS NOT NULL",
            name=op.f("ck_jd_collaborator_revisions_has_content"),
        ),
        sa.CheckConstraint(
            "name IS NULL OR length(btrim(name)) > 0",
            name=op.f("ck_jd_collaborator_revisions_name_content"),
        ),
        sa.CheckConstraint(
            "scope_text IS NULL OR length(btrim(scope_text)) > 0",
            name=op.f("ck_jd_collaborator_revisions_scope_content"),
        ),
    )
    op.create_table(
        "jd_collaborator_selections",
        sa.Column("job_file_id", sa.Uuid(), nullable=False),
        sa.Column("revision_id", sa.Uuid(), nullable=False),
        sa.Column("collaborator_id", sa.Uuid(), nullable=False),
        sa.Column("content_revision_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("job_file_id", "revision_id", "collaborator_id"),
        sa.ForeignKeyConstraint(
            ["job_file_id", "revision_id"],
            ["jd_revisions.job_file_id", "jd_revisions.revision_id"],
            name="fk_jd_collaborator_selections_revision",
        ),
        sa.ForeignKeyConstraint(
            ["job_file_id", "collaborator_id", "content_revision_id"],
            [
                "jd_collaborator_revisions.job_file_id",
                "jd_collaborator_revisions.collaborator_id",
                "jd_collaborator_revisions.content_revision_id",
            ],
            name="fk_jd_collaborator_selections_content",
        ),
        sa.UniqueConstraint("job_file_id", "revision_id", "position"),
        sa.CheckConstraint("position >= 0", name=op.f("ck_jd_collaborator_selections_position")),
    )
    op.create_table(
        "jd_condition_revisions",
        sa.Column("job_file_id", sa.Uuid(), nullable=False),
        sa.Column("condition_id", sa.Uuid(), nullable=False),
        sa.Column("content_revision_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("job_file_id", "condition_id", "content_revision_id"),
        sa.ForeignKeyConstraint(["job_file_id"], ["job_files.job_file_id"]),
        sa.CheckConstraint(
            "kind IN ('work_environment', 'schedule_travel', 'shared_authority', "
            "'shared_collaboration', 'qualification')",
            name=op.f("ck_jd_condition_revisions_kind"),
        ),
        sa.CheckConstraint(
            "length(btrim(text)) > 0", name=op.f("ck_jd_condition_revisions_text_content")
        ),
    )
    op.create_table(
        "jd_condition_selections",
        sa.Column("job_file_id", sa.Uuid(), nullable=False),
        sa.Column("revision_id", sa.Uuid(), nullable=False),
        sa.Column("condition_id", sa.Uuid(), nullable=False),
        sa.Column("content_revision_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("job_file_id", "revision_id", "condition_id"),
        sa.ForeignKeyConstraint(
            ["job_file_id", "revision_id"],
            ["jd_revisions.job_file_id", "jd_revisions.revision_id"],
            name="fk_jd_condition_selections_revision",
        ),
        sa.ForeignKeyConstraint(
            ["job_file_id", "condition_id", "content_revision_id"],
            [
                "jd_condition_revisions.job_file_id",
                "jd_condition_revisions.condition_id",
                "jd_condition_revisions.content_revision_id",
            ],
            name="fk_jd_condition_selections_content",
        ),
        sa.UniqueConstraint("job_file_id", "revision_id", "position"),
        sa.CheckConstraint("position >= 0", name=op.f("ck_jd_condition_selections_position")),
    )
    op.drop_constraint(op.f("ck_jd_operations_kind"), "jd_operations", type_="check")
    op.create_check_constraint(
        op.f("ck_jd_operations_kind"),
        "jd_operations",
        "kind IN ('revise_profile', 'edit_areas', 'edit_tasks', 'edit_capabilities', "
        "'edit_collaborators', 'edit_conditions')",
    )
    for table in (
        "jd_collaborator_revisions",
        "jd_collaborator_selections",
        "jd_condition_revisions",
        "jd_condition_selections",
    ):
        op.execute(
            f"CREATE TRIGGER protect_{table} BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION reject_fixed_jd_mutation()"
        )
    for table in ("jd_collaborator_selections", "jd_condition_selections"):
        op.execute(
            f"CREATE TRIGGER protect_{table}_insert BEFORE INSERT ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION protect_jd_area_selection_insert()"
        )


def downgrade() -> None:
    raise RuntimeError("Fixed collaborators and conditions must remain recoverable")
