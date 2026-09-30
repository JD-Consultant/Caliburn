"""Persist input acceptance and independent consultant/Memory admission."""

import sqlalchemy as sa
from alembic import op

revision = "0002_input_admission"
down_revision = "0001_job_files"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "executions",
        sa.Column("execution_id", sa.Uuid(), nullable=False),
        sa.Column("job_file_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("writer_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("execution_id", name="pk_executions"),
        sa.ForeignKeyConstraint(
            ["job_file_id"], ["job_files.job_file_id"], name="fk_executions_job_file_id_job_files"
        ),
        sa.UniqueConstraint("job_file_id", "execution_id", name="uq_executions_job_file_id"),
        sa.CheckConstraint(
            "kind IN ('consultant_turn', 'memory_batch')", name=op.f("ck_executions_kind")
        ),
        sa.CheckConstraint(
            "status IN ('active', 'paused', 'completed', 'cancelled', 'failed')",
            name=op.f("ck_executions_status"),
        ),
        sa.CheckConstraint(
            "kind = 'consultant_turn' OR status NOT IN ('paused', 'cancelled')",
            name=op.f("ck_executions_memory_control"),
        ),
    )
    op.create_index(
        "uq_executions_active_kind",
        "executions",
        ["job_file_id", "kind"],
        unique=True,
        postgresql_where=sa.text("status IN ('active', 'paused')"),
    )
    op.create_table(
        "interview_inputs",
        sa.Column("job_file_id", sa.Uuid(), nullable=False),
        sa.Column("command_id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("execution_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("job_file_id", "command_id", name="pk_interview_inputs"),
        sa.UniqueConstraint("source_id", name="uq_interview_inputs_source_id"),
        sa.UniqueConstraint("execution_id", name="uq_interview_inputs_execution_id"),
        sa.ForeignKeyConstraint(
            ["job_file_id", "source_id"],
            ["interview_texts.job_file_id", "interview_texts.source_id"],
            name="fk_interview_inputs_job_file_id_interview_texts",
        ),
        sa.ForeignKeyConstraint(
            ["job_file_id", "execution_id"],
            ["executions.job_file_id", "executions.execution_id"],
            name="fk_interview_inputs_job_file_id_executions",
        ),
    )
    op.execute("""
        CREATE TRIGGER protect_interview_inputs BEFORE UPDATE OR DELETE ON interview_inputs
        FOR EACH ROW EXECUTE FUNCTION reject_interview_mutation()
    """)
    op.execute("""
        CREATE FUNCTION protect_execution_identity() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF ROW(NEW.execution_id, NEW.job_file_id, NEW.kind, NEW.created_at)
               IS DISTINCT FROM
               ROW(OLD.execution_id, OLD.job_file_id, OLD.kind, OLD.created_at) THEN
                RAISE EXCEPTION 'Execution identity cannot be rewritten' USING ERRCODE = '23514';
            END IF;
            IF OLD.status IN ('completed', 'cancelled', 'failed')
               AND ROW(NEW.status, NEW.writer_id)
                   IS DISTINCT FROM ROW(OLD.status, OLD.writer_id) THEN
                RAISE EXCEPTION 'Terminal eligibility cannot be revived' USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END
        $$
    """)
    op.execute("""
        CREATE TRIGGER protect_execution_identity BEFORE UPDATE ON executions
        FOR EACH ROW EXECUTE FUNCTION protect_execution_identity()
    """)


def downgrade() -> None:
    raise RuntimeError("Input acceptance contains durable originals; destructive downgrade refused")
