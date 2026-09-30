"""Add task content, separate detail groups and fixed per-JD membership."""

import sqlalchemy as sa
from alembic import op

revision = "0007_jd_task_selections"
down_revision = "0006_jd_area_selections"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "jd_task_revisions",
        sa.Column("job_file_id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("content_revision_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.Text()),
        sa.Column("description", sa.Text()),
        sa.PrimaryKeyConstraint("job_file_id", "task_id", "content_revision_id"),
        sa.ForeignKeyConstraint(["job_file_id"], ["job_files.job_file_id"]),
        sa.CheckConstraint(
            "title IS NOT NULL OR description IS NOT NULL",
            name=op.f("ck_jd_task_revisions_has_content"),
        ),
        sa.CheckConstraint(
            "title IS NULL OR length(btrim(title)) > 0",
            name=op.f("ck_jd_task_revisions_title_content"),
        ),
        sa.CheckConstraint(
            "description IS NULL OR length(btrim(description)) > 0",
            name=op.f("ck_jd_task_revisions_description_content"),
        ),
    )
    op.create_table(
        "jd_task_details",
        sa.Column("job_file_id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("content_revision_id", sa.Uuid(), nullable=False),
        sa.Column("detail_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("job_file_id", "task_id", "content_revision_id", "detail_id"),
        sa.ForeignKeyConstraint(
            ["job_file_id", "task_id", "content_revision_id"],
            [
                "jd_task_revisions.job_file_id",
                "jd_task_revisions.task_id",
                "jd_task_revisions.content_revision_id",
            ],
            name="fk_jd_task_details_content",
        ),
        sa.UniqueConstraint("job_file_id", "task_id", "content_revision_id", "kind", "position"),
        sa.CheckConstraint(
            "kind IN ('outcome', 'requirement')", name=op.f("ck_jd_task_details_kind")
        ),
        sa.CheckConstraint("length(btrim(text)) > 0", name=op.f("ck_jd_task_details_text_content")),
        sa.CheckConstraint("position >= 0", name=op.f("ck_jd_task_details_position")),
    )
    op.create_table(
        "jd_task_selections",
        sa.Column("job_file_id", sa.Uuid(), nullable=False),
        sa.Column("revision_id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("content_revision_id", sa.Uuid(), nullable=False),
        sa.Column("area_id", sa.Uuid()),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("job_file_id", "revision_id", "task_id"),
        sa.ForeignKeyConstraint(
            ["job_file_id", "revision_id"],
            ["jd_revisions.job_file_id", "jd_revisions.revision_id"],
            name="fk_jd_task_selections_revision",
        ),
        sa.ForeignKeyConstraint(
            ["job_file_id", "revision_id", "area_id"],
            [
                "jd_area_selections.job_file_id",
                "jd_area_selections.revision_id",
                "jd_area_selections.area_id",
            ],
            name="fk_jd_task_selections_area",
        ),
        sa.ForeignKeyConstraint(
            ["job_file_id", "task_id", "content_revision_id"],
            [
                "jd_task_revisions.job_file_id",
                "jd_task_revisions.task_id",
                "jd_task_revisions.content_revision_id",
            ],
            name="fk_jd_task_selections_content",
        ),
        sa.UniqueConstraint(
            "job_file_id", "revision_id", "area_id", "position", postgresql_nulls_not_distinct=True
        ),
        sa.CheckConstraint("position >= 0", name=op.f("ck_jd_task_selections_position")),
    )
    op.drop_constraint(op.f("ck_jd_operations_kind"), "jd_operations", type_="check")
    op.create_check_constraint(
        op.f("ck_jd_operations_kind"),
        "jd_operations",
        "kind IN ('revise_profile', 'edit_areas', 'edit_tasks')",
    )
    for table in ("jd_task_revisions", "jd_task_details", "jd_task_selections"):
        op.execute(
            f"CREATE TRIGGER protect_{table} BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION reject_fixed_jd_mutation()"
        )
    # Both membership tables share the same adoption guard; this uses its existing contract.
    op.execute(
        "CREATE TRIGGER protect_jd_task_selection_insert BEFORE INSERT ON jd_task_selections "
        "FOR EACH ROW EXECUTE FUNCTION protect_jd_area_selection_insert()"
    )
    op.execute("""
        CREATE FUNCTION protect_jd_task_detail_insert() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF EXISTS (SELECT 1 FROM jd_task_selections WHERE job_file_id = NEW.job_file_id
                AND task_id = NEW.task_id AND content_revision_id = NEW.content_revision_id) THEN
                RAISE EXCEPTION 'Cannot append details to selected fixed task content'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END
        $$
    """)
    op.execute(
        "CREATE TRIGGER protect_jd_task_detail_insert BEFORE INSERT ON jd_task_details "
        "FOR EACH ROW EXECUTE FUNCTION protect_jd_task_detail_insert()"
    )


def downgrade() -> None:
    raise RuntimeError("Fixed task content and membership must remain recoverable")
