"""Move scheduling evidence into constrained columns in the existing command namespace."""

import sqlalchemy as sa
from alembic import op

revision = "0032_memory_typed_evidence"
down_revision = "0031_jd_operation_result_index"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_interview_inputs_execution_source",
        "interview_inputs",
        ["job_file_id", "execution_id", "source_id"],
    )
    op.add_column("memory_operations", sa.Column("intent_source_id", sa.Uuid(), nullable=True))
    op.add_column("memory_operations", sa.Column("failure_reason", sa.Text(), nullable=True))
    op.add_column("memory_operations", sa.Column("failure_frontier", sa.Integer(), nullable=True))
    op.alter_column("memory_operations", "request_payload", nullable=True)
    op.alter_column("memory_operations", "result_payload", nullable=True)
    # Strict one-time conversion. Invalid evidence aborts the migration, never silently
    # grants eligibility or invents a missing failure frontier. Runtime has no JSON fallback.
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (
                SELECT 1 FROM memory_operations
                WHERE (kind = 'consolidation_intent' AND (
                    jsonb_typeof(result_payload->'source_id') IS DISTINCT FROM 'string'
                    OR request_payload->'source_id' IS DISTINCT FROM result_payload->'source_id'
                )) OR (kind = 'batch_failure' AND (
                    jsonb_typeof(result_payload->'reason') IS DISTINCT FROM 'string'
                    OR request_payload->'reason' IS DISTINCT FROM result_payload->'reason'
                    OR jsonb_typeof(result_payload->'formal_frontier') IS DISTINCT FROM 'number'
                    OR (result_payload->>'formal_frontier') !~ '^[0-9]+$'
                ))
            ) THEN
                RAISE EXCEPTION 'Cannot migrate invalid Memory evidence' USING ERRCODE = '23514';
            END IF;
        END $$
    """)
    op.execute("ALTER TABLE memory_operations DISABLE TRIGGER protect_memory_operations")
    op.execute("""
        UPDATE memory_operations SET
            intent_source_id = (result_payload->>'source_id')::uuid,
            request_payload = NULL, result_payload = NULL
        WHERE kind = 'consolidation_intent'
    """)
    op.execute("""
        UPDATE memory_operations SET
            failure_reason = result_payload->>'reason',
            failure_frontier = (result_payload->>'formal_frontier')::integer,
            request_payload = NULL, result_payload = NULL
        WHERE kind = 'batch_failure'
    """)
    op.execute("ALTER TABLE memory_operations ENABLE TRIGGER protect_memory_operations")
    op.create_check_constraint(
        "evidence_shape",
        "memory_operations",
        "(kind = 'consolidation_intent' AND intent_source_id IS NOT NULL "
        "AND failure_reason IS NULL AND failure_frontier IS NULL "
        "AND request_payload IS NULL AND result_payload IS NULL) OR "
        "(kind = 'batch_failure' AND intent_source_id IS NULL "
        "AND failure_reason IS NOT NULL AND length(failure_reason) BETWEEN 1 AND 100 "
        "AND failure_frontier IS NOT NULL AND failure_frontier >= 0 "
        "AND request_payload IS NULL AND result_payload IS NULL) OR "
        "(kind NOT IN ('consolidation_intent', 'batch_failure') "
        "AND intent_source_id IS NULL AND failure_reason IS NULL AND failure_frontier IS NULL "
        "AND request_payload IS NOT NULL AND result_payload IS NOT NULL)",
    )
    op.create_foreign_key(
        "fk_memory_operations_intent_input",
        "memory_operations",
        "interview_inputs",
        ["job_file_id", "execution_id", "intent_source_id"],
        ["job_file_id", "execution_id", "source_id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    raise RuntimeError("Typed evidence has no legacy JSON downgrade; restore an explicit backup")
