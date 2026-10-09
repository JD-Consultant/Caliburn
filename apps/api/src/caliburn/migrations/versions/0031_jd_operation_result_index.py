"""Index sealed-revision checks by file and result, independently of command history."""

from alembic import op

revision = "0031_jd_operation_result_index"
down_revision = "0030_job_file_creation_receipts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_jd_operations_result_revision", "jd_operations", ["job_file_id", "result_revision_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_jd_operations_result_revision", table_name="jd_operations")
