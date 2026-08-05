"""Add 主要職責 (Duty) and the per-Task competency level.

Revision ID: 0016
Revises: 0015
Create Date: 2026-08-05

`job_analysis_jd_duties` mirrors `job_analysis_jd_tasks`: same PK shape, same
document-scoped unique `display_order`, same CASCADE from the document.

`jd_tasks.duty_id` deliberately has **no foreign key**, matching how OPKS
`task_refs` already work: referential integrity for these child relationships
lives in `JobAnalysisState`, which rejects a Task pointing at a Duty that does
not exist, and a corrupt row therefore fails closed on read instead of loading.
A real FK would also interact badly with the delete-then-insert `replace()`
pattern — `ON DELETE SET NULL` would silently blank every Task's duty during
each duties replace, which is exactly the silent data loss this slice is trying
to avoid.

Existing rows get no Duty. ADR 0052 decision 13 forbids synthesising a fake T1,
so an untouched document keeps every Task unassigned and readiness says so.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID


revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "job_analysis_jd_duties",
        sa.Column("document_id", UUID(as_uuid=True), nullable=False),
        sa.Column("duty_id", sa.Text(), nullable=False),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("display_order", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("document_id", "duty_id", name="ja2_pk_jd_duties"),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["job_analysis_documents.document_id"],
            name="ja2_fk_jd_duties_document",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "document_id", "display_order", name="ja2_uq_jd_duties_order"
        ),
        sa.CheckConstraint("btrim(duty_id) <> ''", name="ja2_ck_jd_duties_duty_id"),
        sa.CheckConstraint(
            "btrim(statement) <> ''", name="ja2_ck_jd_duties_statement"
        ),
        sa.CheckConstraint(
            "display_order >= 0", name="ja2_ck_jd_duties_display_order"
        ),
        sa.CheckConstraint(
            "updated_at >= created_at", name="ja2_ck_jd_duties_time_order"
        ),
    )

    op.add_column(
        "job_analysis_jd_tasks",
        sa.Column("duty_id", sa.Text(), nullable=True),
    )
    op.add_column(
        "job_analysis_jd_tasks",
        sa.Column("competency_level", sa.BigInteger(), nullable=True),
    )
    op.create_check_constraint(
        "ja2_ck_jd_tasks_duty_id",
        "job_analysis_jd_tasks",
        "duty_id IS NULL OR btrim(duty_id) <> ''",
    )
    op.create_check_constraint(
        "ja2_ck_jd_tasks_competency_level",
        "job_analysis_jd_tasks",
        "competency_level IS NULL OR competency_level BETWEEN 1 AND 6",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ja2_ck_jd_tasks_competency_level", "job_analysis_jd_tasks", type_="check"
    )
    op.drop_constraint(
        "ja2_ck_jd_tasks_duty_id", "job_analysis_jd_tasks", type_="check"
    )
    op.drop_column("job_analysis_jd_tasks", "competency_level")
    op.drop_column("job_analysis_jd_tasks", "duty_id")
    op.drop_table("job_analysis_jd_duties")
