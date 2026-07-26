"""job authoring core: documents, immutable revisions, proposals

Revision ID: 0011
Revises: 0010
Create Date: 2026-07-23

Three canonical authoring tables (plan §10). Head pointer is application-enforced
(no circular FK); revisions are immutable; proposals move pending -> one terminal
status under a guard trigger. Downgrade DROPS the three authoring tables and all
their data (pre-production/dev/test only); it does not touch 0010/vNext data.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None

_SHA256 = r"^sha256:[0-9a-f]{64}$"

_REVISION_SOURCE = (
    "source_kind IN ('initial','employee_direct_edit',"
    "'ai_proposal_accept','employee_proposal_edit')"
)
_NUMBER_PARENT = (
    "(revision_number = 0 AND source_kind = 'initial' "
    "AND parent_revision_id IS NULL) "
    "OR (revision_number > 0 AND source_kind <> 'initial' "
    "AND parent_revision_id IS NOT NULL)"
)
_LIFECYCLE = """
CASE status
  WHEN 'pending' THEN
    decision_command_id IS NULL AND decision_schema_id IS NULL
    AND decision_json IS NULL AND decision_hash IS NULL
    AND result_revision_id IS NULL AND stale_reason IS NULL AND resolved_at IS NULL
  WHEN 'accepted' THEN
    decision_command_id IS NOT NULL AND decision_schema_id IS NOT NULL
    AND decision_json IS NOT NULL AND decision_hash IS NOT NULL
    AND result_revision_id IS NOT NULL AND resolved_at IS NOT NULL
    AND stale_reason IS NULL
  WHEN 'edited' THEN
    decision_command_id IS NOT NULL AND decision_schema_id IS NOT NULL
    AND decision_json IS NOT NULL AND decision_hash IS NOT NULL
    AND result_revision_id IS NOT NULL AND resolved_at IS NOT NULL
    AND stale_reason IS NULL
  WHEN 'rejected' THEN
    decision_command_id IS NOT NULL AND decision_schema_id IS NOT NULL
    AND decision_json IS NOT NULL AND decision_hash IS NOT NULL
    AND result_revision_id IS NULL AND stale_reason IS NULL AND resolved_at IS NOT NULL
  WHEN 'stale' THEN
    decision_command_id IS NULL AND decision_schema_id IS NULL
    AND decision_json IS NULL AND decision_hash IS NULL
    AND result_revision_id IS NULL AND stale_reason IS NOT NULL AND resolved_at IS NOT NULL
  ELSE false
