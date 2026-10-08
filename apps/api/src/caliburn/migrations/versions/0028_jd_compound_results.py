"""既有 JD operation 保存複合用例的原效果及建立身分，不另設回執表。"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0028_jd_compound_results"
down_revision = "0027_diagnostic_request_context"
branch_labels = None
depends_on = None

_KINDS = (
    "'revise_profile', 'edit_areas', 'edit_tasks', 'edit_capabilities', "
    "'edit_collaborators', 'edit_conditions', 'restore_candidate', "
    "'discard_candidate', 'adopt_candidate', 'edit_sources', 'undo_completed_turn'"
)


def upgrade() -> None:
    op.add_column("jd_operations", sa.Column("result_payload", JSONB(), nullable=True))
    op.drop_constraint(op.f("ck_jd_operations_kind"), "jd_operations", type_="check")
    op.create_check_constraint(
        op.f("ck_jd_operations_kind"), "jd_operations", f"kind IN ({_KINDS}, 'compound_edit')"
    )


def downgrade() -> None:
    raise RuntimeError("Compound JD operation results cannot be discarded by downgrade")
