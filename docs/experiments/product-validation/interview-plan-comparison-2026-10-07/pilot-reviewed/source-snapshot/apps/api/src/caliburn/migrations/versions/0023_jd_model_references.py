"""Persist short JD model locators independently of mutable candidate revisions."""

import sqlalchemy as sa
from alembic import op

revision = "0023_jd_model_references"
down_revision = "0022_execution_diagnostics"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "jd_model_references",
        sa.Column("reference_number", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("job_file_id", sa.Uuid(), nullable=False),
        sa.Column("canonical_ref", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("reference_number"),
        sa.ForeignKeyConstraint(["job_file_id"], ["job_files.job_file_id"]),
        sa.UniqueConstraint("job_file_id", "canonical_ref"),
    )


def downgrade() -> None:
    raise RuntimeError("JD model aliases may be present in saved histories; do not discard them")
