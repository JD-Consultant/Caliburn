"""interview vNext durable persistence — eight new tables (ADR 0034; V2-B reference §5/§11).

手工撰寫、人工審查;autogenerate 只作 diff 輔助(CHECK/trigger 它偵測不到,
introspection test 才是 gate)。**不碰任何 v3 表**(interview_* / document_* / users
/ job_profiles 原樣)。create order(§11.1):sessions → runs → artifacts →
circular FKs(session initial-state、run manifest)→ commands → events → outbox
→ checkpoints → attempts → triggers。

裁決(§5.2,2026-07-17):runs 的 lifecycle CHECK 對 terminal **只要求**
completed_at 非空、event_count >= 1、completion 不早於 start;
`terminal → manifest_artifact_id IS NOT NULL` 刻意不進 DB CHECK(§12.1 cleanup
需先 NULL circular FK pointer)。manifest 完整性由 WorkflowRun DTO validator、
finalize 單一 transaction、hydrate corruption 檢查與 integration tests 四層保證。

commands 的 occurred_at(domain clock)/committed_at(DB clock)屬不同時鐘,
刻意不建跨時鐘大小 CHECK——時鐘偏差不該讓合法寫入失敗。

Revision ID: 0010
Revises: 0009
"""
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels = None
depends_on = None

_SHA256 = r"^sha256:[0-9a-f]{64}$"
_STABLE_NAME = r"^[a-z][a-z0-9]*([._-][a-z0-9]+)*$"


