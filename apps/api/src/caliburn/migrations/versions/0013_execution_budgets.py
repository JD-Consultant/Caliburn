"""Durable per-execution outbound reservations; no Responses body or Graph cursor copy."""

import sqlalchemy as sa
from alembic import op

revision = "0013_execution_budgets"
down_revision = "0012_memory_candidates_snapshots"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "execution_budgets",
        sa.Column(
            "execution_id", sa.Uuid(), sa.ForeignKey("executions.execution_id"), primary_key=True
        ),
        sa.Column("max_model_steps", sa.Integer(), nullable=False),
        sa.Column("max_compactions", sa.Integer(), nullable=False),
        sa.Column("max_outbound_attempts", sa.Integer(), nullable=False),
        sa.Column("max_attempts_per_request", sa.Integer(), nullable=False),
        sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("max_cost_usd", sa.Numeric(18, 9), nullable=False),
        sa.Column("cost_basis", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "max_model_steps > 0 AND max_compactions > 0 AND max_outbound_attempts > 0 "
            "AND max_attempts_per_request > 0",
            name="positive_limits",
        ),
        sa.CheckConstraint("max_cost_usd > 0 AND max_cost_usd < 1000000000", name="positive_cost"),
        sa.CheckConstraint("btrim(cost_basis) <> ''", name="cost_basis"),
    )
    op.create_table(
        "execution_outbound_attempts",
        sa.Column(
            "execution_id",
            sa.Uuid(),
            sa.ForeignKey("execution_budgets.execution_id"),
            primary_key=True,
        ),
        sa.Column("attempt_id", sa.Uuid(), primary_key=True),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("fingerprint", sa.Text(), nullable=False),
        sa.Column("writer_id", sa.Uuid(), nullable=False),
        sa.Column("reserved_cost_usd", sa.Numeric(18, 9), nullable=False),
        sa.Column("reported_cost_usd", sa.Numeric(18, 9)),
        sa.Column(
            "admitted_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.clock_timestamp(),
            nullable=False,
        ),
        sa.CheckConstraint("kind IN ('model', 'compaction', 'token_count')", name="kind"),
        sa.CheckConstraint("fingerprint ~ '^[0-9a-f]{64}$'", name="fingerprint"),
        sa.CheckConstraint(
            "reserved_cost_usd > 0 AND reserved_cost_usd < 1000000000", name="reserved_cost"
        ),
        sa.CheckConstraint(
            "reported_cost_usd IS NULL OR "
            "(reported_cost_usd >= 0 AND reported_cost_usd < 1000000000)",
            name="reported_cost",
        ),
    )
    op.create_index(
        "ix_execution_outbound_attempts_request",
        "execution_outbound_attempts",
        ["execution_id", "request_id"],
    )
    op.execute("""
        CREATE FUNCTION protect_execution_budget() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'Execution budgets cannot be reset or rewritten'
                USING ERRCODE = '23514';
        END $$;
        CREATE TRIGGER protect_execution_budget BEFORE UPDATE OR DELETE ON execution_budgets
        FOR EACH ROW EXECUTE FUNCTION protect_execution_budget();
        CREATE FUNCTION protect_outbound_attempt() RETURNS trigger LANGUAGE plpgsql AS $$
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
            RETURN NEW;
        END $$;
        CREATE TRIGGER protect_outbound_attempt
        BEFORE UPDATE OR DELETE ON execution_outbound_attempts
        FOR EACH ROW EXECUTE FUNCTION protect_outbound_attempt();
    """)


def downgrade() -> None:
    raise RuntimeError("Outbound accounting cannot be discarded by a destructive downgrade")
