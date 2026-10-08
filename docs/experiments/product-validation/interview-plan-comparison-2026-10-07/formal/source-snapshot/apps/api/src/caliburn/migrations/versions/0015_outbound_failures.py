"""Preserve classified outbound failure originals in the existing accounting owner."""

import sqlalchemy as sa
from alembic import op

revision = "0015_outbound_failures"
down_revision = "0014_execution_pause_requests"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("execution_outbound_attempts", sa.Column("failure_code", sa.Text()))
    op.add_column(
        "execution_outbound_attempts", sa.Column("retry_not_before", sa.DateTime(timezone=True))
    )
    op.create_check_constraint(
        "failure_code",
        "execution_outbound_attempts",
        "failure_code IS NULL OR failure_code IN ('remote_result_unknown', "
        "'transient_service', 'access_blocked', 'capacity_exceeded', "
        "'request_rejected', 'response_protocol')",
    )
    op.create_check_constraint(
        "failure_retry",
        "execution_outbound_attempts",
        "retry_not_before IS NULL OR (failure_code IS NOT NULL AND "
        "failure_code IN ('remote_result_unknown', 'transient_service'))",
    )
    # Extend 0013's protection without weakening identity, deletion or observed cost fencing.
    # Late costs may settle an already failed attempt, but known success cannot become failure.
    op.execute("""
        CREATE OR REPLACE FUNCTION protect_outbound_attempt() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'Outbound attempts cannot be removed' USING ERRCODE = '23514';
            END IF;
            IF ROW(NEW.execution_id, NEW.attempt_id, NEW.request_id, NEW.kind, NEW.fingerprint,
                   NEW.writer_id, NEW.reserved_cost_usd, NEW.admitted_at)
               IS DISTINCT FROM
               ROW(OLD.execution_id, OLD.attempt_id, OLD.request_id, OLD.kind, OLD.fingerprint,
                   OLD.writer_id, OLD.reserved_cost_usd, OLD.admitted_at)
               OR (OLD.reported_cost_usd IS NOT NULL AND
                   NEW.reported_cost_usd IS DISTINCT FROM OLD.reported_cost_usd) THEN
                RAISE EXCEPTION 'Outbound identity and observed costs cannot be rewritten'
                    USING ERRCODE = '23514';
            END IF;
            IF OLD.failure_code IS NOT NULL AND
               ROW(NEW.failure_code, NEW.retry_not_before)
               IS DISTINCT FROM ROW(OLD.failure_code, OLD.retry_not_before) THEN
                RAISE EXCEPTION 'Outbound failures cannot be rewritten' USING ERRCODE = '23514';
            END IF;
            IF OLD.failure_code IS NULL AND OLD.reported_cost_usd IS NOT NULL
               AND NEW.failure_code IS NOT NULL THEN
                RAISE EXCEPTION 'Accounted successful attempts cannot become failures'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END $$
    """)


def downgrade() -> None:
    raise RuntimeError("Outbound failure originals cannot be discarded by a destructive downgrade")