END
"""


def upgrade() -> None:
    op.create_table(
        "job_authoring_documents",
        sa.Column("document_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", UUID(as_uuid=True), nullable=False),
        sa.Column("head_revision_id", UUID(as_uuid=True), nullable=False),
        sa.Column("head_revision_number", sa.BigInteger(), nullable=False),
        sa.Column("head_revision_hash", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "document_id",
                            name="uq_ja_docs_tenant_document"),
        sa.UniqueConstraint("tenant_id", "session_id",
                            name="uq_ja_docs_tenant_session"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "session_id"],
            ["interview_vnext_sessions.tenant_id",
             "interview_vnext_sessions.session_id"],
            name="fk_ja_docs_session", ondelete="RESTRICT"),
        sa.CheckConstraint("head_revision_number >= 0", name="ck_ja_docs_head_number"),
        sa.CheckConstraint(f"head_revision_hash ~ '{_SHA256}'",
                           name="ck_ja_docs_head_hash"),
        sa.CheckConstraint("updated_at >= created_at", name="ck_ja_docs_time_order"),
    )
    op.create_index("ix_ja_docs_tenant_updated", "job_authoring_documents",
                    ["tenant_id", sa.text("updated_at DESC"), "document_id"])

    op.create_table(
        "job_authoring_revisions",
        sa.Column("revision_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", UUID(as_uuid=True), nullable=False),
        sa.Column("revision_number", sa.BigInteger(), nullable=False),
        sa.Column("parent_revision_id", UUID(as_uuid=True), nullable=True),
        sa.Column("source_kind", sa.Text(), nullable=False),
        sa.Column("command_schema_id", sa.Text(), nullable=False),
        sa.Column("command_id", UUID(as_uuid=True), nullable=False),
        sa.Column("command_json", sa.Text(), nullable=False),
        sa.Column("command_hash", sa.Text(), nullable=False),
        sa.Column("snapshot_schema_id", sa.Text(), nullable=False),
        sa.Column("snapshot_json", sa.Text(), nullable=False),
        sa.Column("snapshot_hash", sa.Text(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "revision_id",
                            name="uq_ja_revs_tenant_revision"),
        sa.UniqueConstraint("tenant_id", "document_id", "revision_number",
                            name="uq_ja_revs_document_number"),
        sa.UniqueConstraint("tenant_id", "command_id",
                            name="uq_ja_revs_tenant_command"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "document_id"],
            ["job_authoring_documents.tenant_id",
             "job_authoring_documents.document_id"],
            name="fk_ja_revs_document", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "parent_revision_id"],
            ["job_authoring_revisions.tenant_id",
             "job_authoring_revisions.revision_id"],
            name="fk_ja_revs_parent", ondelete="RESTRICT"),
        sa.CheckConstraint(_NUMBER_PARENT, name="ck_ja_revs_number_parent"),
        sa.CheckConstraint(_REVISION_SOURCE, name="ck_ja_revs_source"),
        sa.CheckConstraint(f"command_hash ~ '{_SHA256}'",
                           name="ck_ja_revs_command_hash"),
        sa.CheckConstraint(f"snapshot_hash ~ '{_SHA256}'",
                           name="ck_ja_revs_snapshot_hash"),
        sa.CheckConstraint("jsonb_typeof(command_json::jsonb) = 'object'",
                           name="ck_ja_revs_command_json"),
        sa.CheckConstraint("jsonb_typeof(snapshot_json::jsonb) = 'object'",
                           name="ck_ja_revs_snapshot_json"),
    )

    op.create_table(
        "job_authoring_proposals",
        sa.Column("proposal_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", UUID(as_uuid=True), nullable=False),
        sa.Column("base_revision_id", UUID(as_uuid=True), nullable=False),
        sa.Column("base_revision_hash", sa.Text(), nullable=False),
        sa.Column("evidence_state_version", sa.BigInteger(), nullable=False),
        sa.Column("evidence_state_hash", sa.Text(), nullable=False),
        sa.Column("source_kind", sa.Text(), nullable=False),
        sa.Column("source_id", UUID(as_uuid=True), nullable=False),
        sa.Column("proposal_schema_id", sa.Text(), nullable=False),
        sa.Column("proposal_json", sa.Text(), nullable=False),
        sa.Column("proposal_hash", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("decision_command_id", UUID(as_uuid=True), nullable=True),
        sa.Column("decision_schema_id", sa.Text(), nullable=True),
        sa.Column("decision_json", sa.Text(), nullable=True),
        sa.Column("decision_hash", sa.Text(), nullable=True),
        sa.Column("result_revision_id", UUID(as_uuid=True), nullable=True),
        sa.Column("stale_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "proposal_id",
                            name="uq_ja_props_tenant_proposal"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "document_id"],
            ["job_authoring_documents.tenant_id",
             "job_authoring_documents.document_id"],
            name="fk_ja_props_document", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "base_revision_id"],
            ["job_authoring_revisions.tenant_id",
             "job_authoring_revisions.revision_id"],
            name="fk_ja_props_base_revision", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "result_revision_id"],
            ["job_authoring_revisions.tenant_id",
             "job_authoring_revisions.revision_id"],
            name="fk_ja_props_result_revision", ondelete="RESTRICT"),
        sa.CheckConstraint("source_kind IN ('scripted','llm_operation')",
                           name="ck_ja_props_source"),
        sa.CheckConstraint("evidence_state_version >= 0",
                           name="ck_ja_props_state_version"),
        sa.CheckConstraint(f"base_revision_hash ~ '{_SHA256}'",
                           name="ck_ja_props_base_hash"),
        sa.CheckConstraint(f"evidence_state_hash ~ '{_SHA256}'",
                           name="ck_ja_props_state_hash"),
        sa.CheckConstraint(f"proposal_hash ~ '{_SHA256}'",
                           name="ck_ja_props_payload_hash"),
        sa.CheckConstraint("jsonb_typeof(proposal_json::jsonb) = 'object'",
                           name="ck_ja_props_payload_json"),
        sa.CheckConstraint(
            "decision_json IS NULL OR jsonb_typeof(decision_json::jsonb) = 'object'",
            name="ck_ja_props_decision_json"),
        sa.CheckConstraint(
            "stale_reason IS NULL OR stale_reason IN "
            "('document_revision_advanced','base_revision_changed',"
            "'evidence_basis_changed')",
            name="ck_ja_props_stale_reason"),
        sa.CheckConstraint(_LIFECYCLE, name="ck_ja_props_lifecycle"),
        sa.CheckConstraint(
            "updated_at >= created_at "
            "AND (resolved_at IS NULL OR resolved_at >= created_at)",
            name="ck_ja_props_time_order"),
    )
    op.create_index(
        "uq_ja_props_decision_command", "job_authoring_proposals",
        ["tenant_id", "decision_command_id"], unique=True,
        postgresql_where=sa.text("decision_command_id IS NOT NULL"))
    op.create_index(
        "ix_ja_props_document_status", "job_authoring_proposals",
        ["tenant_id", "document_id", "status", "created_at", "proposal_id"])

    # Immutable revisions.
    op.execute("""
        CREATE FUNCTION ja_revs_reject_update_fn() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'job_authoring_revisions rows are immutable';
        END $$;
    """)
    op.execute("""
        CREATE TRIGGER ja_revs_reject_update
        BEFORE UPDATE ON job_authoring_revisions
        FOR EACH ROW EXECUTE FUNCTION ja_revs_reject_update_fn();
    """)

    # Proposal guard: immutable identity/payload; only pending -> one terminal.
    op.execute("""
        CREATE FUNCTION ja_props_guard_update_fn() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.proposal_id IS DISTINCT FROM OLD.proposal_id
               OR NEW.tenant_id IS DISTINCT FROM OLD.tenant_id
               OR NEW.document_id IS DISTINCT FROM OLD.document_id
               OR NEW.base_revision_id IS DISTINCT FROM OLD.base_revision_id
               OR NEW.base_revision_hash IS DISTINCT FROM OLD.base_revision_hash
               OR NEW.evidence_state_version IS DISTINCT FROM OLD.evidence_state_version
               OR NEW.evidence_state_hash IS DISTINCT FROM OLD.evidence_state_hash
               OR NEW.source_kind IS DISTINCT FROM OLD.source_kind
               OR NEW.source_id IS DISTINCT FROM OLD.source_id
               OR NEW.proposal_schema_id IS DISTINCT FROM OLD.proposal_schema_id
               OR NEW.proposal_json IS DISTINCT FROM OLD.proposal_json
               OR NEW.proposal_hash IS DISTINCT FROM OLD.proposal_hash
               OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
                RAISE EXCEPTION
                    'job_authoring_proposals identity/payload is immutable';
            END IF;
            IF NOT (OLD.status = 'pending'
                    AND NEW.status IN ('accepted','edited','rejected','stale')) THEN
                RAISE EXCEPTION
                    'illegal job_authoring_proposals transition % -> %',
                    OLD.status, NEW.status;
            END IF;
            RETURN NEW;
        END $$;
    """)
    op.execute("""
        CREATE TRIGGER ja_props_guard_update
        BEFORE UPDATE ON job_authoring_proposals
        FOR EACH ROW EXECUTE FUNCTION ja_props_guard_update_fn();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS ja_props_guard_update ON job_authoring_proposals")
    op.execute("DROP FUNCTION IF EXISTS ja_props_guard_update_fn()")
    op.drop_table("job_authoring_proposals")
    op.execute("DROP TRIGGER IF EXISTS ja_revs_reject_update ON job_authoring_revisions")
    op.execute("DROP FUNCTION IF EXISTS ja_revs_reject_update_fn()")
    op.drop_table("job_authoring_revisions")
    op.drop_table("job_authoring_documents")
