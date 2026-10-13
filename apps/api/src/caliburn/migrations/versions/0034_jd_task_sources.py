"""識別任務共用來源 layout；舊格式只能改用空 namespace，不搬移資料。"""

import sqlalchemy as sa
from alembic import op

revision = "0034_jd_task_sources"
down_revision = "0033_memory_context_storage"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    error = (
        "This storage release requires a fresh database namespace; existing data is not migrated"
    )
    table = "jd_source_references"
    if table not in inspector.get_table_names():
        raise RuntimeError(error)
    columns = {column["name"] for column in inspector.get_columns(table)}
    if (
        "target_task_id" in columns
        or not {"target_kind", "target_field", "target_item_id", "reviewed_revision_id"} <= columns
    ):
        raise RuntimeError(error)
    constraints = {
        constraint["name"]: constraint["sqltext"]
        for constraint in inspector.get_check_constraints(table)
    }
    target_shape = constraints.get("ck_jd_source_references_target_shape", "")
    if not target_shape or any(
        f"'{kind}'" in target_shape for kind in ("detail", "task_capability")
    ):
        raise RuntimeError(error)
    identity = next(
        (
            constraint["column_names"]
            for constraint in inspector.get_unique_constraints(table)
            if constraint["name"] == "uq_jd_source_references_identity"
        ),
        (),
    )
    if set(identity) != {
        "job_file_id",
        "revision_id",
        "target_kind",
        "target_field",
        "target_item_id",
        "source_kind",
        "interview_source_id",
        "memory_layer",
        "memory_object_id",
    }:
        raise RuntimeError(error)


def downgrade() -> None:
    raise NotImplementedError("Storage releases do not support downgrade")
