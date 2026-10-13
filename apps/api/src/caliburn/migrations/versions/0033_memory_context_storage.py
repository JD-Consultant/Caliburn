"""Identify the fresh storage layout without migrating earlier application data."""

import sqlalchemy as sa
from alembic import op

revision = "0033_memory_context_storage"
down_revision = "0032_memory_typed_evidence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    required = {
        "interview_plan_bodies",
        "interview_plan_operations",
        "occupation_reference_candidates",
        "occupation_reference_operations",
        "jd_candidates",
        "jd_operations",
        "memory_batches",
    }
    error = (
        "This storage release requires a fresh database namespace; existing data is not migrated"
    )
    if not required <= tables or "diagnostic_execution_snapshots" in tables:
        raise RuntimeError(error)
    columns = {
        table: {column["name"] for column in inspector.get_columns(table)} for table in required
    }
    if (
        not {"job_file_id", "body_id", "body"} <= columns["interview_plan_bodies"]
        or "body_id" not in columns["interview_plan_operations"]
        or "body" in columns["interview_plan_operations"]
    ):
        raise RuntimeError(error)
    retired = {
        "occupation_reference_candidates": {"generation_id", "base_revision_id"},
        "occupation_reference_operations": {
            "generation_id",
            "result_generation_id",
            "parent_revision_id",
        },
        "jd_candidates": {"generation_id"},
        "jd_operations": {"candidate_generation_id"},
        "memory_batches": {"generation_id"},
    }
    if any(columns[table] & names for table, names in retired.items()):
        raise RuntimeError(error)
    if {"diagnostic_execution_history", "diagnostic_model_steps", "diagnostic_tool_calls"} & set(
        inspector.get_view_names()
    ):
        raise RuntimeError(error)


def downgrade() -> None:
    raise NotImplementedError("Storage releases do not support downgrade")
