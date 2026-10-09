"""Keep minimal command tombstones after deleting all job-file content."""

import sqlalchemy as sa
from alembic import op

revision = "0030_job_file_creation_receipts"
down_revision = "0029_diagnostic_tool_operations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "job_file_creations",
        sa.Column("command_id", sa.Uuid(), nullable=False),
        sa.Column("result_file_id", sa.Uuid(), nullable=True),
        sa.PrimaryKeyConstraint("command_id", name="pk_job_file_creations"),
        sa.UniqueConstraint("result_file_id", name="uq_job_file_creations_result_file_id"),
        sa.ForeignKeyConstraint(
            ["result_file_id"],
            ["job_files.job_file_id"],
            name="fk_job_file_creations_result_file_id_job_files",
            ondelete="SET NULL",
            deferrable=True,
            initially="DEFERRED",
        ),
    )
    op.execute("""
        INSERT INTO job_file_creations(command_id, result_file_id)
        SELECT creation_command_id, job_file_id FROM job_files;
        CREATE OR REPLACE FUNCTION protect_job_file_creation() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF ROW(NEW.job_file_id, NEW.initial_display_name, NEW.employee_name, NEW.created_at)
               IS DISTINCT FROM
               ROW(OLD.job_file_id, OLD.initial_display_name, OLD.employee_name, OLD.created_at)
            THEN
                RAISE EXCEPTION 'Original job-file creation cannot be rewritten'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END $$;
        CREATE FUNCTION protect_job_file_creation_receipt() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'INSERT' THEN
                IF NEW.result_file_id IS NOT NULL THEN RETURN NEW; END IF;
            ELSIF TG_OP = 'UPDATE' THEN
                IF NEW.command_id = OLD.command_id AND OLD.result_file_id IS NOT NULL
                   AND NEW.result_file_id IS NULL
                   AND NOT EXISTS (
                       SELECT 1 FROM job_files WHERE job_file_id = OLD.result_file_id
                   ) THEN RETURN NEW; END IF;
            END IF;
            RAISE EXCEPTION 'Creation receipts may only lose their deleted resource link'
                USING ERRCODE = '23514';
        END $$;
        CREATE TRIGGER protect_job_file_creation_receipts
        BEFORE INSERT OR UPDATE OR DELETE ON job_file_creations
        FOR EACH ROW EXECUTE FUNCTION protect_job_file_creation_receipt();
    """)
    op.drop_column("job_files", "creation_command_id")


def downgrade() -> None:
    raise RuntimeError("Deleted creation commands must remain fenced")
