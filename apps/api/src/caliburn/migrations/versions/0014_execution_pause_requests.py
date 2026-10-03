"""Persist pause intent separately from a durable native Graph stop."""

import sqlalchemy as sa
from alembic import op

revision = "0014_execution_pause_requests"
down_revision = "0013_execution_budgets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "executions",
        sa.Column("pause_requested", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.create_check_constraint(
        "pause_request_control",
        "executions",
        "NOT pause_requested OR (kind = 'consultant_turn' AND status IN ('active', 'paused'))",
    )
    # Keep 0002's identity and terminal fencing, including the new control intent.
    # OLD is essential: clearing the flag in the same UPDATE cannot bypass a pending pause.
    op.execute("""
        CREATE OR REPLACE FUNCTION protect_execution_identity() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF ROW(NEW.execution_id, NEW.job_file_id, NEW.kind, NEW.created_at)
               IS DISTINCT FROM
               ROW(OLD.execution_id, OLD.job_file_id, OLD.kind, OLD.created_at) THEN
                RAISE EXCEPTION 'Execution identity cannot be rewritten' USING ERRCODE = '23514';
            END IF;
            IF OLD.status IN ('completed', 'cancelled', 'failed')
               AND ROW(NEW.status, NEW.writer_id, NEW.pause_requested)
                   IS DISTINCT FROM ROW(OLD.status, OLD.writer_id, OLD.pause_requested) THEN
                RAISE EXCEPTION 'Terminal eligibility cannot be revived' USING ERRCODE = '23514';
            END IF;
            IF NEW.status = 'completed' AND (OLD.status = 'paused' OR OLD.pause_requested) THEN
                RAISE EXCEPTION 'Completion cannot cross a pending or durable pause'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END
        $$
    """)


def downgrade() -> None:
    raise RuntimeError("Durable pause requests cannot be discarded by a destructive downgrade")
