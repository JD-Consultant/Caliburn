import pytest
from completion_batch import (
    DEADLINE,
    LIMITS,
    SCHEDULED,
    carried_guard,
    remaining_cases,
    validate_accounting,
)


def completed(**changes):
    return {
        "closure_submitted": True,
        "turns": [{"turn": 20, "status": "completed"}],
        **changes,
    }


def test_only_incomplete_and_unstarted_cases_remain_in_original_order():
    results = {
        SCHEDULED[0]: completed(),
        SCHEDULED[1]: completed(),
        SCHEDULED[2]: completed(
            closure_submitted=False,
            turns=[{"turn": 11, "status": "failed"}],
            stop="batch_resource_stop",
        ),
    }
    assert remaining_cases(results) == SCHEDULED[2:]


def test_memory_failure_and_quality_information_do_not_restart_completed_case():
    results = {
        SCHEDULED[0]: completed(
            memory_settlement={"failed": 1},
            quality="unknown",
            stop="batch_resource_stop",
        )
    }
    assert remaining_cases(results) == SCHEDULED[1:]


def test_all_unstarted_and_all_completed_boundaries():
    assert remaining_cases({}) == SCHEDULED
    assert remaining_cases({name: completed() for name in SCHEDULED}) == []


@pytest.mark.parametrize(
    "result",
    [
        completed(closure_submitted=False),
        completed(turns=[{"turn": 20, "status": "failed"}]),
        completed(turns=[{"turn": 20, "status": "observation_timeout"}]),
    ],
)
def test_closure_and_completed_turn_are_both_required(result):
    assert remaining_cases({SCHEDULED[0]: result}) == SCHEDULED


def test_unknown_case_is_rejected():
    with pytest.raises(ValueError, match="Unknown"):
        remaining_cases({"warehouse-r3-P2": completed()})


@pytest.mark.parametrize("results", [[], "", None])
def test_non_mapping_completion_evidence_cannot_mean_all_cases_unstarted(results):
    with pytest.raises(ValueError, match="completion evidence"):
        remaining_cases(results)


@pytest.mark.parametrize(
    "result",
    [
        {},
        completed(closure_submitted=1),
        completed(turns=[]),
        completed(turns=[{"turn": 20}]),
    ],
)
def test_ambiguous_completion_evidence_is_rejected(result):
    with pytest.raises(ValueError, match="completion evidence"):
        remaining_cases({SCHEDULED[0]: result})


def accounting():
    return {
        "spent_usd": "0.25",
        "occupied_usd": "0.263296750",
        "retained_reservations": {"original-unknown": "0.013296750"},
        "generations": 250,
        "compacts": 0,
        "outbound": 550,
        "counted_input": 12000000,
        "stop_reason": "batch counted input token limit reached",
    }


def test_valid_accounting_keeps_every_consumed_counter_and_unknown_reserve():
    inherited = accounting()
    prior = {**inherited, "spent_usd": "0.4", "occupied_usd": "0.413296750"}
    assert validate_accounting(prior, inherited) == prior


@pytest.mark.parametrize(
    "change",
    [
        {"spent_usd": "-0.1"},
        {"occupied_usd": "0.25"},
        {"spent_usd": "NaN"},
        {"generations": 249},
        {"generations": True},
        {"compacts": -1},
        {"outbound": 549},
        {"counted_input": 11999999},
        {"retained_reservations": {}, "occupied_usd": "0.25"},
        {
            "retained_reservations": {"original-unknown": "0.013"},
            "occupied_usd": "0.263",
        },
    ],
)
def test_contradictory_accounting_and_counter_rollback_fail_closed(change):
    inherited = accounting()
    with pytest.raises(ValueError, match="accounting"):
        validate_accounting({**inherited, **change}, inherited)


def test_supplement_preloads_all_consumption_and_keeps_unknown_reservation():
    from datetime import timedelta
    from decimal import Decimal

    prior = accounting()
    guard = carried_guard(prior, now=DEADLINE - timedelta(seconds=90), clock=lambda: 100)
    assert guard.spent == Decimal(prior["spent_usd"])
    assert guard.attempts == {"original-unknown": Decimal("0.013296750")}
    assert guard.occupied == Decimal(prior["occupied_usd"])
    assert (guard.generations, guard.compacts, guard.outbound, guard.counted_input) == (
        250,
        0,
        550,
        12000000,
    )
    assert guard.limit == Decimal(8)
    assert (
        guard.max_generations,
        guard.max_compacts,
        guard.max_outbound,
        guard.max_counted_input,
    ) == (3000, 32, 7000, 180000000)
    assert guard.started == 100 and guard.seconds == 90


def test_supplement_constructor_delay_does_not_extend_absolute_deadline(monkeypatch):
    import sys
    from datetime import timedelta
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    import guard as experiment_guard

    current = [100]
    original = experiment_guard.BatchGuard

    def delayed(**kwargs):
        current[0] += 120
        return original(**kwargs)

    monkeypatch.setattr(experiment_guard, "BatchGuard", delayed)
    guard = carried_guard(
        accounting(), now=DEADLINE - timedelta(seconds=90), clock=lambda: current[0]
    )
    with pytest.raises(RuntimeError, match="deadline reached"):
        guard.outbound_attempt({"model": "gpt-6-luna"})


def test_supplement_expired_deadline_is_rejected():
    with pytest.raises(RuntimeError, match="deadline expired"):
        carried_guard(accounting(), now=DEADLINE)


@pytest.mark.parametrize(
    "counter,limit",
    [
        ("generations", "max_generations"),
        ("compacts", "max_compacts"),
        ("outbound", "max_outbound"),
        ("counted_input", "max_counted_input"),
    ],
)
def test_supplement_exhausted_total_counter_is_rejected_before_dispatch(counter, limit):
    from datetime import timedelta

    with pytest.raises(ValueError, match="Supplement .* exhausted"):
        carried_guard(
            {**accounting(), counter: LIMITS[limit]}, now=DEADLINE - timedelta(seconds=90)
        )


def test_supplement_usd_limit_cannot_be_extended():
    from datetime import timedelta

    with pytest.raises(ValueError, match="USD budget"):
        carried_guard(
            {**accounting(), "spent_usd": "8", "occupied_usd": "8.013296750"},
            now=DEADLINE - timedelta(seconds=90),
        )
