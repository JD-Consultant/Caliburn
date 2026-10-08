from datetime import UTC, datetime

import pytest
import repaired_completion as revision


def test_review_expires_at_300_seconds_without_extending_absolute_deadline():
    before = datetime(2026, 10, 7, 7, tzinfo=UTC)
    assert not revision.review_expired(100, monotonic=399, now=before)
    assert revision.review_expired(100, monotonic=400, now=before)
    assert revision.review_expired(100, monotonic=101, now=revision.original.DEADLINE)


def test_claimed_complete_requires_actual_closure_and_completed_turn():
    complete = {"closure_submitted": True, "turns": [{"status": "completed"}]}
    assert revision.validate_complete(["one"], {"one": complete}) == ["one"]
    with pytest.raises(ValueError):
        revision.validate_complete(["one"], {"one": {**complete, "closure_submitted": False}})
    with pytest.raises(ValueError):
        revision.validate_complete(["one"], {"one": {**complete, "turns": [{"status": "failed"}]}})


def test_actual_stopped_batch_gate_carries_latest_counters_and_all_unknown_reserves():
    prior, note = revision.read_gate()
    assert prior["generations"] == 1309 and prior["compacts"] == 11
    assert prior["outbound"] == 2902 and prior["counted_input"] == 69365297
    assert prior["spent_usd"] == "1.522732230"
    assert len(prior["retained_reservations"]) == 3
    assert note["retained_completed_cases"] == revision.RETAINED
    assert note["new_scheduled_cases"] == revision.FRESH
