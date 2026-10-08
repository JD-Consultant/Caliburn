"""Add shared knowledge/skill content and fixed task-use relations."""

import sqlalchemy as sa
from alembic import op

revision = "0008_jd_capability_relations"
down_revision = "0007_jd_task_selections"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "jd_capability_revisions",
        sa.Column("job_file_id", sa.Uuid(), nullable=False),
        sa.Column("capability_id", sa.Uuid(), nullable=False),
        sa.Column("content_revision_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("name", sa.Text()),
        sa.Column("description", sa.Text()),
        sa.PrimaryKeyConstraint("job_file_id", "capability_id", "content_revision_id"),
        sa.ForeignKeyConstraint(["job_file_id"], ["job_files.job_file_id"]),
        sa.CheckConstraint(
            "kind IN ('knowledge', 'skill')", name=op.f("ck_jd_capability_revisions_kind")
        ),
        sa.CheckConstraint(
            "name IS NOT NULL OR description IS NOT NULL",
            name=op.f("ck_jd_capability_revisions_has_content"),
        ),
        sa.CheckConstraint(
            "name IS NULL OR length(btrim(name)) > 0",
            name=op.f("ck_jd_capability_revisions_name_content"),
        ),
        sa.CheckConstraint(
            "description IS NULL OR length(btrim(description)) > 0",
            name=op.f("ck_jd_capability_revisions_description_content"),
        ),
    )
    op.create_table(
        "jd_capability_selections",
        sa.Column("job_file_id", sa.Uuid(), nullable=False),
        sa.Column("revision_id", sa.Uuid(), nullable=False),
        sa.Column("capability_id", sa.Uuid(), nullable=False),
        sa.Column("content_revision_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("job_file_id", "revision_id", "capability_id"),
        sa.ForeignKeyConstraint(
            ["job_file_id", "revision_id"],
            ["jd_revisions.job_file_id", "jd_revisions.revision_id"],
            name="fk_jd_capability_selections_revision",
        ),
        sa.ForeignKeyConstraint(
            ["job_file_id", "capability_id", "content_revision_id"],
            [
                "jd_capability_revisions.job_file_id",
                "jd_capability_revisions.capability_id",
                "jd_capability_revisions.content_revision_id",
            ],
            name="fk_jd_capability_selections_content",
        ),
        sa.UniqueConstraint("job_file_id", "revision_id", "position"),
        sa.CheckConstraint("position >= 0", name=op.f("ck_jd_capability_selections_position")),
    )
    op.create_table(
        "jd_task_capabilities",
        sa.Column("job_file_id", sa.Uuid(), nullable=False),
        sa.Column("revision_id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("capability_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("job_file_id", "revision_id", "task_id", "capability_id"),
        sa.ForeignKeyConstraint(
            ["job_file_id", "revision_id", "task_id"],
            [
                "jd_task_selections.job_file_id",
                "jd_task_selections.revision_id",
                "jd_task_selections.task_id",
            ],
            name="fk_jd_task_capabilities_task",
        ),
        sa.ForeignKeyConstraint(
            ["job_file_id", "revision_id", "capability_id"],
            [
                "jd_capability_selections.job_file_id",
                "jd_capability_selections.revision_id",
                "jd_capability_selections.capability_id",
            ],
            name="fk_jd_task_capabilities_capability",
        ),
        sa.UniqueConstraint("job_file_id", "revision_id", "task_id", "position"),
        sa.CheckConstraint("position >= 0", name=op.f("ck_jd_task_capabilities_position")),
    )
    op.drop_constraint(op.f("ck_jd_operations_kind"), "jd_operations", type_="check")
    op.create_check_constraint(
        op.f("ck_jd_operations_kind"),
        "jd_operations",
        "kind IN ('revise_profile', 'edit_areas', 'edit_tasks', 'edit_capabilities')",
    )
    for table in ("jd_capability_revisions", "jd_capability_selections", "jd_task_capabilities"):
        op.execute(
            f"CREATE TRIGGER protect_{table} BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION reject_fixed_jd_mutation()"
        )
    for table in ("jd_capability_selections", "jd_task_capabilities"):
        op.execute(
            f"CREATE TRIGGER protect_{table}_insert BEFORE INSERT ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION protect_jd_area_selection_insert()"
        )


def downgrade() -> None:
    raise RuntimeError("Fixed capabilities and task relations must remain recoverable")
