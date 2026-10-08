"""No-key finite accounting checks for the explicitly authorized append batch."""

import sys
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from append_batch import DEADLINE, carried_guard  # noqa: E402

PRIOR = {
    "spent_usd": "0.022429100",
    "occupied_usd": "0.035725850",
    "retained_reservations": {"original-unknown": "0.013296750"},
    "generations": 36,
    "compacts": 0,
    "outbound": 77,
    "counted_input": 765475,
}


def test_prior_cost_reserve_and_all_counters_are_preserved():
    guard = carried_guard(
        PRIOR, now=DEADLINE - timedelta(seconds=90), clock=lambda: 100
    )
    assert guard.occupied == Decimal("0.035725850")
    assert guard.attempts == {"original-unknown": Decimal("0.013296750")}
    assert (guard.generations, guard.outbound, guard.counted_input) == (36, 77, 765475)
    assert guard.seconds == 90 and guard.started == 100


def test_deadline_cannot_be_reset_or_started_after_expiry():
    with pytest.raises(RuntimeError, match="deadline expired"):
        carried_guard(PRIOR, now=DEADLINE)


def test_generation_and_input_caps_include_original_consumption():
    guard = carried_guard(
        PRIOR, now=DEADLINE - timedelta(seconds=90), max_generations=36
    )
    with pytest.raises(RuntimeError, match="generation attempt limit"):
        guard.admit({})
    guard = carried_guard(
        PRIOR, now=DEADLINE - timedelta(seconds=90), max_counted_input=765475
    )
    with pytest.raises(RuntimeError, match="counted input"):
        guard.count({"model": "gpt-6-luna"}, 1)


def test_occupied_mismatch_is_rejected_instead_of_freeing_unknown_usage():
    with pytest.raises(RuntimeError, match="released or changed"):
        carried_guard(
            {**PRIOR, "retained_reservations": {}}, now=DEADLINE - timedelta(seconds=90)
        )


def test_constructor_delay_cannot_extend_the_original_absolute_deadline(monkeypatch):
    import append_batch

    current = [100]
    original = append_batch.BatchGuard

    def delayed(**kwargs):
        current[0] += 120
        return original(**kwargs)

    monkeypatch.setattr(append_batch, "BatchGuard", delayed)
    guard = carried_guard(
        PRIOR,
        now=DEADLINE - timedelta(seconds=90),
        clock=lambda: current[0],
    )
    with pytest.raises(RuntimeError, match="deadline reached"):
        guard.outbound_attempt({"model": "gpt-6-luna"})


def test_append_wires_owned_stream_and_accounts_without_reading_key(monkeypatch):
    import asyncio
    import append_batch
    import guard as experiment_guard
    from append_stream import OwnedObservedStream

    original_stream = experiment_guard.ObservedStream
    original_factory = append_batch.run_batch.BatchGuard
    original_freeze = append_batch.run_batch.freeze
    monkeypatch.setattr(append_batch, "prior_evidence", lambda: (PRIOR, {}))

    async def no_provider_main():
        assert experiment_guard.ObservedStream is OwnedObservedStream
        guard = append_batch.run_batch.BatchGuard(limit=Decimal(8))
        assert guard.generations == 36 and guard.outbound == 77
        assert guard.attempts["original-unknown"] == Decimal("0.013296750")

    monkeypatch.setattr(append_batch.run_batch, "main", no_provider_main)
    try:
        asyncio.run(append_batch.main())
    finally:
        experiment_guard.ObservedStream = original_stream
        append_batch.run_batch.BatchGuard = original_factory
        append_batch.run_batch.freeze = original_freeze
