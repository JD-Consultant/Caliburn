"""Persist Current JD OPKS items and their independent proposals.

Revision ID: 0014
Revises: 0013
Create Date: 2026-08-01

Two typed JSON payload tables are sufficient for the first slice.  This does
not add per-kind tables, reference join tables, revisions, or history.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID


revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None

_ENTITY_KINDS = "entity_kind IN ('output','indicator','knowledge','skill','attitude')"
_PROPOSAL_ACTIONS = "action IN ('add','revise','remove')"
_PROPOSAL_STATUSES = (
    "status IN ('pending','deferred','accepted','edited','rejected','stale')"
)
_PROPOSAL_LIFECYCLE = (
    "(status IN ('pending','deferred') AND resolved_at IS NULL) OR "
    "(status IN ('accepted','edited','rejected','stale') AND resolved_at IS NOT NULL)"
)


def upgrade() -> None:
    op.create_table(
        "job_analysis_opks_items",
        sa.Column("document_id", UUID(as_uuid=True), nullable=False),
        sa.Column("entity_id", sa.Text(), nullable=False),
        sa.Column("entity_kind", sa.Text(), nullable=False),
        sa.Column("item_schema_id", sa.Text(), nullable=False),
        sa.Column("item_payload", JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint(
            "document_id",
            "entity_id",
            name="ja2_pk_opks_items",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["job_analysis_documents.document_id"],
            name="ja2_fk_opks_items_document",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint("btrim(entity_id) <> ''", name="ja2_ck_opks_items_id"),
        sa.CheckConstraint(_ENTITY_KINDS, name="ja2_ck_opks_items_kind"),
        sa.CheckConstraint(
            "btrim(item_schema_id) <> ''",
            name="ja2_ck_opks_items_schema",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(item_payload) = 'object'",
            name="ja2_ck_opks_items_payload",
        ),
        sa.CheckConstraint(
            "updated_at >= created_at",
            name="ja2_ck_opks_items_time_order",
        ),
    )
    op.create_index(
        "ja2_ix_opks_items_document_created",
        "job_analysis_opks_items",
        ["document_id", "created_at", "entity_id"],
    )

    op.create_table(
        "job_analysis_opks_proposals",
        sa.Column("document_id", UUID(as_uuid=True), nullable=False),
        sa.Column("proposal_id", sa.Text(), nullable=False),
        sa.Column("operation_id", sa.Text(), nullable=False),
        sa.Column("entity_id", sa.Text(), nullable=False),
        sa.Column("entity_kind", sa.Text(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("base_authority_generation", sa.BigInteger(), nullable=False),
        sa.Column("proposal_schema_id", sa.Text(), nullable=False),
        sa.Column("proposal_payload", JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint(
            "document_id",
            "proposal_id",
            name="ja2_pk_opks_proposals",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["job_analysis_documents.document_id"],
            name="ja2_fk_opks_proposals_document",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "btrim(proposal_id) <> ''",
            name="ja2_ck_opks_proposals_id",
        ),
        sa.CheckConstraint(
            "btrim(operation_id) <> ''",
            name="ja2_ck_opks_proposals_operation_id",
        ),
        sa.CheckConstraint(
            "btrim(entity_id) <> ''",
            name="ja2_ck_opks_proposals_entity_id",
        ),
        sa.CheckConstraint(_ENTITY_KINDS, name="ja2_ck_opks_proposals_kind"),
        sa.CheckConstraint(
            _PROPOSAL_ACTIONS,
            name="ja2_ck_opks_proposals_action",
        ),
        sa.CheckConstraint(
            _PROPOSAL_STATUSES,
            name="ja2_ck_opks_proposals_status",
        ),
        sa.CheckConstraint(
            "base_authority_generation >= 0",
            name="ja2_ck_opks_proposals_generation",
        ),
        sa.CheckConstraint(
            "btrim(proposal_schema_id) <> ''",
            name="ja2_ck_opks_proposals_schema",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(proposal_payload) = 'object'",
            name="ja2_ck_opks_proposals_payload",
        ),
        sa.CheckConstraint(
            _PROPOSAL_LIFECYCLE,
            name="ja2_ck_opks_proposals_lifecycle",
        ),
    )
    op.create_index(
        "ja2_ix_opks_proposals_document_status",
        "job_analysis_opks_proposals",
        ["document_id", "status", "created_at", "proposal_id"],
    )

    op.drop_constraint(
        "ja2_ck_journal_kind",
        "job_analysis_journal",
        type_="check",
    )
    op.create_check_constraint(
        "ja2_ck_journal_kind",
        "job_analysis_journal",
        "kind IN ('consultant_opening','employee_turn','direct_edit',"
        "'proposal_decision','opks_generation')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ja2_ck_journal_kind",
        "job_analysis_journal",
        type_="check",
    )
    op.create_check_constraint(
        "ja2_ck_journal_kind",
        "job_analysis_journal",
        "kind IN ('consultant_opening','employee_turn','direct_edit','proposal_decision')",
    )
    op.drop_table("job_analysis_opks_proposals")
    op.drop_table("job_analysis_opks_items")
