"""Create target job files and immutable interview originals/formal membership."""

import sqlalchemy as sa
from alembic import op

revision = "0001_job_files"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "job_files",
        sa.Column("job_file_id", sa.Uuid(), nullable=False),
        sa.Column("creation_command_id", sa.Uuid(), nullable=False),
        sa.Column("initial_display_name", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("employee_name", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("job_file_id", name="pk_job_files"),
        sa.UniqueConstraint("creation_command_id", name="uq_job_files_creation_command_id"),
        sa.CheckConstraint(
            "length(btrim(display_name)) > 0 AND length(display_name) <= 200",
            name=op.f("ck_job_files_display_name_length"),
        ),
        sa.CheckConstraint(
            "length(btrim(employee_name)) > 0 AND length(employee_name) <= 200",
            name=op.f("ck_job_files_employee_name_length"),
        ),
    )
    op.create_table(
        "interview_texts",
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("job_file_id", sa.Uuid(), nullable=False),
        sa.Column("speaker", sa.Text(), nullable=False),
        sa.Column("interview_text", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("source_id", name="pk_interview_texts"),
        sa.UniqueConstraint("job_file_id", "source_id", name="uq_interview_texts_job_file_id"),
        sa.ForeignKeyConstraint(
            ["job_file_id"],
            ["job_files.job_file_id"],
            name="fk_interview_texts_job_file_id_job_files",
        ),
        sa.CheckConstraint(
            "speaker IN ('app', 'employee', 'consultant')", name=op.f("ck_interview_texts_speaker")
        ),
        sa.CheckConstraint(
            "length(interview_text) > 0", name=op.f("ck_interview_texts_nonempty_text")
        ),
    )
    op.create_table(
        "formal_interviews",
        sa.Column("job_file_id", sa.Uuid(), nullable=False),
        sa.Column("interview_sequence", sa.Integer(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("job_file_id", "interview_sequence", name="pk_formal_interviews"),
        sa.UniqueConstraint("source_id", name="uq_formal_interviews_source_id"),
        sa.ForeignKeyConstraint(
            ["job_file_id", "source_id"],
            ["interview_texts.job_file_id", "interview_texts.source_id"],
            name="fk_formal_interviews_job_file_id_interview_texts",
        ),
        sa.CheckConstraint(
            "interview_sequence > 0", name=op.f("ck_formal_interviews_positive_sequence")
        ),
    )
    op.execute("""
        CREATE FUNCTION reject_interview_mutation() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'Interview originals and formal identities are immutable'
                USING ERRCODE = '23514';
        END
        $$
    """)
    for table in ("interview_texts", "formal_interviews"):
        op.execute(
            f"CREATE TRIGGER protect_{table} BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION reject_interview_mutation()"
        )
    op.execute("""
        CREATE FUNCTION protect_job_file_creation() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF ROW(NEW.job_file_id, NEW.creation_command_id, NEW.initial_display_name,
                   NEW.employee_name, NEW.created_at)
               IS DISTINCT FROM
               ROW(OLD.job_file_id, OLD.creation_command_id, OLD.initial_display_name,
                   OLD.employee_name, OLD.created_at) THEN
                RAISE EXCEPTION 'Original job-file creation cannot be rewritten'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END
        $$
    """)
    op.execute("""
        CREATE TRIGGER protect_job_file_creation BEFORE UPDATE ON job_files
        FOR EACH ROW EXECUTE FUNCTION protect_job_file_creation()
    """)


def downgrade() -> None:
    raise RuntimeError(
        "Initial target schema contains durable originals; destructive downgrade refused"
    )
