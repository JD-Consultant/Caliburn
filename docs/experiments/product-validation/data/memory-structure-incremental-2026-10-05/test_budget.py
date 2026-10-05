"""Exercise the reused budget without any API call."""

from decimal import Decimal

import pytest
from study import MAX_SECONDS, MAX_USD, PRIOR, load_previous


def test_budget_is_shared_between_roles_and_blocks_reservation_over_limit():
    previous = load_previous()
    budget = previous.StudyBudget(512)
    assert budget.max_usd == MAX_USD == Decimal("0.10")
    assert budget.max_seconds == MAX_SECONDS == 1200
    assert PRIOR + MAX_USD <= Decimal(2)
    budget.reserve("b1-request", Decimal("0.04"))
    budget.settle("b1-request", Decimal("0.02"))
    budget.reserve("single-request", Decimal("0.07"))
    with pytest.raises(ValueError, match="estimated_budget_limit"):
        budget.reserve("b2-request", Decimal("0.02"))
    assert budget.occupied == Decimal("0.09")
    assert budget.pending == {"single-request": Decimal("0.07")}


def test_expired_time_and_outbound_cap_block_before_admission():
    budget = load_previous().StudyBudget(1)
    budget.reserve("first", Decimal("0.0001"))
    with pytest.raises(ValueError, match="outbound_limit"):
        budget.reserve("second", Decimal("0.0001"))
    budget.started -= 1201
    with pytest.raises(ValueError, match="time_limit"):
        budget.reserve("third", Decimal("0.0001"))
