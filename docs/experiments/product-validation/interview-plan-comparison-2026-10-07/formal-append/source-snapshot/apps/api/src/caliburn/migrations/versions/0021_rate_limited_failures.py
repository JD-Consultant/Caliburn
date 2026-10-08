"""Record a provider rate limit as its own retryable failure, separate from service faults."""

from alembic import op

revision = "0021_rate_limited_failures"
down_revision = "0020_context_compaction_intent"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("failure_code", "execution_outbound_attempts", type_="check")
    op.drop_constraint("failure_retry", "execution_outbound_attempts", type_="check")
    op.create_check_constraint(
        "failure_code",
        "execution_outbound_attempts",
        "failure_code IS NULL OR failure_code IN ('remote_result_unknown', "
        "'transient_service', 'rate_limited', 'access_blocked', 'capacity_exceeded', "
        "'request_rejected', 'response_protocol')",
    )
    op.create_check_constraint(
        "failure_retry",
        "execution_outbound_attempts",
        "retry_not_before IS NULL OR (failure_code IS NOT NULL AND "
        "failure_code IN ('remote_result_unknown', 'transient_service', 'rate_limited'))",
    )


def downgrade() -> None:
    raise RuntimeError("Saved rate-limited attempts cannot be folded into another failure code")
