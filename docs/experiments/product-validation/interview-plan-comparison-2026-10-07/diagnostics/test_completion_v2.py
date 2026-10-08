from datetime import timedelta

import completion_batch as historical
import completion_batch_v2 as revised
import pytest
from test_completion_batch import accounting

pytest_plugins = ["test_completion_gates"]


def test_revised_deadline_admits_after_prior_deadline_without_resetting_accounting():
    prior = accounting()
    now = historical.DEADLINE + timedelta(hours=2)
    guard = revised.carried_guard(prior, now=now, clock=lambda: 100)
    assert guard.started == 100
    assert guard.seconds == 7200
    assert str(guard.spent) == prior["spent_usd"]
    assert guard.state()["retained_reservations"] == prior["retained_reservations"]
    assert guard.generations == prior["generations"]
    assert guard.outbound == prior["outbound"]
    assert guard.counted_input == prior["counted_input"]


def test_revised_absolute_deadline_still_refuses_expiry():
    with pytest.raises(RuntimeError, match="deadline expired"):
        revised.carried_guard(accounting(), now=revised.DEADLINE)


def test_all_non_time_limits_and_original_entry_are_preserved():
    assert {key: value for key, value in revised.LIMITS.items() if key != "seconds"} == {
        key: value for key, value in historical.LIMITS.items() if key != "seconds"
    }
    assert historical.DEADLINE.isoformat() == "2026-10-07T04:30:34+00:00"
    original = historical.ARTIFACT_ROOT / "supplement-freeze-preflight/source-snapshot"
    relative = historical.Path(historical.__file__).relative_to(historical.ROOT)
    assert historical.file_hash(original / relative) == historical.file_hash(
        historical.Path(historical.__file__)
    )


def test_revised_entry_accepts_original_disk_audit_without_rewriting_its_deadline(
    incident, monkeypatch
):
    prior, audit, path = incident
    monkeypatch.setattr(revised, "DISK_AUDIT", path)
    state, note, todo = revised.read_prior(prior, current_sources={})
    assert state == audit["prior_accounting"]
    assert note["disk_recovery"]["absolute_deadline_utc"] == historical.DEADLINE.isoformat()
    assert todo == revised.SCHEDULED[1:]


def test_revised_freeze_records_explicit_revision_and_old_audit_bytes(
    incident, tmp_path, monkeypatch
):
    prior, _, audit = incident
    monkeypatch.setattr(revised, "DISK_AUDIT", audit)
    _, note, _ = revised.read_prior(prior, current_sources={})
    target = tmp_path / "new-revision/manifest.json"
    target.parent.mkdir()
    data = revised.freeze_supplement(target, note, lambda phase, path: {})
    assert data["absolute_deadline_utc"] == "2026-10-07T08:30:34+00:00"
    assert (
        data["deadline_revision"]["previous_absolute_deadline_utc"]
        == historical.DEADLINE.isoformat()
    )
    assert data["deadline_revision"]["counters_and_reservations_reset"] is False
    assert (
        data["continuation"]["disk_recovery"]["absolute_deadline_utc"]
        == historical.DEADLINE.isoformat()
    )
    assert revised.file_hash(
        historical.Path(data["prior_evidence_snapshot"][str(audit)])
    ) == historical.file_hash(audit)


def test_constructor_delay_consumes_revised_remaining_time(monkeypatch):
    import sys

    sys.path.insert(0, str(revised.HERE))
    import guard as experiment_guard

    current = [100]
    original = experiment_guard.BatchGuard

    def delayed(**kwargs):
        current[0] += 120
        return original(**kwargs)

    monkeypatch.setattr(experiment_guard, "BatchGuard", delayed)
    guard = revised.carried_guard(
        accounting(), now=revised.DEADLINE - timedelta(seconds=90), clock=lambda: current[0]
    )
    with pytest.raises(RuntimeError, match="deadline reached"):
        guard.outbound_attempt({"model": "gpt-6-luna"})
