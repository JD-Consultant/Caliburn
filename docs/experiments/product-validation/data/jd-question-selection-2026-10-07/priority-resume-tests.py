"""Offline counterexamples for an authorized time-only continuation."""

import asyncio
import copy
import importlib.util
import json
import sys
from argparse import Namespace
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest

HERE = Path(__file__).resolve().parent
ROOT = next(path for path in HERE.parents if (path / "AGENTS.md").is_file())
sys.path.insert(0, str(ROOT / "apps/api/src"))
SOURCE = HERE / "priority-resume-run.py"
FALLBACK = HERE / "priority-probe-core.py"
spec = importlib.util.spec_from_file_location(
    "priority_resume_test_subject", SOURCE if SOURCE.exists() else FALLBACK
)
subject = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = subject
spec.loader.exec_module(subject)
core = getattr(subject, "core", subject)


def baseline():
    return {
        "spent_usd": "1.966786395",
        "occupied_usd": "2.014531895",
        "retained_reservations": {
            "9ac7fad2-d05b-4299-9aff-5d89f0141dae": "0.013296750",
            "01e0648a-f46b-49ed-95b3-680b10a61693": "0.011862125",
            "05c0ef97-997d-40bc-9eec-d03be74f09a7": "0.022586625",
        },
        "generations": 1738,
        "outbound": 3847,
        "counted_input": 90093382,
        "compacts": 14,
        "stop_reason": None,
    }


def previous():
    return {
        **baseline(),
        "spent_usd": "2.016560225",
        "occupied_usd": "2.064305725",
        "generations": 1796,
        "outbound": 3973,
        "counted_input": 91281083,
        "stop_reason": "absolute deadline reached",
    }


def build_guard(state=None, original=None):
    if not hasattr(subject, "resume_guard"):
        return core.carried_guard(previous(), now=core.DEADLINE + timedelta(seconds=1))
    return subject.resume_guard(state or previous(), original or baseline(), clock=lambda: 1000000)


def test_cancelled_time_allows_original_expired_stop_without_resetting_consumption():
    guard = build_guard()
    guard.check({"model": "gpt-6-luna"})
    assert guard.state()["spent_usd"] == previous()["spent_usd"]
    assert guard.generations == 1796 and guard.outbound == 3973
    assert guard.counted_input == 91281083 and guard.compacts == 14
    assert guard.attempts == {
        key: Decimal(value) for key, value in previous()["retained_reservations"].items()
    }
    assert guard.stop_reason is None


def test_increment_is_anchored_to_original_probe_not_reallocated_on_resume():
    guard = build_guard()
    assert guard.limit == Decimal("2.514531895")
    assert guard.max_generations == 1994
    assert guard.max_outbound == 4447
    assert guard.max_counted_input == 106093382
    assert guard.max_compacts == 22


@pytest.mark.parametrize("key", list(core.COUNTERS))
def test_original_global_cap_still_clamps_probe_extension(key):
    original = baseline()
    original[key] = core.GLOBAL_COUNTER_LIMITS[key] - 2
    state = previous()
    state[key] = core.GLOBAL_COUNTER_LIMITS[key] - 1
    guard = build_guard(state, original)
    assert getattr(guard, "max_" + key) == core.GLOBAL_COUNTER_LIMITS[key]


def test_spending_up_to_old_increment_cannot_unlock_another_fifty_cents():
    state = previous()
    state["spent_usd"] = "2.466786395"
    state["occupied_usd"] = "2.514531895"
    with pytest.raises(ValueError, match="budget exhausted"):
        build_guard(state)


@pytest.mark.parametrize(
    "reason",
    [
        "unknown provider usage; reservation retained",
        "batch budget reached",
        "batch generation attempt limit reached",
    ],
)
def test_time_authorization_cannot_clear_non_time_stops(reason):
    with pytest.raises(ValueError, match="time stop"):
        build_guard({**previous(), "stop_reason": reason})


@pytest.mark.parametrize("key", list(core.COUNTERS))
def test_original_increment_cannot_be_refilled_after_exhaustion(key):
    exhausted = {**previous(), key: baseline()[key] + core.COUNTERS[key]}
    with pytest.raises(ValueError, match="counter exhausted"):
        build_guard(exhausted)


def test_unknown_reserve_cannot_be_removed_or_repriced():
    changed = previous()
    changed["retained_reservations"] = dict(list(baseline()["retained_reservations"].items())[:2])
    changed["occupied_usd"] = str(
        Decimal(changed["spent_usd"]) + sum(map(Decimal, changed["retained_reservations"].values()))
    )
    with pytest.raises(ValueError, match="reservations changed"):
        build_guard(changed)