def upgrade() -> None:
    # ── 1. sessions(circular FK 欄位先建、constraint 後補)──────────────────
    op.create_table(
        "interview_vnext_sessions",
        sa.Column("session_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("profile_id", UUID(as_uuid=True), nullable=False),
        sa.Column("architecture_id", sa.Text(), nullable=False),
        sa.Column("workflow_version", sa.Text(), nullable=False),
        sa.Column("reference_snapshot_id", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("state_version", sa.BigInteger(), nullable=False),
        sa.Column("state_schema_version", sa.Text(), nullable=False),
        sa.Column("state_json", sa.Text(), nullable=False),
        sa.Column("state_hash", sa.Text(), nullable=False),
        sa.Column("initial_state_artifact_id", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "session_id",
                            name="uq_ivn_sessions_tenant_session"),
        sa.ForeignKeyConstraint(["profile_id"], ["job_profiles.id"],
                                name="fk_ivn_sessions_profile", ondelete="RESTRICT"),
        sa.CheckConstraint(
            "status IN ('planned','active','paused','finishing','completed','failed')",
            name="ck_ivn_sessions_status"),
        sa.CheckConstraint("state_version >= 0", name="ck_ivn_sessions_state_version"),
        sa.CheckConstraint(f"state_hash ~ '{_SHA256}'", name="ck_ivn_sessions_state_hash"),
        sa.CheckConstraint("jsonb_typeof(state_json::jsonb) = 'object'",
                           name="ck_ivn_sessions_state_json_object"),
        sa.CheckConstraint("updated_at >= created_at", name="ck_ivn_sessions_time_order"),
    )
    op.create_index("ix_ivn_sessions_tenant_profile", "interview_vnext_sessions",
                    ["tenant_id", "profile_id", sa.text("updated_at DESC")])

    # ── 2. runs ───────────────────────────────────────────────────────────────
    op.create_table(
        "interview_vnext_runs",
        sa.Column("run_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", UUID(as_uuid=True), nullable=False),
        sa.Column("architecture_id", sa.Text(), nullable=False),
        sa.Column("workflow_version", sa.Text(), nullable=False),
        sa.Column("taxonomy_id", sa.Text(), nullable=False),
        sa.Column("taxonomy_version", sa.Text(), nullable=False),
        sa.Column("taxonomy_hash", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("event_count", sa.BigInteger(), nullable=False),
        sa.Column("first_event_hash", sa.Text(), nullable=True),
        sa.Column("last_event_hash", sa.Text(), nullable=True),
        sa.Column("manifest_artifact_id", UUID(as_uuid=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("tenant_id", "run_id", name="uq_ivn_runs_tenant_run"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "session_id"],
            ["interview_vnext_sessions.tenant_id", "interview_vnext_sessions.session_id"],
            name="fk_ivn_runs_session", ondelete="RESTRICT"),
        sa.CheckConstraint("status IN ('open','completed','failed')",
                           name="ck_ivn_runs_status"),
        sa.CheckConstraint("event_count >= 0", name="ck_ivn_runs_event_count"),
        sa.CheckConstraint(
            "(event_count = 0 AND first_event_hash IS NULL AND last_event_hash IS NULL)"
            " OR (event_count > 0 AND first_event_hash IS NOT NULL"
            " AND last_event_hash IS NOT NULL)",
            name="ck_ivn_runs_event_hash_coherence"),
        sa.CheckConstraint(
            "(status = 'open' AND completed_at IS NULL AND manifest_artifact_id IS NULL)"
            " OR (status IN ('completed','failed') AND completed_at IS NOT NULL"
            " AND event_count >= 1 AND completed_at >= started_at)",
            name="ck_ivn_runs_lifecycle"),
        sa.CheckConstraint(f"first_event_hash IS NULL OR first_event_hash ~ '{_SHA256}'",
                           name="ck_ivn_runs_first_hash"),
        sa.CheckConstraint(f"last_event_hash IS NULL OR last_event_hash ~ '{_SHA256}'",
                           name="ck_ivn_runs_last_hash"),
        sa.CheckConstraint(f"taxonomy_hash ~ '{_SHA256}'", name="ck_ivn_runs_taxonomy_hash"),
    )
    op.create_index("ix_ivn_runs_tenant_session_started", "interview_vnext_runs",
                    ["tenant_id", "session_id", "started_at", "run_id"])

    # ── 3. artifacts ─────────────────────────────────────────────────────────
    op.create_table(
        "interview_vnext_artifacts",
        sa.Column("artifact_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("record_schema_version", sa.Text(), nullable=False),
        sa.Column("run_id", UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", UUID(as_uuid=True), nullable=True),
        sa.Column("turn_id", UUID(as_uuid=True), nullable=True),
        sa.Column("operation_id", UUID(as_uuid=True), nullable=True),
        sa.Column("attempt_id", UUID(as_uuid=True), nullable=True),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("media_type", sa.Text(), nullable=False),
        sa.Column("schema_id", sa.Text(), nullable=True),
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column("byte_size", sa.BigInteger(), nullable=False),
        sa.Column("storage", sa.Text(), nullable=False),
        sa.Column("inline_content", sa.Text(), nullable=True),
        sa.Column("external_uri", sa.Text(), nullable=True),
        sa.Column("retention_class", sa.Text(), nullable=False),
        sa.Column("redaction_status", sa.Text(), nullable=False),
        sa.Column("contains_test_data", sa.Boolean(), nullable=False,
                  server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "artifact_id",
                            name="uq_ivn_artifacts_tenant_artifact"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "run_id"],
            ["interview_vnext_runs.tenant_id", "interview_vnext_runs.run_id"],
            name="fk_ivn_artifacts_run", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "session_id"],
            ["interview_vnext_sessions.tenant_id", "interview_vnext_sessions.session_id"],
            name="fk_ivn_artifacts_session", ondelete="RESTRICT"),
        sa.CheckConstraint(
            "(storage = 'inline' AND inline_content IS NOT NULL AND external_uri IS NULL)"
            " OR (storage = 'external' AND external_uri IS NOT NULL"
            " AND inline_content IS NULL)",
            name="ck_ivn_artifacts_storage_location"),
        sa.CheckConstraint("redaction_status IN ('not_required','applied','unknown')",
                           name="ck_ivn_artifacts_redaction"),
        sa.CheckConstraint(f"content_hash ~ '{_SHA256}'",
                           name="ck_ivn_artifacts_content_hash"),
        sa.CheckConstraint("byte_size >= 0", name="ck_ivn_artifacts_byte_size"),
        sa.CheckConstraint(f"kind ~ '{_STABLE_NAME}'", name="ck_ivn_artifacts_kind_name"),
        sa.CheckConstraint(f"retention_class ~ '{_STABLE_NAME}'",
                           name="ck_ivn_artifacts_retention_name"),
    )
    op.create_index("ix_ivn_artifacts_tenant_session_created", "interview_vnext_artifacts",
                    ["tenant_id", "session_id", "created_at"])
    op.create_index("ix_ivn_artifacts_operation_attempt", "interview_vnext_artifacts",
                    ["operation_id", "attempt_id"])

    # ── 4. circular FKs(artifacts 建好後才能加;§11.1 step 3)────────────────
    op.create_foreign_key(
        "fk_ivn_sessions_initial_state", "interview_vnext_sessions",
        "interview_vnext_artifacts",
        ["tenant_id", "initial_state_artifact_id"], ["tenant_id", "artifact_id"],
        ondelete="RESTRICT")
    op.create_foreign_key(
        "fk_ivn_runs_manifest_artifact", "interview_vnext_runs",
        "interview_vnext_artifacts",
        ["tenant_id", "manifest_artifact_id"], ["tenant_id", "artifact_id"],
        ondelete="RESTRICT")

    # ── 5. commands ──────────────────────────────────────────────────────────
    op.create_table(
        "interview_vnext_commands",
        sa.Column("command_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", UUID(as_uuid=True), nullable=False),
        sa.Column("request_idempotency_key", sa.Text(), nullable=True),
        sa.Column("command_schema_id", sa.Text(), nullable=False),
        sa.Column("command_artifact_id", UUID(as_uuid=True), nullable=False),
        sa.Column("command_hash", sa.Text(), nullable=False),
        sa.Column("reduction_artifact_id", UUID(as_uuid=True), nullable=False),
        sa.Column("reduction_hash", sa.Text(), nullable=False),
        sa.Column("expected_state_version", sa.BigInteger(), nullable=False),
        sa.Column("result_state_version", sa.BigInteger(), nullable=False),
        sa.Column("result_state_hash", sa.Text(), nullable=False),
        sa.Column("result_reason_code", sa.Text(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("committed_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "session_id", "command_id",
                            name="uq_ivn_commands_tenant_session_command"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "session_id"],
            ["interview_vnext_sessions.tenant_id", "interview_vnext_sessions.session_id"],
            name="fk_ivn_commands_session", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "run_id"],
            ["interview_vnext_runs.tenant_id", "interview_vnext_runs.run_id"],
            name="fk_ivn_commands_run", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "command_artifact_id"],
            ["interview_vnext_artifacts.tenant_id", "interview_vnext_artifacts.artifact_id"],
            name="fk_ivn_commands_command_artifact", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "reduction_artifact_id"],
            ["interview_vnext_artifacts.tenant_id", "interview_vnext_artifacts.artifact_id"],
            name="fk_ivn_commands_reduction_artifact", ondelete="RESTRICT"),
        sa.CheckConstraint(f"command_hash ~ '{_SHA256}'",
                           name="ck_ivn_commands_command_hash"),
        sa.CheckConstraint(f"reduction_hash ~ '{_SHA256}'",
                           name="ck_ivn_commands_reduction_hash"),
        sa.CheckConstraint(f"result_state_hash ~ '{_SHA256}'",
                           name="ck_ivn_commands_result_hash"),
        sa.CheckConstraint(
            "expected_state_version >= 0"
            " AND result_state_version = expected_state_version + 1",
            name="ck_ivn_commands_version_increment"),
        sa.CheckConstraint(f"result_reason_code ~ '{_STABLE_NAME}'",
                           name="ck_ivn_commands_reason_name"),
    )
    op.create_index("uq_ivn_commands_request_key", "interview_vnext_commands",
                    ["tenant_id", "session_id", "request_idempotency_key"],
                    unique=True,
                    postgresql_where=sa.text("request_idempotency_key IS NOT NULL"))

    # ── 6. execution events ──────────────────────────────────────────────────
    op.create_table(
        "interview_vnext_execution_events",
        sa.Column("event_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", UUID(as_uuid=True), nullable=False),
        sa.Column("turn_id", UUID(as_uuid=True), nullable=True),
        sa.Column("operation_id", UUID(as_uuid=True), nullable=True),
        sa.Column("parent_operation_id", UUID(as_uuid=True), nullable=True),
        sa.Column("attempt_id", UUID(as_uuid=True), nullable=True),
        sa.Column("attempt", sa.Integer(), nullable=True),
        sa.Column("event_schema_version", sa.Text(), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("stage", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("sequence", sa.BigInteger(), nullable=False),
        sa.Column("previous_event_hash", sa.Text(), nullable=True),
        sa.Column("event_hash", sa.Text(), nullable=False),
        sa.Column("event_json", sa.Text(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "run_id", "sequence",
                            name="uq_ivn_events_tenant_run_sequence"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "run_id"],
            ["interview_vnext_runs.tenant_id", "interview_vnext_runs.run_id"],
            name="fk_ivn_events_run", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "session_id"],
            ["interview_vnext_sessions.tenant_id", "interview_vnext_sessions.session_id"],
            name="fk_ivn_events_session", ondelete="RESTRICT"),
        sa.CheckConstraint("status IN ('ok','partial','failed','skipped')",
                           name="ck_ivn_events_status"),
        sa.CheckConstraint("sequence >= 1", name="ck_ivn_events_sequence_positive"),
        sa.CheckConstraint(
            "(sequence = 1 AND previous_event_hash IS NULL)"
            " OR (sequence > 1 AND previous_event_hash IS NOT NULL)",
            name="ck_ivn_events_chain_link"),
        sa.CheckConstraint(
            "(attempt IS NULL AND attempt_id IS NULL)"
            " OR (attempt >= 1 AND attempt_id IS NOT NULL AND operation_id IS NOT NULL)",
            name="ck_ivn_events_attempt_pair"),
        sa.CheckConstraint(f"event_hash ~ '{_SHA256}'", name="ck_ivn_events_event_hash"),
        sa.CheckConstraint(
            f"previous_event_hash IS NULL OR previous_event_hash ~ '{_SHA256}'",
            name="ck_ivn_events_previous_hash"),
        sa.CheckConstraint("jsonb_typeof(event_json::jsonb) = 'object'",
                           name="ck_ivn_events_event_json_object"),
    )
    op.create_index("ix_ivn_events_tenant_session_occurred",
                    "interview_vnext_execution_events",
                    ["tenant_id", "session_id", "occurred_at"])
    op.create_index("ix_ivn_events_operation_attempt",
                    "interview_vnext_execution_events",
                    ["operation_id", "attempt_id"])

    # ── 7. outbox ────────────────────────────────────────────────────────────
    op.create_table(
        "interview_vnext_outbox",
        sa.Column("message_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", UUID(as_uuid=True), nullable=False),
        sa.Column("event_sequence", sa.BigInteger(), nullable=False),
        sa.Column("event_hash", sa.Text(), nullable=False),
        sa.Column("event_json", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("delivery_attempts", sa.Integer(), nullable=False),
        sa.Column("lease_owner", sa.Text(), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["message_id"],
                                ["interview_vnext_execution_events.event_id"],
                                name="fk_ivn_outbox_event", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "run_id"],
            ["interview_vnext_runs.tenant_id", "interview_vnext_runs.run_id"],
            name="fk_ivn_outbox_run", ondelete="RESTRICT"),
        sa.UniqueConstraint("tenant_id", "run_id", "event_sequence",
                            name="uq_ivn_outbox_tenant_run_sequence"),
        sa.CheckConstraint(
            "status IN ('pending','leased','retry_wait','delivered','dead_letter')",
            name="ck_ivn_outbox_status"),
        sa.CheckConstraint("delivery_attempts >= 0", name="ck_ivn_outbox_attempts"),
        sa.CheckConstraint("event_sequence >= 1", name="ck_ivn_outbox_sequence"),
        sa.CheckConstraint(f"event_hash ~ '{_SHA256}'", name="ck_ivn_outbox_event_hash"),
        sa.CheckConstraint("jsonb_typeof(event_json::jsonb) = 'object'",
                           name="ck_ivn_outbox_event_json_object"),
        sa.CheckConstraint(
            "(status = 'leased' AND lease_owner IS NOT NULL"
            " AND lease_expires_at IS NOT NULL)"
            " OR (status <> 'leased' AND lease_owner IS NULL"
            " AND lease_expires_at IS NULL)",
            name="ck_ivn_outbox_lease_shape"),
        sa.CheckConstraint(
            "(status = 'retry_wait' AND next_attempt_at IS NOT NULL)"
            " OR (status <> 'retry_wait' AND next_attempt_at IS NULL)",
            name="ck_ivn_outbox_retry_shape"),
        sa.CheckConstraint(
            "(status = 'delivered' AND delivered_at IS NOT NULL)"
            " OR (status <> 'delivered' AND delivered_at IS NULL)",
            name="ck_ivn_outbox_delivered_shape"),
        sa.CheckConstraint(
            "status NOT IN ('retry_wait','dead_letter') OR last_error_code IS NOT NULL",
            name="ck_ivn_outbox_error_shape"),
        sa.CheckConstraint("updated_at >= created_at", name="ck_ivn_outbox_time_order"),
    )
    op.create_index("ix_ivn_outbox_pending", "interview_vnext_outbox",
                    ["created_at", "message_id"],
                    postgresql_where=sa.text("status = 'pending'"))
    op.create_index("ix_ivn_outbox_retry", "interview_vnext_outbox",
                    ["next_attempt_at", "created_at", "message_id"],
                    postgresql_where=sa.text("status = 'retry_wait'"))
    op.create_index("ix_ivn_outbox_expired", "interview_vnext_outbox",
                    ["lease_expires_at", "message_id"],
                    postgresql_where=sa.text("status = 'leased'"))
    op.create_index("ix_ivn_outbox_run_ordering", "interview_vnext_outbox",
                    ["tenant_id", "run_id", "event_sequence", "status"])

    # ── 8. operation checkpoints ─────────────────────────────────────────────
    op.create_table(
        "interview_vnext_operation_checkpoints",
        sa.Column("checkpoint_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", UUID(as_uuid=True), nullable=False),
        sa.Column("turn_id", UUID(as_uuid=True), nullable=True),
        sa.Column("operation_id", UUID(as_uuid=True), nullable=False),
        sa.Column("operation_name", sa.Text(), nullable=False),
        sa.Column("operation_definition_hash", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("revision", sa.BigInteger(), nullable=False),
        sa.Column("checkpoint_schema_version", sa.Text(), nullable=False),
        sa.Column("checkpoint_json", sa.Text(), nullable=False),
        sa.Column("request_artifact_id", UUID(as_uuid=True), nullable=False),
        sa.Column("active_attempt_id", UUID(as_uuid=True), nullable=True),
        sa.Column("active_attempt", sa.Integer(), nullable=True),
        sa.Column("provider_result_artifact_id", UUID(as_uuid=True), nullable=True),
        sa.Column("verification_artifact_id", UUID(as_uuid=True), nullable=True),
        sa.Column("domain_result_artifact_id", UUID(as_uuid=True), nullable=True),
        sa.Column("response_artifact_id", UUID(as_uuid=True), nullable=True),
        sa.Column("failure_artifact_id", UUID(as_uuid=True), nullable=True),
        sa.Column("failure_reason_code", sa.Text(), nullable=True),
        sa.Column("state_before_hash", sa.Text(), nullable=False),
        sa.Column("state_after_hash", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "operation_id",
                            name="uq_ivn_ckpt_tenant_operation"),
        sa.UniqueConstraint("tenant_id", "session_id", "operation_name",
                            "idempotency_key", name="uq_ivn_ckpt_idempotency"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "run_id"],
            ["interview_vnext_runs.tenant_id", "interview_vnext_runs.run_id"],
            name="fk_ivn_ckpt_run", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "session_id"],
            ["interview_vnext_sessions.tenant_id", "interview_vnext_sessions.session_id"],
            name="fk_ivn_ckpt_session", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "request_artifact_id"],
            ["interview_vnext_artifacts.tenant_id", "interview_vnext_artifacts.artifact_id"],
            name="fk_ivn_ckpt_request_artifact", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "provider_result_artifact_id"],
            ["interview_vnext_artifacts.tenant_id", "interview_vnext_artifacts.artifact_id"],
            name="fk_ivn_ckpt_provider_result", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "verification_artifact_id"],
            ["interview_vnext_artifacts.tenant_id", "interview_vnext_artifacts.artifact_id"],
            name="fk_ivn_ckpt_verification", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "domain_result_artifact_id"],
            ["interview_vnext_artifacts.tenant_id", "interview_vnext_artifacts.artifact_id"],
            name="fk_ivn_ckpt_domain_result", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "response_artifact_id"],
            ["interview_vnext_artifacts.tenant_id", "interview_vnext_artifacts.artifact_id"],
            name="fk_ivn_ckpt_response", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "failure_artifact_id"],
            ["interview_vnext_artifacts.tenant_id", "interview_vnext_artifacts.artifact_id"],
            name="fk_ivn_ckpt_failure", ondelete="RESTRICT"),
        sa.CheckConstraint(
            "status IN ('prepared','calling','provider_completed',"
            "'verified','committed','failed')",
            name="ck_ivn_ckpt_status"),
        sa.CheckConstraint("revision >= 0", name="ck_ivn_ckpt_revision"),
        sa.CheckConstraint(
            "(status = 'prepared' AND active_attempt_id IS NULL"
            " AND active_attempt IS NULL)"
            " OR (status <> 'prepared' AND active_attempt_id IS NOT NULL"
            " AND active_attempt >= 1)",
            name="ck_ivn_ckpt_attempt_shape"),
        sa.CheckConstraint(
            "(status IN ('provider_completed','verified','committed')"
            " AND provider_result_artifact_id IS NOT NULL)"
            " OR (status IN ('prepared','calling')"
            " AND provider_result_artifact_id IS NULL)"
            " OR status = 'failed'",
            name="ck_ivn_ckpt_provider_shape"),
        sa.CheckConstraint(
            "(status IN ('verified','committed')"
            " AND verification_artifact_id IS NOT NULL)"
            " OR (status IN ('prepared','calling','provider_completed')"
            " AND verification_artifact_id IS NULL)"
            " OR status = 'failed'",
            name="ck_ivn_ckpt_verification_shape"),
        sa.CheckConstraint(
            "(status = 'committed' AND domain_result_artifact_id IS NOT NULL"
            " AND response_artifact_id IS NOT NULL AND state_after_hash IS NOT NULL)"
            " OR (status <> 'committed' AND domain_result_artifact_id IS NULL"
            " AND response_artifact_id IS NULL AND state_after_hash IS NULL)",
            name="ck_ivn_ckpt_committed_shape"),
        sa.CheckConstraint(
            "(status = 'failed' AND failure_artifact_id IS NOT NULL"
            " AND failure_reason_code IS NOT NULL)"
            " OR (status <> 'failed' AND failure_artifact_id IS NULL"
            " AND failure_reason_code IS NULL)",
            name="ck_ivn_ckpt_failed_shape"),
        sa.CheckConstraint(f"operation_definition_hash ~ '{_SHA256}'",
                           name="ck_ivn_ckpt_definition_hash"),
        sa.CheckConstraint(f"state_before_hash ~ '{_SHA256}'",
                           name="ck_ivn_ckpt_before_hash"),
        sa.CheckConstraint(f"state_after_hash IS NULL OR state_after_hash ~ '{_SHA256}'",
                           name="ck_ivn_ckpt_after_hash"),
        sa.CheckConstraint("jsonb_typeof(checkpoint_json::jsonb) = 'object'",
                           name="ck_ivn_ckpt_json_object"),
        sa.CheckConstraint("updated_at >= created_at", name="ck_ivn_ckpt_time_order"),
    )

    # ── 9. operation attempts ────────────────────────────────────────────────
    op.create_table(
        "interview_vnext_operation_attempts",
        sa.Column("attempt_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", UUID(as_uuid=True), nullable=False),
        sa.Column("operation_id", UUID(as_uuid=True), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("request_artifact_id", UUID(as_uuid=True), nullable=False),
        sa.Column("result_artifact_id", UUID(as_uuid=True), nullable=True),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("requested_model", sa.Text(), nullable=False),
        sa.Column("provider_execution_ref_kind", sa.Text(), nullable=True),
        sa.Column("provider_execution_ref", sa.Text(), nullable=True),
        sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("tenant_id", "attempt_id",
                            name="uq_ivn_attempts_tenant_attempt"),
        sa.UniqueConstraint("tenant_id", "operation_id", "attempt",
                            name="uq_ivn_attempts_operation_attempt"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "operation_id"],
            ["interview_vnext_operation_checkpoints.tenant_id",
             "interview_vnext_operation_checkpoints.operation_id"],
            name="fk_ivn_attempts_checkpoint", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "run_id"],
            ["interview_vnext_runs.tenant_id", "interview_vnext_runs.run_id"],
            name="fk_ivn_attempts_run", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "session_id"],
            ["interview_vnext_sessions.tenant_id", "interview_vnext_sessions.session_id"],
            name="fk_ivn_attempts_session", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "request_artifact_id"],
            ["interview_vnext_artifacts.tenant_id", "interview_vnext_artifacts.artifact_id"],
            name="fk_ivn_attempts_request_artifact", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "result_artifact_id"],
            ["interview_vnext_artifacts.tenant_id", "interview_vnext_artifacts.artifact_id"],
            name="fk_ivn_attempts_result_artifact", ondelete="RESTRICT"),
        sa.CheckConstraint("status IN ('calling','result_recorded')",
                           name="ck_ivn_attempts_status"),
        sa.CheckConstraint("attempt >= 1", name="ck_ivn_attempts_number"),
        sa.CheckConstraint(
            "(status = 'calling' AND result_artifact_id IS NULL"
            " AND completed_at IS NULL)"
            " OR (status = 'result_recorded' AND result_artifact_id IS NOT NULL"
            " AND completed_at IS NOT NULL)",
            name="ck_ivn_attempts_result_shape"),
        sa.CheckConstraint(
            "(provider_execution_ref_kind IS NULL AND provider_execution_ref IS NULL)"
            " OR (provider_execution_ref_kind IS NOT NULL"
            " AND provider_execution_ref IS NOT NULL)",
            name="ck_ivn_attempts_ref_pair"),
        sa.CheckConstraint(f"provider ~ '{_STABLE_NAME}'", name="ck_ivn_attempts_provider"),
        sa.CheckConstraint(
            "updated_at >= started_at"
            " AND (completed_at IS NULL OR completed_at >= started_at)",
            name="ck_ivn_attempts_time_order"),
    )

    # ── 10. triggers:immutability(artifact/event/command)+ outbox guard ────
    op.execute("""
        CREATE FUNCTION ivn_reject_update() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION '% rows are immutable', TG_TABLE_NAME;
        END $$;
    """)
    for table, trigger in (
        ("interview_vnext_artifacts", "ivn_artifacts_reject_update"),
        ("interview_vnext_execution_events", "ivn_events_reject_update"),
        ("interview_vnext_commands", "ivn_commands_reject_update"),
    ):
        op.execute(f"""
            CREATE TRIGGER {trigger}
            BEFORE UPDATE ON {table}
            FOR EACH ROW EXECUTE FUNCTION ivn_reject_update();
        """)

    # outbox 第二道防線:identity/payload 不可改;status 只依 §5.6 合法 transition。
    # owner 一致性由 repository 的 SQL WHERE 驗(trigger 不知道 caller 是誰);
    # trigger 把關「時間/計數/欄位形狀在該 transition 下合法」。
    op.execute("""
        CREATE FUNCTION ivn_outbox_guard() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.message_id <> OLD.message_id
               OR NEW.tenant_id <> OLD.tenant_id
               OR NEW.run_id <> OLD.run_id
               OR NEW.event_sequence <> OLD.event_sequence
               OR NEW.event_hash <> OLD.event_hash
               OR NEW.event_json <> OLD.event_json
               OR NEW.created_at <> OLD.created_at THEN
                RAISE EXCEPTION 'interview_vnext_outbox identity/payload is immutable';
            END IF;
            IF NOT (
                (OLD.status = 'pending' AND NEW.status = 'leased'
                    AND NEW.delivery_attempts = OLD.delivery_attempts + 1
                    AND NEW.lease_expires_at > CURRENT_TIMESTAMP)
                OR (OLD.status = 'retry_wait' AND NEW.status = 'leased'
                    AND OLD.next_attempt_at <= CURRENT_TIMESTAMP
                    AND NEW.delivery_attempts = OLD.delivery_attempts + 1
                    AND NEW.lease_expires_at > CURRENT_TIMESTAMP)
                OR (OLD.status = 'leased' AND NEW.status = 'leased'
                    AND OLD.lease_expires_at <= CURRENT_TIMESTAMP
                    AND NEW.delivery_attempts = OLD.delivery_attempts + 1
                    AND NEW.lease_expires_at > CURRENT_TIMESTAMP)
                OR (OLD.status = 'leased' AND NEW.status = 'delivered'
                    AND OLD.lease_expires_at >= CURRENT_TIMESTAMP
                    AND NEW.delivery_attempts = OLD.delivery_attempts)
                OR (OLD.status = 'leased' AND NEW.status = 'retry_wait'
                    AND OLD.lease_expires_at >= CURRENT_TIMESTAMP
                    AND NEW.delivery_attempts = OLD.delivery_attempts
                    AND NEW.next_attempt_at > CURRENT_TIMESTAMP)
                OR (OLD.status = 'leased' AND NEW.status = 'dead_letter'
                    AND OLD.lease_expires_at >= CURRENT_TIMESTAMP
                    AND NEW.delivery_attempts = OLD.delivery_attempts)
            ) THEN
                RAISE EXCEPTION
                    'illegal interview_vnext_outbox transition % -> %',
                    OLD.status, NEW.status;
            END IF;
            RETURN NEW;
        END $$;
    """)
    op.execute("""
        CREATE TRIGGER ivn_outbox_guard_update
        BEFORE UPDATE ON interview_vnext_outbox
        FOR EACH ROW EXECUTE FUNCTION ivn_outbox_guard();
    """)


