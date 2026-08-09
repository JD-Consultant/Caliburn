"""Persist employee OPKS display order with a deterministic legacy backfill.

The order is scoped to one document and one OPKS entity kind.  Existing rows
are ranked by the repository's former read order, ``created_at, entity_id``;
ties therefore receive the same stable order they had before this column.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "job_analysis_opks_items",
        sa.Column("display_order", sa.BigInteger(), nullable=True),
    )
    op.execute(
        sa.text(
            """
            WITH ranked AS (
                SELECT
                    document_id,
                    entity_id,
                    row_number() OVER (
                        PARTITION BY document_id, entity_kind
                        ORDER BY created_at, entity_id
                    ) - 1 AS display_order
                FROM job_analysis_opks_items
            )
            UPDATE job_analysis_opks_items AS item
            SET display_order = ranked.display_order
            FROM ranked
            WHERE item.document_id = ranked.document_id
              AND item.entity_id = ranked.entity_id
            """
        )
    )
    op.alter_column(
        "job_analysis_opks_items",
        "display_order",
        existing_type=sa.BigInteger(),
        nullable=False,
    )
    op.create_unique_constraint(
        "ja2_uq_opks_items_kind_order",
        "job_analysis_opks_items",
        ["document_id", "entity_kind", "display_order"],
    )
    op.create_check_constraint(
        "ja2_ck_opks_items_display_order",
        "job_analysis_opks_items",
        "display_order >= 0",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ja2_ck_opks_items_display_order",
        "job_analysis_opks_items",
        type_="check",
    )
    op.drop_constraint(
        "ja2_uq_opks_items_kind_order",
        "job_analysis_opks_items",
        type_="unique",
    )
    op.drop_column("job_analysis_opks_items", "display_order")
