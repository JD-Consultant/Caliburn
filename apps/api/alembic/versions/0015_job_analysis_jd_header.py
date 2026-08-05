"""Carry the iCAP header on the Current JD authority row.

Revision ID: 0015
Revises: 0014
Create Date: 2026-08-04

Two columns on ``job_analysis_documents`` beside ``work_model_*``.  The header
is Current JD authority (ADR 0053 decision 3), so it belongs on the row that
already carries ``authority_generation``: the CAS in ``update_authority()``
then covers the header for free, with no second table and no extra round trip.

Existing rows are backfilled with an empty header, which is exactly what an
untouched document should read as.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB


revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None

_SCHEMA_ID = "job-analysis-jd-header/1"


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
        sa.text(
            "UPDATE job_analysis_documents "
            "SET jd_header_schema_id = :schema_id, jd_header_json = :payload "
            "WHERE jd_header_schema_id IS NULL"
        ).bindparams(
            sa.bindparam("schema_id", value=_SCHEMA_ID),
            sa.bindparam("payload", value="{}", type_=JSONB()),
        )
    )
    op.alter_column("job_analysis_documents", "jd_header_schema_id", nullable=False)
    op.alter_column("job_analysis_documents", "jd_header_json", nullable=False)
    op.create_check_constraint(
        "ja2_ck_documents_jd_header_schema",
        "job_analysis_documents",
        "btrim(jd_header_schema_id) <> ''",
    )
    op.create_check_constraint(
        "ja2_ck_documents_jd_header_json",
        "job_analysis_documents",
        "jsonb_typeof(jd_header_json) = 'object'",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ja2_ck_documents_jd_header_json", "job_analysis_documents", type_="check"
    )
    op.drop_constraint(
        "ja2_ck_documents_jd_header_schema", "job_analysis_documents", type_="check"
    )
    op.drop_column("job_analysis_documents", "jd_header_json")
    op.drop_column("job_analysis_documents", "jd_header_schema_id")
