"""Explicit mechanical revision must preserve prior cost and resource counters."""

import json
import shutil
import sys
from decimal import Decimal
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from carry import audit_raw, load_carry, verify_carry
from frozen_manifest import LIMITS, arm_templates
from runner import guard_from_ledger

FINAL = {
    "spent_usd": "0.040769275",
    "occupied_usd": "0.040769275",
    "retained_reservations": {},
    "generations": 49,
    "compacts": 0,
    "outbound": 104,
    "counted_input": 1077584,
    "stop_reason": None,
    "batch_deadline": None,
    "limit_usd": "4.00",
}


def test_fresh_revision_guard_starts_at_carried_usage_not_zero(tmp_path):
    frozen = {
        "limits": LIMITS,
        "arm_templates": arm_templates(),
        "carry": {"final_guard": FINAL},
    }
    guard = guard_from_ledger(tmp_path, frozen)
    assert guard.spent == Decimal("0.040769275")
    assert guard.generations == 49
    assert guard.outbound == 104
    assert guard.counted_input == 1077584


def test_carried_unknown_reservation_is_not_reset(tmp_path):
    state = {
        **FINAL,
        "retained_reservations": {"unknown": "0.5"},
        "occupied_usd": "0.540769275",
    }
    frozen = {
        "limits": LIMITS,
        "arm_templates": arm_templates(),
        "carry": {"final_guard": state},
    }
    with pytest.raises(RuntimeError, match="unknown"):
        guard_from_ledger(tmp_path, frozen)


@pytest.fixture
def preserved_prior(tmp_path):
    original = HERE / "runs/comparison-v1"
    report = json.loads(
        (original / "interruption-accounting.json").read_text(encoding="utf-8")
    )
    directory = tmp_path / "comparison-v1"
    for relative in ["interruption-accounting.json", *report["artifact_sha256"]]:
        target = directory / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(original / relative, target)
    return directory


def test_raw_prior_independently_seeds_the_exact_cumulative_accounting(preserved_prior):
    carry = load_carry(preserved_prior)
    assert carry["final_guard"] == FINAL
    verify_carry(preserved_prior.parent, carry)


def test_unfinished_raw_admission_is_rejected(preserved_prior):
    trace = preserved_prior / "pilot/warehouse-r1-P2/provider-trace.jsonl"
    rows = [json.loads(line) for line in trace.read_text(encoding="utf-8").splitlines()]
    for index in range(len(rows) - 1, -1, -1):
        if rows[index]["event"] == "received":
            rows.pop(index)
            break
    trace.write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8"
    )
    with pytest.raises(RuntimeError, match="unfinished outbound"):
        audit_raw(
            preserved_prior,
            json.loads((preserved_prior / "manifest.json").read_text(encoding="utf-8")),
        )


def test_unknown_raw_usage_is_rejected(preserved_prior):
    trace = preserved_prior / "pilot/warehouse-r1-P2/provider-trace.jsonl"
    rows = [json.loads(line) for line in trace.read_text(encoding="utf-8").splitlines()]
    next(row for row in reversed(rows) if row["event"] == "received")["usage"] = None
    trace.write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8"
    )
    with pytest.raises(RuntimeError, match="Unknown usage"):
        audit_raw(
            preserved_prior,
            json.loads((preserved_prior / "manifest.json").read_text(encoding="utf-8")),
        )


def test_prior_trace_hash_drift_blocks_new_outbound(preserved_prior):
    carry = load_carry(preserved_prior)
    trace = preserved_prior / "pilot/warehouse-r1-P2/provider-trace.jsonl"
    trace.write_text(trace.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="evidence missing or changed"):
        verify_carry(preserved_prior.parent, carry)


def test_prior_counter_mismatch_cannot_seed_new_revision(preserved_prior):
    trace = preserved_prior / "pilot/warehouse-r1-P2/provider-trace.jsonl"
    rows = [json.loads(line) for line in trace.read_text(encoding="utf-8").splitlines()]
    rows[-1]["outbound"] = 103
    trace.write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8"
    )
    with pytest.raises(RuntimeError, match="cumulative witness"):
        audit_raw(
            preserved_prior,
            json.loads((preserved_prior / "manifest.json").read_text(encoding="utf-8")),
        )


def test_pilot_limit_remains_cumulative_after_seed(tmp_path):
    guard = guard_from_ledger(
        tmp_path,
        {
            "limits": LIMITS,
            "arm_templates": arm_templates(),
            "carry": {"final_guard": FINAL},
        },
    )
    guard.phase = "pilot"
    guard.phase_start = {"generations": 0, "compacts": 0}
    guard.generations = 160
    with pytest.raises(RuntimeError, match="pilot generation allowance"):
        guard.admit({"model": "gpt-6-luna"})
