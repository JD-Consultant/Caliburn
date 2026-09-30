"""Add fixed JD profile revisions and original edit results in the target namespace."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0005_jd_profile_revisions"
down_revision = "0004_job_file_renames"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "jd_revisions",
        sa.Column("job_file_id", sa.Uuid(), nullable=False),
        sa.Column("revision_id", sa.Uuid(), nullable=False),
        sa.Column("parent_revision_id", sa.Uuid()),
        sa.Column("job_title", sa.Text()),
        sa.Column("organization_unit", sa.Text()),
        sa.Column("reports_to", sa.Text()),
        sa.Column("purpose", sa.Text()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("job_file_id", "revision_id", name="pk_jd_revisions"),
        sa.ForeignKeyConstraint(
            ["job_file_id"], ["job_files.job_file_id"], name="fk_jd_revisions_job_file_id_job_files"
        ),
        sa.ForeignKeyConstraint(
            ["job_file_id", "parent_revision_id"],
            ["jd_revisions.job_file_id", "jd_revisions.revision_id"],
            name="fk_jd_revisions_parent",
        ),
        sa.CheckConstraint(
            "parent_revision_id IS NULL OR parent_revision_id <> revision_id",
            name=op.f("ck_jd_revisions_not_self_parent"),
        ),
    )
    op.create_table(
        "job_descriptions",
        sa.Column("job_file_id", sa.Uuid(), nullable=False),
        sa.Column("initial_revision_id", sa.Uuid(), nullable=False),
        sa.Column("current_revision_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("job_file_id", name="pk_job_descriptions"),
        sa.ForeignKeyConstraint(
            ["job_file_id"],
            ["job_files.job_file_id"],
            name="fk_job_descriptions_job_file_id_job_files",
        ),
        sa.ForeignKeyConstraint(
            ["job_file_id", "initial_revision_id"],
            ["jd_revisions.job_file_id", "jd_revisions.revision_id"],
            name="fk_job_descriptions_initial_revision",
        ),
        sa.ForeignKeyConstraint(
            ["job_file_id", "current_revision_id"],
            ["jd_revisions.job_file_id", "jd_revisions.revision_id"],
            name="fk_job_descriptions_current_revision",
        ),
    )
    op.create_table(
        "jd_operations",
        sa.Column("job_file_id", sa.Uuid(), nullable=False),
        sa.Column("command_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("expected_revision_id", sa.Uuid(), nullable=False),
        sa.Column("result_revision_id", sa.Uuid(), nullable=False),
        sa.Column("request_payload", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("job_file_id", "command_id", name="pk_jd_operations"),
        sa.ForeignKeyConstraint(
            ["job_file_id"],
            ["job_files.job_file_id"],
            name="fk_jd_operations_job_file_id_job_files",
        ),
        sa.ForeignKeyConstraint(
            ["job_file_id", "expected_revision_id"],
            ["jd_revisions.job_file_id", "jd_revisions.revision_id"],
            name="fk_jd_operations_expected_revision",
        ),
        sa.ForeignKeyConstraint(
            ["job_file_id", "result_revision_id"],
            ["jd_revisions.job_file_id", "jd_revisions.revision_id"],
            name="fk_jd_operations_result_revision",
        ),
        sa.CheckConstraint("kind IN ('revise_profile')", name=op.f("ck_jd_operations_kind")),
    )
    # This upgrades only prior NEW-target files, whose JD did not exist yet; no legacy read.
    op.execute("""
        INSERT INTO jd_revisions (job_file_id, revision_id)
        SELECT job_file_id, gen_random_uuid() FROM job_files
    """)
    op.execute("""
        INSERT INTO job_descriptions (job_file_id, initial_revision_id, current_revision_id)
        SELECT job_file_id, revision_id, revision_id FROM jd_revisions
    """)
    op.execute("""
        CREATE FUNCTION reject_fixed_jd_mutation() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'Fixed JD revisions and original results are immutable'
                USING ERRCODE = '23514';
        END
        $$
    """)
    for table in ("jd_revisions", "jd_operations"):
        op.execute(
            f"CREATE TRIGGER protect_{table} BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION reject_fixed_jd_mutation()"
        )
    op.execute("""
        CREATE FUNCTION protect_jd_identity() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.job_file_id IS DISTINCT FROM OLD.job_file_id
                OR NEW.initial_revision_id IS DISTINCT FROM OLD.initial_revision_id THEN
                RAISE EXCEPTION 'JD identity and initial baseline are immutable'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END
        $$
    """)
    op.execute("""
        CREATE TRIGGER protect_jd_identity BEFORE UPDATE ON job_descriptions
        FOR EACH ROW EXECUTE FUNCTION protect_jd_identity()
    """)


def downgrade() -> None:
    raise RuntimeError("Fixed JD revisions and original results must remain recoverable")
