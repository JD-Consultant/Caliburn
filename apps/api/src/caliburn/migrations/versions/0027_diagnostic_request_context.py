"""讓診斷保留未取得回應的請求及當時捕捉的 Context 綁定。"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0027_diagnostic_request_context"
down_revision = "0026_interview_plans"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "diagnostic_execution_snapshots",
        sa.Column("captured_initial_context", JSONB(), nullable=True),
    )
    op.execute("""
        CREATE OR REPLACE VIEW diagnostic_execution_history WITH (security_invoker = true) AS
        SELECT j.display_name, e.job_file_id, e.execution_id, e.kind, e.status,
               e.created_at, e.pause_requested,
               d.employee_input, d.final_reply,
               fi.interview_sequence AS input_sequence,
               fr.interview_sequence AS reply_sequence,
               d.snapshot_at, d.execution_status AS status_at_snapshot,
               CASE WHEN d.snapshot_at IS NULL THEN NULL ELSE
                   (SELECT count(*)::integer FROM jsonb_array_elements(d.steps) s(item)
                    WHERE jsonb_typeof(s.item->'response') = 'object')
               END AS saved_response_count,
               a.model_attempt_count, a.failed_attempt_count, a.compaction_attempt_count,
               a.failures,
               c.status AS jd_candidate_status, c.base_revision_id AS jd_base_revision_id,
               c.current_revision_id AS jd_candidate_revision_id,
               jo.jd_operation_count, ms.published_snapshot_ids, d.captured_initial_context,
               CASE WHEN d.snapshot_at IS NULL THEN NULL ELSE
                   (SELECT count(*)::integer FROM jsonb_array_elements(d.steps) s(item)
                    WHERE s.item->>'response_state' = 'request_only')
               END AS request_only_count,
               mh.snapshot_id AS current_published_snapshot_id
        FROM executions e JOIN job_files j USING (job_file_id)
        LEFT JOIN diagnostic_execution_snapshots d USING (job_file_id, execution_id)
        LEFT JOIN interview_inputs ii USING (job_file_id, execution_id)
        LEFT JOIN memory_heads mh ON mh.job_file_id=e.job_file_id
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
               COALESCE(s.item->>'response_source', s.item->>'source') AS response_source
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
               s.tool_results->>(t.item->>'call_id') AS tool_output,s.snapshot_at
        FROM diagnostic_model_steps s
        CROSS JOIN LATERAL jsonb_array_elements(s.response->'output')
            WITH ORDINALITY t(item,ordinality)
        WHERE t.item->>'type'='function_call'
    """)


def downgrade() -> None:
    raise RuntimeError("Rebuild disposable diagnostic projections with a forward migration")