def test_schedule_retains_exact_complete_prefix_and_restarts_only_partial_with_unique_attempt():
    schedule = core.next_schedule()
    done = [{"trial": item["trial"], "replies": 3} for item in schedule[:5]]
    remaining = subject.remaining_schedule(schedule, done, "resume01")
    assert len(remaining) == 19
    assert remaining[0]["logical_trial"] == "c03-r1-B1"
    assert [item["logical_trial"] for item in remaining] == [item["trial"] for item in schedule[5:]]
    assert len({item["trial"] for item in remaining}) == 19
    assert all(item["trial"] != item["logical_trial"] for item in remaining)
    assert [item["arm"] for item in remaining] == [item["arm"] for item in schedule[5:]]


@pytest.mark.parametrize("indices", [[0, 2], [0, 0], [1], [0, 1, 3]])
def test_skipping_or_duplicating_complete_trials_cannot_select_a_quality_sample(indices):
    schedule = core.next_schedule()
    with pytest.raises(ValueError, match="exact schedule prefix"):
        subject.remaining_schedule(
            schedule, [{"trial": schedule[i]["trial"], "replies": 1} for i in indices], "resume01"
        )


def test_source_and_criteria_privacy_fence_remains_the_original_function():
    guard = build_guard()
    guard.inspect_request = lambda payload: core.inspect_public_request(
        payload,
        expected_instructions="same",
        private_answers=["undisclosed answer"],
        disclosed=set(),
        private_criteria=("private assessment",),
    )
    for text in ["undisclosed answer", "private assessment"]:
        with pytest.raises(ValueError):
            guard.outbound_attempt({"model": "gpt-6-luna", "instructions": "same", "input": text})


def test_wait_is_bounded_without_an_experiment_time_deadline():
    guard = build_guard()
    ticks = iter([0.0, 301.0])
    with pytest.raises(RuntimeError, match="semantic review wait"):
        asyncio.run(
            subject.wait_decision(
                Path("nonexistent-resume-output"),
                "opaque",
                "question",
                "warehouse_load",
                {},
                guard,
                monotonic=lambda: next(ticks),
            )
        )
    assert guard.stop_reason == "semantic review wait exceeded 300 seconds"


def test_late_file_cannot_escape_wait_bound_when_it_appears_during_sleep(monkeypatch):
    guard = build_guard()
    output = core.OUTPUT_ROOT / ("priority-probe-resume-late-file-" + uuid4().hex[:8])
    (output / "decisions").mkdir(parents=True)
    clock = [0.0]

    async def late_arrival(seconds):
        (output / "decisions" / "opaque.json").write_text(
            json.dumps(
                {
                    "question_quote": "question",
                    "reason": "synthetic",
                    "review_method": "semantic_review",
                    "answer_kind": "unknown",
                }
            ),
            encoding="utf-8",
        )
        clock[0] = 301.0

    monkeypatch.setattr(asyncio, "sleep", late_arrival)
    with pytest.raises(RuntimeError, match="semantic review wait"):
        asyncio.run(
            subject.wait_decision(
                output,
                "opaque",
                "question",
                "warehouse_load",
                {"unknown_reply": "unknown"},
                guard,
                monotonic=lambda: clock[0],
            )
        )
    assert guard.stop_reason == "semantic review wait exceeded 300 seconds"


def test_final_ledger_keeps_retained_complete_and_partial_costs_separate():
    schedule = core.next_schedule()
    completed = [{"trial": t["trial"], "replies": 3} for t in schedule[:5]]
    manifest = {
        "schedule": subject.remaining_schedule(schedule, completed, "resume01"),
        "retained_completed": completed,
        "prior_effective_replies": 16,
        "prior_partial_effective_replies": 1,
        "probe_baseline_guard": baseline(),
        "time_limit_cancelled_authorization": "不用管截止",
    }
    raw = {
        "completed": [{"trial": manifest["schedule"][0]["trial"], "replies": 3}],
        "effective_replies": 3,
        "guard": previous(),
        "absolute_deadline_utc": core.DEADLINE.isoformat(),
    }
    value = subject.annotate_final(raw, manifest)
    assert value["effective_replies"] == 19
    assert value["new_effective_replies"] == 3
    assert value["retained_effective_replies"] == 16
    assert len(value["all_completed_logical_trials"]) == 6
    assert value["completed"][0]["logical_trial"] == "c03-r1-B1"
    assert value["absolute_deadline_utc"] is None
    assert value["planned_max_effective_replies"] == 48
    assert value["actual_max_effective_replies"] == 49


