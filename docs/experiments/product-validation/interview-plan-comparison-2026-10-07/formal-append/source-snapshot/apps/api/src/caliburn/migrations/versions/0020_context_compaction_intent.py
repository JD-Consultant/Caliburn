"""Retain next-work compaction intent on the existing role history binding."""

import sqlalchemy as sa
from alembic import op

revision = "0020_context_compaction_intent"
down_revision = "0019_optional_cost_limit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "context_history_bindings",
        sa.Column("compact_requested", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    raise RuntimeError("Cannot discard outstanding context compaction requests")
