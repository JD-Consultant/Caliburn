"""Give OPKS items an employee-controlled display order.

Revision ID: 0017
Revises: 0016
Create Date: 2026-08-06

匯出的 `O1.1.1`／`K01` 位置碼由排序推出（ADR 0058 決定 3／5）。在此之前 OPKS 的順序落在
`(created_at, entity_id)`——決定性，但員工無法調整，而 Duty／Task 都有上下移按鈕。

**回填刻意等於 migration 前的讀取順序**：依 `(document_id, entity_kind)` 分組，
按 `(created_at, entity_id)` 由 0 起編號。既有文件升級後的 OPKS 呈現順序**逐項不變**。

唯一性範圍是 `(document_id, entity_kind)`，不是 Task：`O{i}.{j}.{k}` 的 `{k}` 在該 Task 內
重新從 1 編號，比照 `jd_tasks.display_order` 文件層唯一而 `T{i}.{j}` 在 Duty 內重編。
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
        """
        UPDATE job_analysis_opks_items AS target
        SET display_order = ranked.position
        FROM (
            SELECT
                document_id,
                entity_id,
                ROW_NUMBER() OVER (
                    PARTITION BY document_id, entity_kind
                    ORDER BY created_at, entity_id
                ) - 1 AS position
            FROM job_analysis_opks_items
        ) AS ranked
        WHERE target.document_id = ranked.document_id
          AND target.entity_id = ranked.entity_id
        """
    )
    op.alter_column(
        "job_analysis_opks_items",
        "display_order",
        existing_type=sa.BigInteger(),
        nullable=False,
    )
    op.create_check_constraint(
        "ja2_ck_opks_items_display_order",
        "job_analysis_opks_items",
        "display_order >= 0",
    )
    op.create_unique_constraint(
        "ja2_uq_opks_items_order",
        "job_analysis_opks_items",
        ["document_id", "entity_kind", "display_order"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "ja2_uq_opks_items_order", "job_analysis_opks_items", type_="unique"
    )
    op.drop_constraint(
        "ja2_ck_opks_items_display_order",
        "job_analysis_opks_items",
        type_="check",
    )
    op.drop_column("job_analysis_opks_items", "display_order")