def downgrade() -> None:
    """只在無 production vNext data 的開發/測試使用(§11.2);不碰 v3。"""
    # 1. triggers/functions
    op.execute("DROP TRIGGER IF EXISTS ivn_outbox_guard_update ON interview_vnext_outbox")
    op.execute("DROP FUNCTION IF EXISTS ivn_outbox_guard()")
    for table, trigger in (
        ("interview_vnext_artifacts", "ivn_artifacts_reject_update"),
        ("interview_vnext_execution_events", "ivn_events_reject_update"),
        ("interview_vnext_commands", "ivn_commands_reject_update"),
    ):
        op.execute(f"DROP TRIGGER IF EXISTS {trigger} ON {table}")
    op.execute("DROP FUNCTION IF EXISTS ivn_reject_update()")

    # 2. circular FKs
    op.drop_constraint("fk_ivn_sessions_initial_state", "interview_vnext_sessions",
                       type_="foreignkey")
    op.drop_constraint("fk_ivn_runs_manifest_artifact", "interview_vnext_runs",
                       type_="foreignkey")

    # 3. reverse drop
    op.drop_table("interview_vnext_operation_attempts")
    op.drop_table("interview_vnext_operation_checkpoints")
    op.drop_table("interview_vnext_outbox")
    op.drop_table("interview_vnext_execution_events")
    op.drop_table("interview_vnext_commands")
    op.drop_table("interview_vnext_artifacts")
    op.drop_table("interview_vnext_runs")
    op.drop_table("interview_vnext_sessions")
