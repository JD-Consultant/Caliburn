"""Expose trusted native tool operation identities in disposable diagnostic views."""

from alembic import op

revision = "0029_diagnostic_tool_operations"
down_revision = "0028_jd_compound_results"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE OR REPLACE VIEW diagnostic_model_steps WITH (security_invoker = true) AS
        SELECT j.display_name, d.job_file_id, d.execution_id, e.kind, e.status,
               s.ordinality AS response_order, s.item->>'role' AS role,
               s.item->>'thread_id' AS thread_id, s.item->>'checkpoint_id' AS checkpoint_id,
               s.item->>'checkpoint_time' AS checkpoint_time, s.item->>'source' AS source,
               s.item->'response'->>'id' AS response_id,
               s.item->'request'->>'model' AS model,
               s.item->'request' AS request, s.item->'response' AS response,
               s.item->'tool_results' AS tool_results, d.snapshot_at,
               s.item->>'request_id' AS request_id,
               COALESCE(s.item->>'response_state', 'recorded') AS response_state,
               s.item->>'response_checkpoint_id' AS response_checkpoint_id,
               s.item->>'response_checkpoint_time' AS response_checkpoint_time,
               COALESCE(s.item->>'response_source', s.item->>'source') AS response_source,
               s.item->'metadata' AS metadata
        FROM diagnostic_execution_snapshots d
        JOIN executions e USING (job_file_id,execution_id)
        JOIN job_files j USING (job_file_id)
        CROSS JOIN LATERAL jsonb_array_elements(d.steps) WITH ORDINALITY s(item,ordinality)
    """)
    op.execute("""
        CREATE OR REPLACE VIEW diagnostic_tool_calls WITH (security_invoker = true) AS
        SELECT s.display_name,s.job_file_id,s.execution_id,s.role,s.thread_id,
               s.response_order,s.response_id,t.ordinality AS output_index,
               t.item->>'call_id' AS call_id,t.item->>'name' AS tool_name,
               t.item->>'arguments' AS tool_arguments,
               CASE WHEN s.tool_results ? (t.item->>'call_id') THEN 'recorded'
                    ELSE 'not_recorded' END AS result_state,
               s.tool_results->>(t.item->>'call_id') AS tool_output,s.snapshot_at,
               (s.metadata->'tool_operation_ids'->>(t.item->>'call_id'))::uuid AS operation_id
        FROM diagnostic_model_steps s
        CROSS JOIN LATERAL jsonb_array_elements(s.response->'output')
            WITH ORDINALITY t(item,ordinality)
        WHERE t.item->>'type'='function_call'
    """)


def downgrade() -> None:
    raise RuntimeError("Rebuild disposable diagnostic projections with a forward migration")
