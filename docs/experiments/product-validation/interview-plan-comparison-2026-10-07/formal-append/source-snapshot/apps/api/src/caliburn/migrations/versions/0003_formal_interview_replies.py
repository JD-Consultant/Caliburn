"""Bind one immutable formal reply to its accepted input, without copying original text."""

import sqlalchemy as sa
from alembic import op

revision = "0003_formal_replies"
down_revision = "0002_input_admission"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_interview_inputs_job_file_id_execution_id",
        "interview_inputs",
        ["job_file_id", "execution_id"],
    )
    op.create_table(
        "interview_replies",
        sa.Column("job_file_id", sa.Uuid(), nullable=False),
        sa.Column("execution_id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("job_file_id", "execution_id", name="pk_interview_replies"),
        sa.UniqueConstraint("source_id", name="uq_interview_replies_source_id"),
        sa.ForeignKeyConstraint(
            ["job_file_id", "execution_id"],
            ["interview_inputs.job_file_id", "interview_inputs.execution_id"],
            name="fk_interview_replies_job_file_id_interview_inputs",
        ),
        sa.ForeignKeyConstraint(
            ["job_file_id", "source_id"],
            ["interview_texts.job_file_id", "interview_texts.source_id"],
            name="fk_interview_replies_job_file_id_interview_texts",
        ),
    )
    op.execute("""
        CREATE TRIGGER protect_interview_replies BEFORE UPDATE OR DELETE ON interview_replies
        FOR EACH ROW EXECUTE FUNCTION reject_interview_mutation()
    """)


def downgrade() -> None:
    raise RuntimeError("Formal replies must remain traceable; destructive downgrade refused")
