"""Add opt-in checkpoint inspection copies and invoker-rights DataGrip views."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0022_execution_diagnostics"
down_revision = "0021_rate_limited_failures"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "diagnostic_execution_snapshots",
        sa.Column("execution_id", sa.Uuid(), nullable=False),
        sa.Column("job_file_id", sa.Uuid(), nullable=False),
        sa.Column("snapshot_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("execution_status", sa.Text(), nullable=False),
        sa.Column("employee_input", sa.Text(), nullable=True),
        sa.Column("final_reply", sa.Text(), nullable=True),
        sa.Column("steps", JSONB(), nullable=False),
        sa.PrimaryKeyConstraint("execution_id", name="pk_diagnostic_execution_snapshots"),
        sa.ForeignKeyConstraint(
            ["job_file_id", "execution_id"],
            ["executions.job_file_id", "executions.execution_id"],
            name="fk_diagnostic_execution_snapshots_job_file_id_executions",
        ),
        sa.CheckConstraint("jsonb_typeof(steps) = 'array'", name="steps_array"),
    )
    # Independently aggregate child relations. A direct multi-way join multiplies counts.
    op.execute("""
        CREATE VIEW diagnostic_execution_history WITH (security_invoker = true) AS
        SELECT j.display_name, e.job_file_id, e.execution_id, e.kind, e.status,
               e.created_at, e.pause_requested,
               d.employee_input, d.final_reply,
               fi.interview_sequence AS input_sequence,
               fr.interview_sequence AS reply_sequence,
               d.snapshot_at, d.execution_status AS status_at_snapshot,
               jsonb_array_length(d.steps) AS saved_response_count,
               a.model_attempt_count, a.failed_attempt_count, a.compaction_attempt_count,
               a.failures,
               c.status AS jd_candidate_status, c.base_revision_id AS jd_base_revision_id,
               c.current_revision_id AS jd_candidate_revision_id,
               jo.jd_operation_count, ms.published_snapshot_ids
        FROM executions e JOIN job_files j USING (job_file_id)
        LEFT JOIN diagnostic_execution_snapshots d USING (job_file_id, execution_id)
        LEFT JOIN interview_inputs ii USING (job_file_id, execution_id)
        LEFT JOIN formal_interviews fi ON fi.source_id=ii.source_id AND fi.job_file_id=e.job_file_id
        LEFT JOIN interview_replies rr
            ON rr.job_file_id=e.job_file_id AND rr.execution_id=e.execution_id
        LEFT JOIN formal_interviews fr ON fr.source_id=rr.source_id AND fr.job_file_id=e.job_file_id
        LEFT JOIN jd_candidates c ON c.job_file_id=e.job_file_id AND c.execution_id=e.execution_id
        LEFT JOIN LATERAL (
            SELECT count(*) FILTER (WHERE kind='model') AS model_attempt_count,
                   count(*) FILTER (WHERE failure_code IS NOT NULL) AS failed_attempt_count,
                   count(*) FILTER (WHERE kind='compaction') AS compaction_attempt_count,
                   jsonb_agg(jsonb_build_object('kind',kind,'failure_code',failure_code,
                       'request_id',request_id,'attempt_id',attempt_id,'admitted_at',admitted_at)
                       ORDER BY admitted_at,attempt_id)
                       FILTER (WHERE failure_code IS NOT NULL) AS failures
            FROM execution_outbound_attempts WHERE execution_id=e.execution_id
        ) a ON true
        LEFT JOIN LATERAL (
            SELECT count(*) AS jd_operation_count FROM jd_operations
            WHERE candidate_execution_id=e.execution_id AND job_file_id=e.job_file_id
        ) jo ON true
        LEFT JOIN LATERAL (
            SELECT jsonb_agg(snapshot_id ORDER BY created_at,snapshot_id) AS published_snapshot_ids
            FROM memory_snapshots WHERE execution_id=e.execution_id AND job_file_id=e.job_file_id
        ) ms ON true
    """)
    op.execute("""
        CREATE VIEW diagnostic_model_steps WITH (security_invoker = true) AS
        SELECT j.display_name, d.job_file_id, d.execution_id, e.kind, e.status,
               s.ordinality AS response_order, s.item->>'role' AS role,
               s.item->>'thread_id' AS thread_id, s.item->>'checkpoint_id' AS checkpoint_id,
               s.item->>'checkpoint_time' AS checkpoint_time, s.item->>'source' AS source,
               s.item->'response'->>'id' AS response_id,
               s.item->'request'->>'model' AS model,
               s.item->'request' AS request, s.item->'response' AS response,
               s.item->'tool_results' AS tool_results, d.snapshot_at
        FROM diagnostic_execution_snapshots d
        JOIN executions e USING (job_file_id,execution_id)
        JOIN job_files j USING (job_file_id)
        CROSS JOIN LATERAL jsonb_array_elements(d.steps) WITH ORDINALITY s(item,ordinality)
    """)
    op.execute("""
        CREATE VIEW diagnostic_tool_calls WITH (security_invoker = true) AS
        SELECT s.display_name,s.job_file_id,s.execution_id,s.role,s.thread_id,
               s.response_order,s.response_id,t.ordinality AS output_index,
               t.item->>'call_id' AS call_id,t.item->>'name' AS tool_name,
               t.item->>'arguments' AS tool_arguments,
               CASE WHEN s.tool_results ? (t.item->>'call_id') THEN 'recorded'
                    ELSE 'not_recorded' END AS result_state,
               s.tool_results->>(t.item->>'call_id') AS tool_output,s.snapshot_at
        FROM diagnostic_model_steps s
        CROSS JOIN LATERAL jsonb_array_elements(s.response->'output')
            WITH ORDINALITY t(item,ordinality)
        WHERE t.item->>'type'='function_call'
    """)


def downgrade() -> None:
    # Only disposable diagnostic data, never original checkpoints or business results.
    op.execute("DROP VIEW diagnostic_tool_calls")
    op.execute("DROP VIEW diagnostic_model_steps")
    op.execute("DROP VIEW diagnostic_execution_history")
    op.drop_table("diagnostic_execution_snapshots")
