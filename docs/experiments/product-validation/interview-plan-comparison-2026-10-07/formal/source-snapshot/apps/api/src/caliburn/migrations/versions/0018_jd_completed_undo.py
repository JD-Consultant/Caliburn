"""Allow completed-Turn JD undo in the existing immutable operation journal."""

from alembic import op

revision = "0018_jd_completed_undo"
down_revision = "0017_jd_source_references"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(op.f("ck_jd_operations_kind"), "jd_operations", type_="check")
    op.create_check_constraint(
        op.f("ck_jd_operations_kind"),
        "jd_operations",
        "kind IN ('revise_profile', 'edit_areas', 'edit_tasks', 'edit_capabilities', "
        "'edit_collaborators', 'edit_conditions', 'restore_candidate', "
        "'discard_candidate', 'adopt_candidate', 'edit_sources', 'undo_completed_turn')",
    )


def downgrade() -> None:
    raise RuntimeError("Completed JD undo results must remain recoverable")
