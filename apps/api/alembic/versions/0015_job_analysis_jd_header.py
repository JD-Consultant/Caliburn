"""Persist the Current JD Header on the existing document authority row.

Revision ID: 0015
Revises: 0014
Create Date: 2026-08-09
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB


revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "job_analysis_documents",
        sa.Column("jd_header_schema_id", sa.Text(), nullable=True),
    )
    op.add_column(
        "job_analysis_documents",
        sa.Column("jd_header_json", JSONB(), nullable=True),
    )
    op.execute(
        "UPDATE job_analysis_documents "
        "SET jd_header_schema_id = 'job-analysis-jd-header/1', "
        "jd_header_json = '{}'::jsonb"
    )
    op.alter_column(
        "job_analysis_documents",
        "jd_header_schema_id",
        nullable=False,
    )
    op.alter_column(
        "job_analysis_documents",
        "jd_header_json",
        nullable=False,
    )


def downgrade() -> None:
    op.drop_column("job_analysis_documents", "jd_header_json")
    op.drop_column("job_analysis_documents", "jd_header_schema_id")
