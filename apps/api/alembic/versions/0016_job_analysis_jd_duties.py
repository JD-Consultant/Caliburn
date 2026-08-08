"""Persist employee-authored Current JD Duties and Task assignment fields.

Revision ID: 0016
Revises: 0015
Create Date: 2026-08-09

Existing Tasks remain unassigned.  The composite FK is deferred so the shared
replace-all authority seam can update Duties and Tasks atomically.
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
        sa.PrimaryKeyConstraint(
            "document_id",
            "duty_id",
            name="ja2_pk_jd_duties",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["job_analysis_documents.document_id"],
            name="ja2_fk_jd_duties_document",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "document_id",
            "display_order",
            name="ja2_uq_jd_duties_order",
        ),
        sa.CheckConstraint("btrim(duty_id) <> ''", name="ja2_ck_jd_duties_id"),
        sa.CheckConstraint(
            "btrim(statement) <> ''",
            name="ja2_ck_jd_duties_statement",
        ),
        sa.CheckConstraint(
            "display_order >= 0",
            name="ja2_ck_jd_duties_display_order",
        ),
        sa.CheckConstraint(
            "updated_at >= created_at",
            name="ja2_ck_jd_duties_time_order",
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
    op.create_foreign_key(
        "ja2_fk_jd_tasks_duty",
        "job_analysis_jd_tasks",
        "job_analysis_jd_duties",
        ["document_id", "duty_id"],
        ["document_id", "duty_id"],
        deferrable=True,
        initially="DEFERRED",
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
        "ja2_ck_jd_tasks_competency_level",
        "job_analysis_jd_tasks",
        type_="check",
    )
    op.drop_constraint(
        "ja2_ck_jd_tasks_duty_id",
        "job_analysis_jd_tasks",
        type_="check",
    )
    op.drop_constraint(
        "ja2_fk_jd_tasks_duty",
        "job_analysis_jd_tasks",
        type_="foreignkey",
    )
    op.drop_column("job_analysis_jd_tasks", "competency_level")
    op.drop_column("job_analysis_jd_tasks", "duty_id")
    op.drop_table("job_analysis_jd_duties")
