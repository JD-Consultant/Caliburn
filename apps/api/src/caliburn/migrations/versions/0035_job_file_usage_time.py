"""Track cumulative active-interview time per job file, heartbeat-accumulated."""

import sqlalchemy as sa
from alembic import op

revision = "0035_job_file_usage_time"
down_revision = "0034_jd_task_sources"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "job_files",
        sa.Column("active_usage_seconds", sa.BigInteger(), nullable=False, server_default="0"),
    )
    op.create_check_constraint(
        op.f("ck_job_files_active_usage_seconds_range"),
        "job_files",
        "active_usage_seconds BETWEEN 0 AND 9007199254740991",
    )


def downgrade() -> None:
    raise RuntimeError(
        "Accumulated usage time must remain recoverable; destructive downgrade refused"
    )
