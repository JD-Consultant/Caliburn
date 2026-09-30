"""Add reusable area content and ordered membership in fixed JD revisions."""

import sqlalchemy as sa
from alembic import op

revision = "0006_jd_area_selections"
down_revision = "0005_jd_profile_revisions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "jd_area_revisions",
        sa.Column("job_file_id", sa.Uuid(), nullable=False),
        sa.Column("area_id", sa.Uuid(), nullable=False),
        sa.Column("content_revision_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.Text()),
        sa.Column("scope_text", sa.Text()),
        sa.PrimaryKeyConstraint("job_file_id", "area_id", "content_revision_id"),
        sa.ForeignKeyConstraint(["job_file_id"], ["job_files.job_file_id"]),
        sa.CheckConstraint(
            "title IS NOT NULL OR scope_text IS NOT NULL",
            name=op.f("ck_jd_area_revisions_has_content"),
        ),
        sa.CheckConstraint(
            "title IS NULL OR length(btrim(title)) > 0",
            name=op.f("ck_jd_area_revisions_title_content"),
        ),
        sa.CheckConstraint(
            "scope_text IS NULL OR length(btrim(scope_text)) > 0",
            name=op.f("ck_jd_area_revisions_scope_content"),
        ),
    )
    op.create_table(
        "jd_area_selections",
        sa.Column("job_file_id", sa.Uuid(), nullable=False),
        sa.Column("revision_id", sa.Uuid(), nullable=False),
        sa.Column("area_id", sa.Uuid(), nullable=False),
        sa.Column("content_revision_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("job_file_id", "revision_id", "area_id"),
        sa.ForeignKeyConstraint(
            ["job_file_id", "revision_id"],
            ["jd_revisions.job_file_id", "jd_revisions.revision_id"],
            name="fk_jd_area_selections_revision",
        ),
        sa.ForeignKeyConstraint(
            ["job_file_id", "area_id", "content_revision_id"],
            [
                "jd_area_revisions.job_file_id",
                "jd_area_revisions.area_id",
                "jd_area_revisions.content_revision_id",
            ],
            name="fk_jd_area_selections_content",
        ),
        sa.UniqueConstraint("job_file_id", "revision_id", "position"),
        sa.CheckConstraint("position >= 0", name=op.f("ck_jd_area_selections_position")),
    )
    op.drop_constraint(op.f("ck_jd_operations_kind"), "jd_operations", type_="check")
    op.create_check_constraint(
        op.f("ck_jd_operations_kind"), "jd_operations", "kind IN ('revise_profile', 'edit_areas')"
    )
    for table in ("jd_area_revisions", "jd_area_selections"):
        op.execute(
            f"CREATE TRIGGER protect_{table} BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION reject_fixed_jd_mutation()"
        )
    # Once a revision has a formal head/result, appending membership would rewrite history.
    # All membership is written BEFORE adopting that new revision in the same transaction.
    op.execute("""
        CREATE FUNCTION protect_jd_area_selection_insert() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF EXISTS (SELECT 1 FROM job_descriptions WHERE job_file_id = NEW.job_file_id
                AND (initial_revision_id = NEW.revision_id
                    OR current_revision_id = NEW.revision_id))
                OR EXISTS (SELECT 1 FROM jd_operations WHERE job_file_id = NEW.job_file_id
                    AND result_revision_id = NEW.revision_id) THEN
                RAISE EXCEPTION 'Cannot append membership to an adopted JD revision'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END
        $$
    """)
    op.execute("""
        CREATE TRIGGER protect_jd_area_selection_insert BEFORE INSERT ON jd_area_selections
        FOR EACH ROW EXECUTE FUNCTION protect_jd_area_selection_insert()
    """)


def downgrade() -> None:
    raise RuntimeError("Fixed JD selections and content must remain recoverable")
