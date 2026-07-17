"""SQLAlchemy rows for vNext durable persistence (V2-B reference §5/§6).

Adapter-only: rows never cross into domain/application — repositories hydrate
Pydantic contracts through ``serialization.py`` on every read. Canonical
payloads live in TEXT (exact hashed bytes; JSONB would re-serialize them),
query fields are normalized columns. Statuses are Text + named CheckConstraint
(no native ENUM); no ORM cascade, no relationship(), no ``version_id_col`` —
session/checkpoint CAS is explicit SQL in the repositories.

Naming: ``uq_/ix_/ck_/fk_ivn_*`` (all identifiers < 63 bytes). Composite
``(tenant_id, …)`` FKs keep every cross-table link inside one tenant (§2.3).
The two circular FKs (session initial-state, run manifest) use ``use_alter``
so metadata matches migration 0010, which adds them after ``artifacts``.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


_SHA256 = r"^sha256:[0-9a-f]{64}$"
_STABLE_NAME = r"^[a-z][a-z0-9]*([._-][a-z0-9]+)*$"


class VNextSessionRow(Base):
    """§5.1:materialized aggregate state 的唯一權威列(CAS 更新)。"""

    __tablename__ = "interview_vnext_sessions"

    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    profile_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    architecture_id: Mapped[str] = mapped_column(Text, nullable=False)
    workflow_version: Mapped[str] = mapped_column(Text, nullable=False)
    reference_snapshot_id: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    state_version: Mapped[int] = mapped_column(BigInteger, nullable=False)
    state_schema_version: Mapped[str] = mapped_column(Text, nullable=False)
    state_json: Mapped[str] = mapped_column(Text, nullable=False)
    state_hash: Mapped[str] = mapped_column(Text, nullable=False)
    initial_state_artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("tenant_id", "session_id", name="uq_ivn_sessions_tenant_session"),
        ForeignKeyConstraint(["profile_id"], ["job_profiles.id"],
                             name="fk_ivn_sessions_profile", ondelete="RESTRICT"),
        # circular:artifacts 建好後才加(migration 0010 同名 ALTER;use_alter 對齊)
        ForeignKeyConstraint(
            ["tenant_id", "initial_state_artifact_id"],
            ["interview_vnext_artifacts.tenant_id", "interview_vnext_artifacts.artifact_id"],
            name="fk_ivn_sessions_initial_state", ondelete="RESTRICT", use_alter=True),
        Index("ix_ivn_sessions_tenant_profile",
              "tenant_id", "profile_id", text("updated_at DESC")),
        CheckConstraint(
            "status IN ('planned','active','paused','finishing','completed','failed')",
            name="ck_ivn_sessions_status"),
        CheckConstraint("state_version >= 0", name="ck_ivn_sessions_state_version"),
        CheckConstraint(f"state_hash ~ '{_SHA256}'", name="ck_ivn_sessions_state_hash"),
        CheckConstraint("jsonb_typeof(state_json::jsonb) = 'object'",
                        name="ck_ivn_sessions_state_json_object"),
        CheckConstraint("updated_at >= created_at", name="ck_ivn_sessions_time_order"),
    )


class VNextRunRow(Base):
    """§5.2:durable workflow run(event hash-chain 擁有者)。
    terminal→manifest 非空**刻意不進 DB CHECK**(§5.2 裁決:cleanup 需暫時
    解除 pointer);由 WorkflowRun validator + finalize 協定 + hydrate
    corruption 檢查共同保證。"""

    __tablename__ = "interview_vnext_runs"

    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    architecture_id: Mapped[str] = mapped_column(Text, nullable=False)
    workflow_version: Mapped[str] = mapped_column(Text, nullable=False)
    taxonomy_id: Mapped[str] = mapped_column(Text, nullable=False)
    taxonomy_version: Mapped[str] = mapped_column(Text, nullable=False)
    taxonomy_hash: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    event_count: Mapped[int] = mapped_column(BigInteger, nullable=False)
    first_event_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_event_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    manifest_artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("tenant_id", "run_id", name="uq_ivn_runs_tenant_run"),
        ForeignKeyConstraint(
            ["tenant_id", "session_id"],
            ["interview_vnext_sessions.tenant_id", "interview_vnext_sessions.session_id"],
            name="fk_ivn_runs_session", ondelete="RESTRICT"),
        # circular:artifacts 建好後才加
        ForeignKeyConstraint(
            ["tenant_id", "manifest_artifact_id"],
            ["interview_vnext_artifacts.tenant_id", "interview_vnext_artifacts.artifact_id"],
            name="fk_ivn_runs_manifest_artifact", ondelete="RESTRICT", use_alter=True),
        Index("ix_ivn_runs_tenant_session_started",
              "tenant_id", "session_id", "started_at", "run_id"),
        CheckConstraint("status IN ('open','completed','failed')", name="ck_ivn_runs_status"),
        CheckConstraint("event_count >= 0", name="ck_ivn_runs_event_count"),
        CheckConstraint(
            "(event_count = 0 AND first_event_hash IS NULL AND last_event_hash IS NULL)"
            " OR (event_count > 0 AND first_event_hash IS NOT NULL"
            " AND last_event_hash IS NOT NULL)",
            name="ck_ivn_runs_event_hash_coherence"),
        CheckConstraint(
            "(status = 'open' AND completed_at IS NULL AND manifest_artifact_id IS NULL)"
            " OR (status IN ('completed','failed') AND completed_at IS NOT NULL"
            " AND event_count >= 1 AND completed_at >= started_at)",
            name="ck_ivn_runs_lifecycle"),
        CheckConstraint(f"first_event_hash IS NULL OR first_event_hash ~ '{_SHA256}'",
                        name="ck_ivn_runs_first_hash"),
        CheckConstraint(f"last_event_hash IS NULL OR last_event_hash ~ '{_SHA256}'",
                        name="ck_ivn_runs_last_hash"),
        CheckConstraint(f"taxonomy_hash ~ '{_SHA256}'", name="ck_ivn_runs_taxonomy_hash"),
    )


class VNextArtifactRow(Base):
    """§5.3:immutable replay/audit payload;UPDATE 由 trigger 拒絕(migration)。"""

    __tablename__ = "interview_vnext_artifacts"

    artifact_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    record_schema_version: Mapped[str] = mapped_column(Text, nullable=False)
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    session_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    turn_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    operation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    attempt_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    media_type: Mapped[str] = mapped_column(Text, nullable=False)
    schema_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_hash: Mapped[str] = mapped_column(Text, nullable=False)
    byte_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    storage: Mapped[str] = mapped_column(Text, nullable=False)
    inline_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    external_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    retention_class: Mapped[str] = mapped_column(Text, nullable=False)
    redaction_status: Mapped[str] = mapped_column(Text, nullable=False)
    contains_test_data: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("tenant_id", "artifact_id", name="uq_ivn_artifacts_tenant_artifact"),
        ForeignKeyConstraint(
            ["tenant_id", "run_id"],
            ["interview_vnext_runs.tenant_id", "interview_vnext_runs.run_id"],
            name="fk_ivn_artifacts_run", ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ["tenant_id", "session_id"],
            ["interview_vnext_sessions.tenant_id", "interview_vnext_sessions.session_id"],
            name="fk_ivn_artifacts_session", ondelete="RESTRICT"),
        Index("ix_ivn_artifacts_tenant_session_created",
              "tenant_id", "session_id", "created_at"),
        Index("ix_ivn_artifacts_operation_attempt", "operation_id", "attempt_id"),
        CheckConstraint(
            "(storage = 'inline' AND inline_content IS NOT NULL AND external_uri IS NULL)"
            " OR (storage = 'external' AND external_uri IS NOT NULL"
            " AND inline_content IS NULL)",
            name="ck_ivn_artifacts_storage_location"),
        CheckConstraint("redaction_status IN ('not_required','applied','unknown')",
                        name="ck_ivn_artifacts_redaction"),
        CheckConstraint(f"content_hash ~ '{_SHA256}'", name="ck_ivn_artifacts_content_hash"),
        CheckConstraint("byte_size >= 0", name="ck_ivn_artifacts_byte_size"),
        CheckConstraint(f"kind ~ '{_STABLE_NAME}'", name="ck_ivn_artifacts_kind_name"),
        CheckConstraint(f"retention_class ~ '{_STABLE_NAME}'",
                        name="ck_ivn_artifacts_retention_name"),
    )


class VNextCommandRow(Base):
    """§5.4:成功套用的 command 一列(idempotency record);immutable。
    occurred_at(domain clock)與 committed_at(DB clock)屬不同時鐘,刻意
    **不**建立跨時鐘大小 CHECK——時鐘偏差不該讓合法寫入失敗。"""

    __tablename__ = "interview_vnext_commands"

    command_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    request_idempotency_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    command_schema_id: Mapped[str] = mapped_column(Text, nullable=False)
    command_artifact_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    command_hash: Mapped[str] = mapped_column(Text, nullable=False)
    reduction_artifact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False)
    reduction_hash: Mapped[str] = mapped_column(Text, nullable=False)
    expected_state_version: Mapped[int] = mapped_column(BigInteger, nullable=False)
    result_state_version: Mapped[int] = mapped_column(BigInteger, nullable=False)
    result_state_hash: Mapped[str] = mapped_column(Text, nullable=False)
    result_reason_code: Mapped[str] = mapped_column(Text, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    committed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("tenant_id", "session_id", "command_id",
                         name="uq_ivn_commands_tenant_session_command"),
        ForeignKeyConstraint(
            ["tenant_id", "session_id"],
            ["interview_vnext_sessions.tenant_id", "interview_vnext_sessions.session_id"],
            name="fk_ivn_commands_session", ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ["tenant_id", "run_id"],
            ["interview_vnext_runs.tenant_id", "interview_vnext_runs.run_id"],
            name="fk_ivn_commands_run", ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ["tenant_id", "command_artifact_id"],
            ["interview_vnext_artifacts.tenant_id", "interview_vnext_artifacts.artifact_id"],
            name="fk_ivn_commands_command_artifact", ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ["tenant_id", "reduction_artifact_id"],
            ["interview_vnext_artifacts.tenant_id", "interview_vnext_artifacts.artifact_id"],
            name="fk_ivn_commands_reduction_artifact", ondelete="RESTRICT"),
        # partial unique(request key 可 null)= unique partial index,非 constraint
        Index("uq_ivn_commands_request_key",
              "tenant_id", "session_id", "request_idempotency_key",
              unique=True,
              postgresql_where=text("request_idempotency_key IS NOT NULL")),
        CheckConstraint(f"command_hash ~ '{_SHA256}'", name="ck_ivn_commands_command_hash"),
        CheckConstraint(f"reduction_hash ~ '{_SHA256}'",
                        name="ck_ivn_commands_reduction_hash"),
        CheckConstraint(f"result_state_hash ~ '{_SHA256}'",
                        name="ck_ivn_commands_result_hash"),
        CheckConstraint(
            "expected_state_version >= 0"
            " AND result_state_version = expected_state_version + 1",
            name="ck_ivn_commands_version_increment"),
        CheckConstraint(f"result_reason_code ~ '{_STABLE_NAME}'",
                        name="ck_ivn_commands_reason_name"),
    )


class VNextExecutionEventRow(Base):
    """§5.5:hash-chained execution event;immutable;sequence 由 append 交易配發。
    session_id 收窄為 NOT NULL(envelope optional shape 的 DB 收緊)。"""

    __tablename__ = "interview_vnext_execution_events"

    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    turn_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    operation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    parent_operation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True)
    attempt_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    attempt: Mapped[int | None] = mapped_column(Integer, nullable=True)
    event_schema_version: Mapped[str] = mapped_column(Text, nullable=False)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    stage: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    sequence: Mapped[int] = mapped_column(BigInteger, nullable=False)
    previous_event_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    event_hash: Mapped[str] = mapped_column(Text, nullable=False)
    event_json: Mapped[str] = mapped_column(Text, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("tenant_id", "run_id", "sequence",
                         name="uq_ivn_events_tenant_run_sequence"),
        ForeignKeyConstraint(
            ["tenant_id", "run_id"],
            ["interview_vnext_runs.tenant_id", "interview_vnext_runs.run_id"],
            name="fk_ivn_events_run", ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ["tenant_id", "session_id"],
            ["interview_vnext_sessions.tenant_id", "interview_vnext_sessions.session_id"],
            name="fk_ivn_events_session", ondelete="RESTRICT"),
        Index("ix_ivn_events_tenant_session_occurred",
              "tenant_id", "session_id", "occurred_at"),
        Index("ix_ivn_events_operation_attempt", "operation_id", "attempt_id"),
        CheckConstraint("status IN ('ok','partial','failed','skipped')",
                        name="ck_ivn_events_status"),
        CheckConstraint("sequence >= 1", name="ck_ivn_events_sequence_positive"),
        CheckConstraint(
            "(sequence = 1 AND previous_event_hash IS NULL)"
            " OR (sequence > 1 AND previous_event_hash IS NOT NULL)",
            name="ck_ivn_events_chain_link"),
        CheckConstraint(
            "(attempt IS NULL AND attempt_id IS NULL)"
            " OR (attempt >= 1 AND attempt_id IS NOT NULL AND operation_id IS NOT NULL)",
            name="ck_ivn_events_attempt_pair"),
        CheckConstraint(f"event_hash ~ '{_SHA256}'", name="ck_ivn_events_event_hash"),
        CheckConstraint(f"previous_event_hash IS NULL OR previous_event_hash ~ '{_SHA256}'",
                        name="ck_ivn_events_previous_hash"),
        CheckConstraint("jsonb_typeof(event_json::jsonb) = 'object'",
                        name="ck_ivn_events_event_json_object"),
    )


class VNextOutboxRow(Base):
    """§5.6:transactional outbox(at-least-once;message_id = event_id)。
    identity/payload immutable + 合法 transition 由 trigger 第二道防線把關。"""

    __tablename__ = "interview_vnext_outbox"

    message_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    event_sequence: Mapped[int] = mapped_column(BigInteger, nullable=False)
    event_hash: Mapped[str] = mapped_column(Text, nullable=False)
    event_json: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    delivery_attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    lease_owner: Mapped[str | None] = mapped_column(Text, nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    next_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    last_error_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(["message_id"], ["interview_vnext_execution_events.event_id"],
                             name="fk_ivn_outbox_event", ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ["tenant_id", "run_id"],
            ["interview_vnext_runs.tenant_id", "interview_vnext_runs.run_id"],
            name="fk_ivn_outbox_run", ondelete="RESTRICT"),
        UniqueConstraint("tenant_id", "run_id", "event_sequence",
                         name="uq_ivn_outbox_tenant_run_sequence"),
        # lease queue partial indexes:predicate 與 lease query 的 status 條件完全一致
        Index("ix_ivn_outbox_pending", "created_at", "message_id",
              postgresql_where=text("status = 'pending'")),
        Index("ix_ivn_outbox_retry", "next_attempt_at", "created_at", "message_id",
              postgresql_where=text("status = 'retry_wait'")),
        Index("ix_ivn_outbox_expired", "lease_expires_at", "message_id",
              postgresql_where=text("status = 'leased'")),
        Index("ix_ivn_outbox_run_ordering",
              "tenant_id", "run_id", "event_sequence", "status"),
        CheckConstraint(
            "status IN ('pending','leased','retry_wait','delivered','dead_letter')",
            name="ck_ivn_outbox_status"),
        CheckConstraint("delivery_attempts >= 0", name="ck_ivn_outbox_attempts"),
        CheckConstraint("event_sequence >= 1", name="ck_ivn_outbox_sequence"),
        CheckConstraint(f"event_hash ~ '{_SHA256}'", name="ck_ivn_outbox_event_hash"),
        CheckConstraint("jsonb_typeof(event_json::jsonb) = 'object'",
                        name="ck_ivn_outbox_event_json_object"),
        CheckConstraint(
            "(status = 'leased' AND lease_owner IS NOT NULL"
            " AND lease_expires_at IS NOT NULL)"
            " OR (status <> 'leased' AND lease_owner IS NULL"
            " AND lease_expires_at IS NULL)",
            name="ck_ivn_outbox_lease_shape"),
        CheckConstraint(
            "(status = 'retry_wait' AND next_attempt_at IS NOT NULL)"
            " OR (status <> 'retry_wait' AND next_attempt_at IS NULL)",
            name="ck_ivn_outbox_retry_shape"),
        CheckConstraint(
            "(status = 'delivered' AND delivered_at IS NOT NULL)"
            " OR (status <> 'delivered' AND delivered_at IS NULL)",
            name="ck_ivn_outbox_delivered_shape"),
        CheckConstraint(
            "status NOT IN ('retry_wait','dead_letter') OR last_error_code IS NOT NULL",
            name="ck_ivn_outbox_error_shape"),
        CheckConstraint("updated_at >= created_at", name="ck_ivn_outbox_time_order"),
    )


class VNextCheckpointRow(Base):
    """§5.7:durable operation checkpoint;revision 是 CAS token(explicit SQL)。"""

    __tablename__ = "interview_vnext_operation_checkpoints"

    checkpoint_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    turn_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    operation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    operation_name: Mapped[str] = mapped_column(Text, nullable=False)
    operation_definition_hash: Mapped[str] = mapped_column(Text, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    revision: Mapped[int] = mapped_column(BigInteger, nullable=False)
    checkpoint_schema_version: Mapped[str] = mapped_column(Text, nullable=False)
    checkpoint_json: Mapped[str] = mapped_column(Text, nullable=False)
    request_artifact_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    active_attempt_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True)
    active_attempt: Mapped[int | None] = mapped_column(Integer, nullable=True)
    provider_result_artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True)
    verification_artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True)
    domain_result_artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True)
    response_artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True)
    failure_artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True)
    failure_reason_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    state_before_hash: Mapped[str] = mapped_column(Text, nullable=False)
    state_after_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("tenant_id", "operation_id", name="uq_ivn_ckpt_tenant_operation"),
        UniqueConstraint("tenant_id", "session_id", "operation_name", "idempotency_key",
                         name="uq_ivn_ckpt_idempotency"),
        ForeignKeyConstraint(
            ["tenant_id", "run_id"],
            ["interview_vnext_runs.tenant_id", "interview_vnext_runs.run_id"],
            name="fk_ivn_ckpt_run", ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ["tenant_id", "session_id"],
            ["interview_vnext_sessions.tenant_id", "interview_vnext_sessions.session_id"],
            name="fk_ivn_ckpt_session", ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ["tenant_id", "request_artifact_id"],
            ["interview_vnext_artifacts.tenant_id", "interview_vnext_artifacts.artifact_id"],
            name="fk_ivn_ckpt_request_artifact", ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ["tenant_id", "provider_result_artifact_id"],
            ["interview_vnext_artifacts.tenant_id", "interview_vnext_artifacts.artifact_id"],
            name="fk_ivn_ckpt_provider_result", ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ["tenant_id", "verification_artifact_id"],
            ["interview_vnext_artifacts.tenant_id", "interview_vnext_artifacts.artifact_id"],
            name="fk_ivn_ckpt_verification", ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ["tenant_id", "domain_result_artifact_id"],
            ["interview_vnext_artifacts.tenant_id", "interview_vnext_artifacts.artifact_id"],
            name="fk_ivn_ckpt_domain_result", ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ["tenant_id", "response_artifact_id"],
            ["interview_vnext_artifacts.tenant_id", "interview_vnext_artifacts.artifact_id"],
            name="fk_ivn_ckpt_response", ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ["tenant_id", "failure_artifact_id"],
            ["interview_vnext_artifacts.tenant_id", "interview_vnext_artifacts.artifact_id"],
            name="fk_ivn_ckpt_failure", ondelete="RESTRICT"),
        CheckConstraint(
            "status IN ('prepared','calling','provider_completed',"
            "'verified','committed','failed')",
            name="ck_ivn_ckpt_status"),
        CheckConstraint("revision >= 0", name="ck_ivn_ckpt_revision"),
        CheckConstraint(
            "(status = 'prepared' AND active_attempt_id IS NULL"
            " AND active_attempt IS NULL)"
            " OR (status <> 'prepared' AND active_attempt_id IS NOT NULL"
            " AND active_attempt >= 1)",
            name="ck_ivn_ckpt_attempt_shape"),
        CheckConstraint(
            "(status IN ('provider_completed','verified','committed')"
            " AND provider_result_artifact_id IS NOT NULL)"
            " OR (status IN ('prepared','calling')"
            " AND provider_result_artifact_id IS NULL)"
            " OR status = 'failed'",
            name="ck_ivn_ckpt_provider_shape"),
        CheckConstraint(
            "(status IN ('verified','committed')"
            " AND verification_artifact_id IS NOT NULL)"
            " OR (status IN ('prepared','calling','provider_completed')"
            " AND verification_artifact_id IS NULL)"
            " OR status = 'failed'",
            name="ck_ivn_ckpt_verification_shape"),
        CheckConstraint(
            "(status = 'committed' AND domain_result_artifact_id IS NOT NULL"
            " AND response_artifact_id IS NOT NULL AND state_after_hash IS NOT NULL)"
            " OR (status <> 'committed' AND domain_result_artifact_id IS NULL"
            " AND response_artifact_id IS NULL AND state_after_hash IS NULL)",
            name="ck_ivn_ckpt_committed_shape"),
        CheckConstraint(
            "(status = 'failed' AND failure_artifact_id IS NOT NULL"
            " AND failure_reason_code IS NOT NULL)"
            " OR (status <> 'failed' AND failure_artifact_id IS NULL"
            " AND failure_reason_code IS NULL)",
            name="ck_ivn_ckpt_failed_shape"),
        CheckConstraint(f"operation_definition_hash ~ '{_SHA256}'",
                        name="ck_ivn_ckpt_definition_hash"),
        CheckConstraint(f"state_before_hash ~ '{_SHA256}'",
                        name="ck_ivn_ckpt_before_hash"),
        CheckConstraint(f"state_after_hash IS NULL OR state_after_hash ~ '{_SHA256}'",
                        name="ck_ivn_ckpt_after_hash"),
        CheckConstraint("jsonb_typeof(checkpoint_json::jsonb) = 'object'",
                        name="ck_ivn_ckpt_json_object"),
        CheckConstraint("updated_at >= created_at", name="ck_ivn_ckpt_time_order"),
    )


class VNextAttemptRow(Base):
    """§5.8:每次 model attempt 一列;只有 calling → result_recorded 一次性
    UPDATE,retry 一律 INSERT 新列。"""

    __tablename__ = "interview_vnext_operation_attempts"

    attempt_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    operation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    request_artifact_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    result_artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True)
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    requested_model: Mapped[str] = mapped_column(Text, nullable=False)
    provider_execution_ref_kind: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider_execution_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    deadline_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("tenant_id", "attempt_id", name="uq_ivn_attempts_tenant_attempt"),
        UniqueConstraint("tenant_id", "operation_id", "attempt",
                         name="uq_ivn_attempts_operation_attempt"),
        ForeignKeyConstraint(
            ["tenant_id", "operation_id"],
            ["interview_vnext_operation_checkpoints.tenant_id",
             "interview_vnext_operation_checkpoints.operation_id"],
            name="fk_ivn_attempts_checkpoint", ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ["tenant_id", "run_id"],
            ["interview_vnext_runs.tenant_id", "interview_vnext_runs.run_id"],
            name="fk_ivn_attempts_run", ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ["tenant_id", "session_id"],
            ["interview_vnext_sessions.tenant_id", "interview_vnext_sessions.session_id"],
            name="fk_ivn_attempts_session", ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ["tenant_id", "request_artifact_id"],
            ["interview_vnext_artifacts.tenant_id", "interview_vnext_artifacts.artifact_id"],
            name="fk_ivn_attempts_request_artifact", ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ["tenant_id", "result_artifact_id"],
            ["interview_vnext_artifacts.tenant_id", "interview_vnext_artifacts.artifact_id"],
            name="fk_ivn_attempts_result_artifact", ondelete="RESTRICT"),
        CheckConstraint("status IN ('calling','result_recorded')",
                        name="ck_ivn_attempts_status"),
        CheckConstraint("attempt >= 1", name="ck_ivn_attempts_number"),
        CheckConstraint(
            "(status = 'calling' AND result_artifact_id IS NULL"
            " AND completed_at IS NULL)"
            " OR (status = 'result_recorded' AND result_artifact_id IS NOT NULL"
            " AND completed_at IS NOT NULL)",
            name="ck_ivn_attempts_result_shape"),
        CheckConstraint(
            "(provider_execution_ref_kind IS NULL AND provider_execution_ref IS NULL)"
            " OR (provider_execution_ref_kind IS NOT NULL"
            " AND provider_execution_ref IS NOT NULL)",
            name="ck_ivn_attempts_ref_pair"),
        CheckConstraint(f"provider ~ '{_STABLE_NAME}'", name="ck_ivn_attempts_provider"),
        CheckConstraint(
            "updated_at >= started_at"
            " AND (completed_at IS NULL OR completed_at >= started_at)",
            name="ck_ivn_attempts_time_order"),
    )