def test_prepare_and_adaptation_never_connect_or_read_key(monkeypatch):
    original_dir = core.OUTPUT_ROOT / "priority-probe-after-repair-v1"
    name = "priority-probe-resume-offline-" + uuid4().hex[:8]
    args = Namespace(mode="prepare", previous=str(original_dir), name=name, offline_only=True)
    runner = subject.original_runner()
    driver = runner.shared()

    def blocked(*args, **kwargs):
        pytest.fail("Offline continuation attempted credential/database/network")

    monkeypatch.setattr(driver, "read_openai_api_key", blocked)
    monkeypatch.setattr(driver.psycopg, "connect", blocked)
    monkeypatch.setattr(driver, "create_engine", blocked)
    monkeypatch.setattr(driver.subprocess, "run", blocked)
    monkeypatch.setattr(runner, "owned_database", blocked)
    monkeypatch.setattr(runner, "shared", lambda: driver)
    monkeypatch.setattr(subject, "original_runner", lambda: runner)
    output = subject.prepare(args)
    manifest = core.read_json(output / "manifest.json")
    assert len(manifest["schedule"]) == 19
    assert manifest["offline_only"] is True
    assert manifest["absolute_deadline_utc"] is None
    assert manifest["probe_baseline_guard"] == baseline()
    assert manifest["prior_guard"] == previous()
    assert manifest["actual_max_effective_replies"] == 49
    assert manifest["previous_frozen_manifest_sha256"] == core.file_hash(
        original_dir / "manifest.json"
    )
    subject.verify(manifest)
    for key, value in [
        ("prior_effective_replies", 0),
        ("actual_max_effective_replies", 50),
        ("fresh_max_effective_replies", 40),
        ("prior_partial_effective_replies", 0),
        ("planned_max_effective_replies", 49),
        ("semantic_review_wait_seconds", 900),
        ("quality_bodies_read_for_retention", True),
    ]:
        altered = copy.deepcopy(manifest)
        altered[key] = value
        with pytest.raises(ValueError, match="Continuation reply/selection metadata changed"):
            subject.verify(altered)
    assert (
        manifest["time_limit_revocation_receipt_sha256"]
        == "a0f24a1b21752c3dc232f68493308dff641121ae833b0f08573ecffb59de50a4"
    )
    for key in ["instructions", "cases", "assessments"]:
        altered = copy.deepcopy(manifest)
        altered[key] = None
        with pytest.raises(ValueError, match="Frozen trial method changed"):
            subject.verify(altered)
    with pytest.raises(ValueError, match="Offline preparation"):
        subject.execute(args)
    assert not (output / "started.json").exists()


def test_adapter_writes_cumulative_export_and_permanent_unique_resume_lease(monkeypatch):
    original_dir = core.OUTPUT_ROOT / "priority-probe-after-repair-v1"
    name = "priority-probe-resume-adapter-" + uuid4().hex[:8]
    args = Namespace(previous=str(original_dir), name=name, offline_only=False)
    runner = subject.original_runner()
    driver = runner.shared()

    def blocked(*args, **kwargs):
        pytest.fail("Adapter-only test attempted key/database/network")

    monkeypatch.setattr(driver, "read_openai_api_key", blocked)
    monkeypatch.setattr(driver.psycopg, "connect", blocked)
    monkeypatch.setattr(driver, "create_engine", blocked)
    monkeypatch.setattr(driver.subprocess, "run", blocked)
    monkeypatch.setattr(runner, "owned_database", blocked)
    monkeypatch.setattr(runner, "shared", lambda: driver)
    monkeypatch.setattr(subject, "original_runner", lambda: runner)
    output = subject.prepare(args)
    manifest = core.read_json(output / "manifest.json")
    lease_root = output / "offline-lease-test"
    monkeypatch.setattr(runner.core, "OUTPUT_ROOT", lease_root)

    def execute_only_exports(received):
        guard = runner.core.carried_guard(
            manifest["prior_guard"], verify_frozen=lambda: runner.verify(manifest)
        )
        guard.check({"model": "gpt-6-luna"})
        runner.save_new(
            lease_root / "priority-probe-execution-lease.json", {"directory": str(output)}
        )
        runner.save_new(
            output / "started.json", {"deadline": "old", "prior_guard": manifest["prior_guard"]}
        )
        runner.save_new(
            output / "final-ledger.json",
            {
                "completed": [],
                "effective_replies": 0,
                "guard": guard.state(),
                "prior_guard": manifest["prior_guard"],
                "absolute_deadline_utc": "old",
            },
        )

    monkeypatch.setattr(runner, "execute", execute_only_exports)
    subject.execute(args)
    result = core.read_json(output / "final-ledger.json")
    assert result["effective_replies"] == 16
    assert result["new_effective_replies"] == 0
    assert result["all_completed_logical_trials"] == [
        item["trial"] for item in manifest["retained_completed"]
    ]
    assert result["guard"]["occupied_usd"] == "2.064305725"
    assert result["guard"]["stop_reason"] is None
    assert core.read_json(output / "started.json")["deadline"] is None
    assert (lease_root / "priority-resume-execution-lease.json").is_file()
    assert not (lease_root / "priority-probe-execution-lease.json").exists()
    with pytest.raises(FileExistsError):
        subject.execute(args)
