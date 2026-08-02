"""job analysis local Current State persistence

Revision ID: 0012
Revises: 0011
Create Date: 2026-07-29

Greenfield tables only: no old-row migration, dual write, tenant seam,
revision history, trigger, RLS, or event-sourced replay.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID


revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None

_PROPOSAL_STATUSES = (
    "status IN ('pending','deferred','accepted','edited','rejected',"
    "'revision_requested','stale')"
)
_PROPOSAL_LIFECYCLE = (
    "(status IN ('pending','deferred') AND resolved_at IS NULL) OR "
    "(status IN ('accepted','edited','rejected','revision_requested','stale') "
    "AND resolved_at IS NOT NULL)"
)


def upgrade() -> None:
    op.create_table(
        "job_analysis_documents",
        sa.Column("document_id", UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("work_model_schema_id", sa.Text(), nullable=False),
        sa.Column("work_model_json", JSONB(), nullable=False),
        sa.Column("active_question_json", JSONB(), nullable=True),
        sa.Column("authority_generation", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("document_id", name="ja2_pk_documents"),
        sa.CheckConstraint("btrim(title) <> ''", name="ja2_ck_documents_title"),
        sa.CheckConstraint(
            "btrim(work_model_schema_id) <> ''",
            name="ja2_ck_documents_work_model_schema",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(work_model_json) = 'object'",
            name="ja2_ck_documents_work_model_json",
        ),
        sa.CheckConstraint(
            "active_question_json IS NULL "
            "OR jsonb_typeof(active_question_json) = 'object'",
            name="ja2_ck_documents_active_question_json",
        ),
        sa.CheckConstraint(
            "authority_generation >= 0",
            name="ja2_ck_documents_generation",
        ),
        sa.CheckConstraint(
            "updated_at >= created_at",
            name="ja2_ck_documents_time_order",
        ),
    )
    op.create_index(
        "ja2_ix_documents_updated",
        "job_analysis_documents",
        [sa.text("updated_at DESC"), "document_id"],
    )

    op.create_table(
        "job_analysis_jd_tasks",
        sa.Column("document_id", UUID(as_uuid=True), nullable=False),
        sa.Column("task_id", sa.Text(), nullable=False),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("purpose_result", sa.Text(), nullable=True),
        sa.Column("context", sa.Text(), nullable=True),
        sa.Column("frequency_text", sa.Text(), nullable=True),
        sa.Column("responsibility_role", sa.Text(), nullable=True),
        sa.Column("enablers_json", JSONB(), nullable=False),
        sa.Column("display_order", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint(
            "document_id",
            "task_id",
            name="ja2_pk_jd_tasks",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["job_analysis_documents.document_id"],
            name="ja2_fk_jd_tasks_document",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "document_id",
            "display_order",
            name="ja2_uq_jd_tasks_order",
        ),
        sa.CheckConstraint(
            "btrim(task_id) <> ''",
            name="ja2_ck_jd_tasks_task_id",
        ),
        sa.CheckConstraint(
            "btrim(statement) <> ''",
            name="ja2_ck_jd_tasks_statement",
        ),
        sa.CheckConstraint(
            "responsibility_role IS NULL "
            "OR responsibility_role IN ('primary','shared','assist')",
            name="ja2_ck_jd_tasks_role",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(enablers_json) = 'array'",
            name="ja2_ck_jd_tasks_enablers_json",
        ),
        sa.CheckConstraint(
            "display_order >= 0",
            name="ja2_ck_jd_tasks_display_order",
        ),
        sa.CheckConstraint(
            "updated_at >= created_at",
            name="ja2_ck_jd_tasks_time_order",
        ),
    )

    op.create_table(
        "job_analysis_proposals",
        sa.Column("document_id", UUID(as_uuid=True), nullable=False),
        sa.Column("proposal_id", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("base_authority_generation", sa.BigInteger(), nullable=False),
        sa.Column("proposal_schema_id", sa.Text(), nullable=False),
        sa.Column("proposal_payload", JSONB(), nullable=False),
        sa.Column("caused_by_decision_id", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint(
            "document_id",
            "proposal_id",
            name="ja2_pk_proposals",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["job_analysis_documents.document_id"],
            name="ja2_fk_proposals_document",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "btrim(proposal_id) <> ''",
            name="ja2_ck_proposals_id",
        ),
        sa.CheckConstraint(_PROPOSAL_STATUSES, name="ja2_ck_proposals_status"),
        sa.CheckConstraint(
            "base_authority_generation >= 0",
            name="ja2_ck_proposals_generation",
        ),
        sa.CheckConstraint(
            "btrim(proposal_schema_id) <> ''",
            name="ja2_ck_proposals_schema",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(proposal_payload) = 'object'",
            name="ja2_ck_proposals_payload",
        ),
        sa.CheckConstraint(
            _PROPOSAL_LIFECYCLE,
            name="ja2_ck_proposals_lifecycle",
        ),
    )
    op.create_index(
        "ja2_ix_proposals_document_status",
        "job_analysis_proposals",
        ["document_id", "status", "created_at", "proposal_id"],
    )
    op.create_index(
        "ja2_uq_proposals_replacement",
        "job_analysis_proposals",
        ["document_id", "caused_by_decision_id"],
        unique=True,
        postgresql_where=sa.text("caused_by_decision_id IS NOT NULL"),
    )

    op.create_table(
        "job_analysis_journal",
        sa.Column(
            "journal_sequence",
            sa.BigInteger(),
            sa.Identity(),
            nullable=False,
        ),
        sa.Column("document_id", UUID(as_uuid=True), nullable=False),
        sa.Column("entry_id", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("payload_schema_id", sa.Text(), nullable=False),
        sa.Column("payload", JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint(
            "journal_sequence",
            name="ja2_pk_journal",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["job_analysis_documents.document_id"],
            name="ja2_fk_journal_document",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "document_id",
            "entry_id",
            name="ja2_uq_journal_entry",
        ),
        sa.CheckConstraint(
            "btrim(entry_id) <> ''",
            name="ja2_ck_journal_entry_id",
        ),
        sa.CheckConstraint(
            "kind IN ('employee_turn','direct_edit','proposal_decision')",
            name="ja2_ck_journal_kind",
        ),
        sa.CheckConstraint(
            "btrim(payload_schema_id) <> ''",
            name="ja2_ck_journal_schema",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(payload) = 'object'",
            name="ja2_ck_journal_payload",
        ),
    )
    op.create_index(
        "ja2_ix_journal_document_sequence",
        "job_analysis_journal",
        ["document_id", sa.text("journal_sequence DESC")],
    )


def downgrade() -> None:
    op.drop_table("job_analysis_journal")
    op.drop_table("job_analysis_proposals")
    op.drop_table("job_analysis_jd_tasks")
    op.drop_table("job_analysis_documents")

