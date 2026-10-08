"""Allow product executions without a monetary gate; preserve explicit evaluation budgets."""

import sqlalchemy as sa
from alembic import op

revision = "0019_optional_cost_limit"
down_revision = "0018_jd_completed_undo"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "execution_budgets", "max_cost_usd", existing_type=sa.Numeric(18, 9), nullable=True
    )


def downgrade() -> None:
    raise RuntimeError("Cannot invent monetary limits for existing product executions")
