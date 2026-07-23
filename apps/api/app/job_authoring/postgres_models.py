"""SQLAlchemy rows for the Job Authoring Core (plan §11.1).

Adapter-only: rows never cross into the pure core — repositories hydrate the
Pydantic records in ``postgres.py`` on every read. Canonical payloads live in
TEXT (exact hashed bytes; JSONB would re-serialize them); query fields are
normalized columns. No ORM relationship/cascade/``version_id_col`` — head CAS
and lifecycle updates are explicit SQL in the repositories.

Registered on the app ``Base`` metadata (imported by ``alembic/env.py``) so
autogenerate matches migration ``0011``. Table/constraint names mirror that
migration exactly; triggers/functions are migration-only.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

_SHA256 = r"^sha256:[0-9a-f]{64}$"


class JobAuthoringDocumentRow(Base):
    __tablename__ = "job_authoring_documents"

    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    head_revision_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    head_revision_number: Mapped[int] = mapped_column(BigInteger, nullable=False)
    head_revision_hash: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("tenant_id", "document_id", name="uq_ja_docs_tenant_document"),
        UniqueConstraint("tenant_id", "session_id", name="uq_ja_docs_tenant_session"),
        ForeignKeyConstraint(
            ["tenant_id", "session_id"],
            ["interview_vnext_sessions.tenant_id", "interview_vnext_sessions.session_id"],
            name="fk_ja_docs_session", ondelete="RESTRICT"),
        CheckConstraint("head_revision_number >= 0", name="ck_ja_docs_head_number"),
        CheckConstraint(f"head_revision_hash ~ '{_SHA256}'", name="ck_ja_docs_head_hash"),
        CheckConstraint("updated_at >= created_at", name="ck_ja_docs_time_order"),
        Index("ix_ja_docs_tenant_updated", "tenant_id",
              text("updated_at DESC"), "document_id"),
    )


class JobAuthoringRevisionRow(Base):
    __tablename__ = "job_authoring_revisions"

    revision_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    revision_number: Mapped[int] = mapped_column(BigInteger, nullable=False)
    parent_revision_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True)
    source_kind: Mapped[str] = mapped_column(Text, nullable=False)
    command_schema_id: Mapped[str] = mapped_column(Text, nullable=False)
    command_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    command_json: Mapped[str] = mapped_column(Text, nullable=False)
    command_hash: Mapped[str] = mapped_column(Text, nullable=False)
    snapshot_schema_id: Mapped[str] = mapped_column(Text, nullable=False)
    snapshot_json: Mapped[str] = mapped_column(Text, nullable=False)
    snapshot_hash: Mapped[str] = mapped_column(Text, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("tenant_id", "revision_id", name="uq_ja_revs_tenant_revision"),
        UniqueConstraint("tenant_id", "document_id", "revision_number",
                         name="uq_ja_revs_document_number"),
        UniqueConstraint("tenant_id", "command_id", name="uq_ja_revs_tenant_command"),
        ForeignKeyConstraint(
            ["tenant_id", "document_id"],
            ["job_authoring_documents.tenant_id", "job_authoring_documents.document_id"],
            name="fk_ja_revs_document", ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ["tenant_id", "parent_revision_id"],
            ["job_authoring_revisions.tenant_id", "job_authoring_revisions.revision_id"],
            name="fk_ja_revs_parent", ondelete="RESTRICT"),
        CheckConstraint(
            "(revision_number = 0 AND source_kind = 'initial' "
            "AND parent_revision_id IS NULL) "
            "OR (revision_number > 0 AND source_kind <> 'initial' "
            "AND parent_revision_id IS NOT NULL)",
            name="ck_ja_revs_number_parent"),
        CheckConstraint(
            "source_kind IN ('initial','employee_direct_edit',"
            "'ai_proposal_accept','employee_proposal_edit')",
            name="ck_ja_revs_source"),
        CheckConstraint(f"command_hash ~ '{_SHA256}'", name="ck_ja_revs_command_hash"),
        CheckConstraint(f"snapshot_hash ~ '{_SHA256}'", name="ck_ja_revs_snapshot_hash"),
        CheckConstraint("jsonb_typeof(command_json::jsonb) = 'object'",
                        name="ck_ja_revs_command_json"),
        CheckConstraint("jsonb_typeof(snapshot_json::jsonb) = 'object'",
                        name="ck_ja_revs_snapshot_json"),
    )


class JobAuthoringProposalRow(Base):
    __tablename__ = "job_authoring_proposals"

    proposal_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    base_revision_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    base_revision_hash: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_state_version: Mapped[int] = mapped_column(BigInteger, nullable=False)
    evidence_state_hash: Mapped[str] = mapped_column(Text, nullable=False)
    source_kind: Mapped[str] = mapped_column(Text, nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    proposal_schema_id: Mapped[str] = mapped_column(Text, nullable=False)
    proposal_json: Mapped[str] = mapped_column(Text, nullable=False)
    proposal_hash: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    decision_command_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True)
    decision_schema_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    decision_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    decision_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_revision_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True)
    stale_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("tenant_id", "proposal_id", name="uq_ja_props_tenant_proposal"),
        ForeignKeyConstraint(
            ["tenant_id", "document_id"],
            ["job_authoring_documents.tenant_id", "job_authoring_documents.document_id"],
            name="fk_ja_props_document", ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ["tenant_id", "base_revision_id"],
            ["job_authoring_revisions.tenant_id", "job_authoring_revisions.revision_id"],
            name="fk_ja_props_base_revision", ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ["tenant_id", "result_revision_id"],
            ["job_authoring_revisions.tenant_id", "job_authoring_revisions.revision_id"],
            name="fk_ja_props_result_revision", ondelete="RESTRICT"),
        CheckConstraint("source_kind IN ('scripted','llm_operation')",
                        name="ck_ja_props_source"),
        CheckConstraint("evidence_state_version >= 0", name="ck_ja_props_state_version"),
        CheckConstraint(f"base_revision_hash ~ '{_SHA256}'", name="ck_ja_props_base_hash"),
        CheckConstraint(f"evidence_state_hash ~ '{_SHA256}'", name="ck_ja_props_state_hash"),
        CheckConstraint(f"proposal_hash ~ '{_SHA256}'", name="ck_ja_props_payload_hash"),
        CheckConstraint("jsonb_typeof(proposal_json::jsonb) = 'object'",
                        name="ck_ja_props_payload_json"),
        CheckConstraint(
            "decision_json IS NULL OR jsonb_typeof(decision_json::jsonb) = 'object'",
            name="ck_ja_props_decision_json"),
        CheckConstraint(
            "stale_reason IS NULL OR stale_reason IN "
            "('document_revision_advanced','base_revision_changed',"
            "'evidence_basis_changed')",
            name="ck_ja_props_stale_reason"),
        CheckConstraint(
            "CASE status "
            "WHEN 'pending' THEN decision_command_id IS NULL AND decision_schema_id IS NULL "
            "AND decision_json IS NULL AND decision_hash IS NULL "
            "AND result_revision_id IS NULL AND stale_reason IS NULL AND resolved_at IS NULL "
            "WHEN 'accepted' THEN decision_command_id IS NOT NULL "
            "AND decision_schema_id IS NOT NULL AND decision_json IS NOT NULL "
            "AND decision_hash IS NOT NULL AND result_revision_id IS NOT NULL "
            "AND resolved_at IS NOT NULL AND stale_reason IS NULL "
            "WHEN 'edited' THEN decision_command_id IS NOT NULL "
            "AND decision_schema_id IS NOT NULL AND decision_json IS NOT NULL "
            "AND decision_hash IS NOT NULL AND result_revision_id IS NOT NULL "
            "AND resolved_at IS NOT NULL AND stale_reason IS NULL "
            "WHEN 'rejected' THEN decision_command_id IS NOT NULL "
            "AND decision_schema_id IS NOT NULL AND decision_json IS NOT NULL "
            "AND decision_hash IS NOT NULL AND result_revision_id IS NULL "
            "AND stale_reason IS NULL AND resolved_at IS NOT NULL "
            "WHEN 'stale' THEN decision_command_id IS NULL AND decision_schema_id IS NULL "
            "AND decision_json IS NULL AND decision_hash IS NULL "
            "AND result_revision_id IS NULL AND stale_reason IS NOT NULL "
            "AND resolved_at IS NOT NULL "
            "ELSE false END",
            name="ck_ja_props_lifecycle"),
        CheckConstraint(
            "updated_at >= created_at "
            "AND (resolved_at IS NULL OR resolved_at >= created_at)",
            name="ck_ja_props_time_order"),
        Index("uq_ja_props_decision_command", "tenant_id", "decision_command_id",
              unique=True, postgresql_where=text("decision_command_id IS NOT NULL")),
        Index("ix_ja_props_document_status", "tenant_id", "document_id", "status",
              "created_at", "proposal_id"),
    )
