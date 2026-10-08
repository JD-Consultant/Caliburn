"""Keep rename freshness and original results in the job-file owner."""

import sqlalchemy as sa
from alembic import op

revision = "0004_job_file_renames"
down_revision = "0003_formal_replies"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "job_files", sa.Column("name_revision", sa.BigInteger(), nullable=False, server_default="1")
    )
    op.create_check_constraint(
        op.f("ck_job_files_name_revision_range"),
        "job_files",
        "name_revision BETWEEN 1 AND 9007199254740991",
    )
    op.execute("""
        CREATE FUNCTION advance_job_file_name_revision() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            NEW.name_revision := OLD.name_revision +
                CASE WHEN NEW.display_name IS DISTINCT FROM OLD.display_name THEN 1 ELSE 0 END;
            RETURN NEW;
        END
        $$
    """)
    op.execute("""
        CREATE TRIGGER advance_job_file_name_revision BEFORE UPDATE ON job_files
        FOR EACH ROW EXECUTE FUNCTION advance_job_file_name_revision()
    """)
    op.create_table(
        "job_file_renames",
        sa.Column("job_file_id", sa.Uuid(), nullable=False),
        sa.Column("command_id", sa.Uuid(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("expected_name_revision", sa.BigInteger(), nullable=False),
        sa.Column("name_revision", sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint("job_file_id", "command_id", name="pk_job_file_renames"),
        sa.ForeignKeyConstraint(
            ["job_file_id"],
            ["job_files.job_file_id"],
            name="fk_job_file_renames_job_file_id_job_files",
        ),
        sa.CheckConstraint(
            "length(btrim(display_name)) > 0 AND length(display_name) <= 200",
            name=op.f("ck_job_file_renames_display_name_length"),
        ),
        sa.CheckConstraint(
            "expected_name_revision BETWEEN 1 AND 9007199254740991 "
            "AND name_revision BETWEEN expected_name_revision AND expected_name_revision + 1",
            name=op.f("ck_job_file_renames_name_revision_range"),
        ),
    )
    op.execute("""
        CREATE FUNCTION reject_job_file_rename_mutation() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'Original rename results are immutable' USING ERRCODE = '23514';
        END
        $$
    """)
    op.execute("""
        CREATE TRIGGER protect_job_file_renames BEFORE UPDATE OR DELETE ON job_file_renames
        FOR EACH ROW EXECUTE FUNCTION reject_job_file_rename_mutation()
    """)


def downgrade() -> None:
    raise RuntimeError(
        "Original rename results must remain recoverable; destructive downgrade refused"
    )
