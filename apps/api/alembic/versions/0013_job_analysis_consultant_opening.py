"""Allow the deterministic consultant opening in the job-analysis Journal."""

from alembic import op


revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "ja2_ck_journal_kind",
        "job_analysis_journal",
        type_="check",
    )
    op.create_check_constraint(
        "ja2_ck_journal_kind",
        "job_analysis_journal",
        "kind IN ('consultant_opening','employee_turn','direct_edit','proposal_decision')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ja2_ck_journal_kind",
        "job_analysis_journal",
        type_="check",
    )
    op.create_check_constraint(
        "ja2_ck_journal_kind",
        "job_analysis_journal",
        "kind IN ('employee_turn','direct_edit','proposal_decision')",
    )
