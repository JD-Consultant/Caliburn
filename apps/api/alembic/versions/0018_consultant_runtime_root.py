"""Fresh current-only root for the durable consultant document catalog."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID


revision = "0018"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "consultant_documents",
        sa.Column("document_id", UUID(as_uuid=True), nullable=False),
        sa.Column("thread_id", UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("document_id", name="consultant_pk_documents"),
        sa.UniqueConstraint("thread_id", name="consultant_uq_documents_thread"),
        sa.CheckConstraint(
            "btrim(title) <> ''",
            name="consultant_ck_documents_title",
        ),
        sa.CheckConstraint(
            "updated_at >= created_at",
            name="consultant_ck_documents_time_order",
        ),
        sa.CheckConstraint(
            "deleted_at IS NULL OR deleted_at >= created_at",
            name="consultant_ck_documents_deleted_time",
        ),
    )
    op.create_index(
        "consultant_ix_documents_updated",
        "consultant_documents",
        [sa.text("updated_at DESC"), "document_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "consultant_ix_documents_updated",
        table_name="consultant_documents",
    )
    op.drop_table("consultant_documents")
