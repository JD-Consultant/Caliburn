"""Root-only continuation after the human cancelled the experiment time limit.

Reuse the frozen formal runner; only bind continuation metadata, output lease,
time-free guard and a bounded semantic-review wait in this process. Imports,
dry-run and prepare never read credentials or connect to a database/provider.
"""

import argparse
import copy
import importlib.util
import json
import platform
import re
import sys
import time
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import uuid4

HERE = Path(__file__).resolve().parent
ROOT = next(path for path in HERE.parents if (path / "AGENTS.md").is_file())
sys.path.insert(0, str(ROOT / "apps/api/src"))
spec = importlib.util.spec_from_file_location(
    "priority_resume_core", HERE / "priority-probe-core.py"
)
core = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = core
spec.loader.exec_module(core)
TIME_AUTHORIZATION = "不用管截止"
TIME_STOPS = {None, "absolute deadline reached", "batch deadline reached"}
REVOCATION_RECEIPT = core.OUTPUT_ROOT / "time-limit-revocation-user-receipt.json"
REVOCATION_RECEIPT_SHA256 = "a0f24a1b21752c3dc232f68493308dff641121ae833b0f08573ecffb59de50a4"


def original_runner() -> Any:
    return core.load_module(
        "priority_resume_original_runner_" + uuid4().hex, HERE / "priority-probe-run.py"
    )


class ResumeGuard(core.ProbeGuard):
    def check(self, payload: dict[str, Any]) -> None:
        if self.stop_reason:
            raise RuntimeError(self.stop_reason)
        if payload.get("model") != "gpt-6-luna":
            raise RuntimeError("unapproved model")
        if self.started is None:
            self.started = self.clock()


def fixed_limits(baseline: dict[str, Any]) -> dict[str, int]:
    return {
        key: min(core.GLOBAL_COUNTER_LIMITS[key], baseline[key] + increment)
        for key, increment in core.COUNTERS.items()
    }


def resume_guard(
    previous: dict[str, Any],
    baseline: dict[str, Any],
    *,
    clock: Callable[[], float] = time.monotonic,
    verify_frozen: Callable[[], None] = lambda: None,
) -> ResumeGuard:
    core.validate_accounting(previous, baseline)
    if previous.get("stop_reason") not in TIME_STOPS:
        raise ValueError("Only a time stop may be cleared by the time cancellation")
    limits = fixed_limits(baseline)
    if any(previous[key] >= limit for key, limit in limits.items()):
        raise ValueError("Original probe/global counter exhausted")
    limit = min(Decimal("8.00"), Decimal(baseline["occupied_usd"]) + Decimal("0.50"))
    if Decimal(previous["occupied_usd"]) >= limit:
        raise ValueError("Original probe/global budget exhausted")
    guard = ResumeGuard(
        limit=limit,
        seconds=float("inf"),
        clock=clock,
        verify_frozen=verify_frozen,
        max_generations=limits["generations"],
        max_outbound=limits["outbound"],
        max_counted_input=limits["counted_input"],
        max_compacts=limits["compacts"],
    )
    guard.spent = Decimal(previous["spent_usd"])
    guard.attempts = {
        key: Decimal(value) for key, value in previous["retained_reservations"].items()
    }
    for key in core.COUNTERS:
        setattr(guard, key, previous[key])
    guard.inspect_request = lambda payload: None
    return guard


def remaining_schedule(
    schedule: list[dict[str, Any]], completed: list[dict[str, Any]], attempt: str
) -> list[dict[str, Any]]:
    actual = [item["trial"] for item in completed]
    if actual != [item["trial"] for item in schedule[: len(completed)]] or len(set(actual)) != len(
        actual
    ):
        raise ValueError("Retained complete trials must be an exact schedule prefix")
    if not re.fullmatch(r"[a-z0-9_-]{1,48}", attempt):
        raise ValueError("Invalid unique attempt suffix")
    return [
        {**item, "logical_trial": item["trial"], "trial": item["trial"] + "-attempt-" + attempt}
        for item in schedule[len(completed) :]
    ]


async def wait_decision(
    output: Path,
    opaque: str,
    question: str,
    case: str,
    policy: dict[str, Any],
    guard: ResumeGuard,
    *,
    monotonic: Callable[[], float] = time.monotonic,
) -> tuple[str | None, dict[str, Any], str]:
    import asyncio

    started = monotonic()
    path = output / "decisions" / (opaque + ".json")
    while not path.exists():
        guard.check({"model": "gpt-6-luna"})
        if monotonic() - started >= 300:
            guard.refuse("semantic review wait exceeded 300 seconds")
        await asyncio.sleep(1)
    guard.check({"model": "gpt-6-luna"})
    if monotonic() - started >= 300:
        guard.refuse("semantic review wait exceeded 300 seconds")
    decision = core.read_json(path)
    answer = core.validate_selection(decision, question, policy, case)
    return answer, decision, core.file_hash(path)


def output_path(name: str) -> Path:
    if not re.fullmatch(r"priority-probe-resume-[a-z0-9_-]{1,32}", name):
        raise ValueError("Invalid continuation output name")
    return core.OUTPUT_ROOT / name


def validate_authorization(
    directory: Path, manifest: dict[str, Any], ledger: dict[str, Any]
) -> None:
    if core.file_hash(REVOCATION_RECEIPT) != REVOCATION_RECEIPT_SHA256:
        raise ValueError("Time cancellation receipt changed")
    receipt = core.read_json(REVOCATION_RECEIPT)
    if (
        receipt["human_instruction"] != TIME_AUTHORIZATION
        or receipt["received_in_current_root_turn"] is not True
        or receipt["revoked"] != "absolute and elapsed time deadlines only"
        or Path(receipt["original_manifest"]).resolve() != (directory / "manifest.json").resolve()
        or receipt["original_manifest_sha256"] != core.file_hash(directory / "manifest.json")
        or receipt["interrupted_final_ledger_sha256"]
        != core.file_hash(directory / "final-ledger.json")
        or receipt["inherited_guard"] != ledger["guard"]
        or receipt["fixed_cumulative_counter_limits"] != fixed_limits(manifest["prior_guard"])
        or Decimal(receipt["fixed_probe_occupied_limit_usd"])
        != min(Decimal("8.00"), Decimal(manifest["prior_guard"]["occupied_usd"]) + Decimal("0.50"))
        or receipt["retain_completed_trials"] != [item["trial"] for item in ledger["completed"]]
        or receipt["remaining_logical_trials"]
        != len(manifest["schedule"]) - len(ledger["completed"])
        or receipt["logical_planned_max_replies"] != 48
        or receipt["already_incurred_partial_replies"]
        != ledger["effective_replies"] - sum(item["replies"] for item in ledger["completed"])
        or receipt["maximum_actual_replies_including_partial"] != 49
        or receipt["discard_partial_as_quality_sample"] is not True
    ):
        raise ValueError("Time cancellation receipt does not match this sealed batch")


def previous_carrier(directory: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    if directory.resolve().parent != core.OUTPUT_ROOT.resolve():
        raise ValueError("Previous batch must be directly in the owned probe root")
    manifest = core.read_json(directory / "manifest.json")
    ledger = core.read_json(directory / "final-ledger.json")
    validate_authorization(directory, manifest, ledger)
    if manifest.get("offline_only") is not False:
        raise ValueError("Previous batch must be a sealed paid batch")
    original_guard = core.carrier(manifest["ledger"], manifest["quality_lock"])
    if original_guard != manifest["prior_guard"] or ledger["prior_guard"] != original_guard:
        raise ValueError("Original probe baseline changed")
    core.verify_frozen(manifest)
    resume_guard(ledger["guard"], original_guard)
    schedule = manifest["schedule"]
    if schedule != core.next_schedule():
        raise ValueError("Original finite schedule changed")
    remaining_schedule(schedule, ledger["completed"], "validation")
    if type(ledger["effective_replies"]) is not int or ledger["effective_replies"] < sum(
        item["replies"] for item in ledger["completed"]
    ):
        raise ValueError("Invalid previous effective replies")
    for item in ledger["completed"]:
        trial = directory / item["trial"]
        required = [
            "quality-map.json",
            "formal-jd-before.json",
            "formal-jd.json",
            "formal-interviews.json",
            "fixed-source-contents-before.json",
            "fixed-source-contents.json",
        ]
        if not all((trial / name).is_file() for name in required):
            raise ValueError("A retained complete trial lacks formal exports")
        opaque = core.read_json(trial / "quality-map.json")["opaque_id"]
        if (
            not re.fullmatch(r"[0-9a-f]{32}", opaque)
            or not (directory / "blind-quality" / (opaque + ".json")).is_file()
        ):
            raise ValueError("A retained complete trial lacks its anonymous bundle")
    return manifest, ledger


def prepare(args: argparse.Namespace) -> Path:
    previous = Path(args.previous).resolve()
    old_manifest, ledger = previous_carrier(previous)
    runner = original_runner()
    driver = runner.shared()
    output = output_path(args.name)
    if output.exists():
        raise ValueError("Continuation output must be a fresh directory")
    attempt = uuid4().hex[:12]
    files = driver.freeze_files(
        [ROOT / path for path in old_manifest["files"]]
        + list(HERE.glob("priority-resume-*.py"))
        + list(HERE.glob("priority-resume-*.md")),
        root=ROOT,
        output=output,
    )
    completed_replies = sum(item["replies"] for item in ledger["completed"])
    partial_replies = ledger["effective_replies"] - completed_replies
    remaining = remaining_schedule(old_manifest["schedule"], ledger["completed"], attempt)
    max_fresh = sum(
        dict(zip(core.CASE_KEYS, old_manifest["cases"], strict=True))[item["case_key"]]["max_turns"]
        for item in remaining
    )
    if completed_replies + max_fresh > old_manifest["max_effective_replies"]:
        raise ValueError("Original planned effective reply cap changed")
    # Hash prior raw artifacts without interpreting any quality verdict/bundle body.
    retained_files = {
        str(path.resolve()): core.file_hash(path)
        for path in previous.rglob("*")
        if path.is_file() and "frozen" not in path.relative_to(previous).parts
    }
    manifest = {
        **copy.deepcopy(old_manifest),
        "files": files,
        "schedule": remaining,
        "offline_only": args.offline_only,
        "runtime": platform.python_version(),
        "name": args.name,
        "previous_directory": str(previous),
        "previous_files": retained_files,
        "previous_frozen_manifest_sha256": core.file_hash(previous / "manifest.json"),
        "previous_final_ledger_sha256": core.file_hash(previous / "final-ledger.json"),
        "time_limit_revocation_receipt": str(REVOCATION_RECEIPT.resolve()),
        "time_limit_revocation_receipt_sha256": REVOCATION_RECEIPT_SHA256,
        "probe_baseline_guard": old_manifest["prior_guard"],
        "prior_guard": ledger["guard"],
        "retained_completed": ledger["completed"],
        "prior_effective_replies": ledger["effective_replies"],
        "prior_partial_effective_replies": partial_replies,
        "planned_max_effective_replies": old_manifest["max_effective_replies"],
        "fresh_max_effective_replies": max_fresh,
        "actual_max_effective_replies": old_manifest["max_effective_replies"] + partial_replies,
        "fixed_cumulative_limits": fixed_limits(old_manifest["prior_guard"]),
        "fixed_occupied_usd_limit": str(
            min(
                Decimal("8.00"),
                Decimal(old_manifest["prior_guard"]["occupied_usd"]) + Decimal("0.50"),
            )
        ),
        "absolute_deadline_utc": None,
        "duration_limit_seconds": None,
        "time_limit_cancelled_authorization": TIME_AUTHORIZATION,
        "authorization_effect": (
            "Only time bounds cancelled; original cost, request/token caps, planned cases, "
            "arms and criteria unchanged. Interrupted trial re-created under a unique attempt; "
            "old raw data and its consumption retained, never a quality sample."
        ),
        "quality_bodies_read_for_retention": False,
        "semantic_review_wait_seconds": 300,
        "prepared_at": datetime.now(UTC).isoformat(),
    }
    runner.save_new(output / "manifest.json", manifest)
    verify(manifest)
    print(
        json.dumps(
            {
                "prepared": str(output),
                "retained_complete": len(ledger["completed"]),
                "fresh_trials": len(remaining),
                "fresh_max_replies": max_fresh,
                "actual_max_replies": manifest["actual_max_effective_replies"],
                "provider_calls": 0,
                "credential_read": False,
                "database_connected": False,
            }
        )
    )
    return output


def verify(manifest: dict[str, Any]) -> None:
    core.verify_frozen(manifest)
    if (
        manifest.get("time_limit_cancelled_authorization") != TIME_AUTHORIZATION
        or manifest.get("absolute_deadline_utc") is not None
        or manifest.get("duration_limit_seconds") is not None
    ):
        raise ValueError("Time cancellation metadata mismatch")
    for path, digest in manifest["previous_files"].items():
        if core.file_hash(path) != digest:
            raise ValueError("Prior sealed raw artifact changed")
    previous = Path(manifest["previous_directory"])
    old, ledger = previous_carrier(previous)
    if (
        core.file_hash(previous / "manifest.json") != manifest["previous_frozen_manifest_sha256"]
        or core.file_hash(previous / "final-ledger.json")
        != manifest["previous_final_ledger_sha256"]
    ):
        raise ValueError("Previous sealed carrier changed")
    baseline = old["prior_guard"]
    if (
        manifest["time_limit_revocation_receipt"] != str(REVOCATION_RECEIPT.resolve())
        or manifest["time_limit_revocation_receipt_sha256"] != REVOCATION_RECEIPT_SHA256
    ):
        raise ValueError("Time cancellation receipt changed")
    if (
        manifest["probe_baseline_guard"] != baseline
        or manifest["prior_guard"] != ledger["guard"]
        or manifest["retained_completed"] != ledger["completed"]
    ):
        raise ValueError("Original probe baseline/retained consumption changed")
    if manifest["fixed_cumulative_limits"] != fixed_limits(baseline) or Decimal(
        manifest["fixed_occupied_usd_limit"]
    ) != min(Decimal("8.00"), Decimal(baseline["occupied_usd"]) + Decimal("0.50")):
        raise ValueError("Original cumulative caps changed")
    for name in (
        "instructions",
        "common_focus",
        "reference_instructions",
        "tools",
        "cases",
        "reference_fixture",
        "reply_policy",
        "assessments",
        "model",
        "effort",
        "max_output_tokens",
        "provider",
        "service_tier",
        "notes_enabled",
        "ledger",
        "ledger_sha256",
        "quality_lock",
        "quality_lock_sha256",
        "additional_limits",
        "max_effective_replies",
    ):
        if manifest[name] != old[name]:
            raise ValueError("Frozen trial method changed: " + name)
    logical = [
        {key: value for key, value in item.items() if key not in {"logical_trial", "trial"}}
        | {"trial": item["logical_trial"]}
        for item in manifest["schedule"]
    ]
    if (
        logical != old["schedule"][len(ledger["completed"]) :]
        or len({item["trial"] for item in manifest["schedule"]}) != len(logical)
        or any(item["trial"] == item["logical_trial"] for item in manifest["schedule"])
    ):
        raise ValueError("Exact remaining schedule/unique attempts changed")
    cases = dict(zip(core.CASE_KEYS, old["cases"], strict=True))
    partial = ledger["effective_replies"] - sum(item["replies"] for item in ledger["completed"])
    expected = {
        "prior_effective_replies": ledger["effective_replies"],
        "prior_partial_effective_replies": partial,
        "planned_max_effective_replies": old["max_effective_replies"],
        "fresh_max_effective_replies": sum(
            cases[item["case_key"]]["max_turns"] for item in logical
        ),
        "actual_max_effective_replies": old["max_effective_replies"] + partial,
        "semantic_review_wait_seconds": 300,
        "quality_bodies_read_for_retention": False,
    }
    if any(
        type(manifest[key]) is not type(value) or manifest[key] != value
        for key, value in expected.items()
    ):
        raise ValueError("Continuation reply/selection metadata changed")
    resume_guard(manifest["prior_guard"], baseline)


def annotate_final(raw: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    value = copy.deepcopy(raw)
    logical = {item["trial"]: item["logical_trial"] for item in manifest["schedule"]}
    value["completed"] = [
        {**item, "logical_trial": logical[item["trial"]]} for item in raw["completed"]
    ]
    value.update(
        all_completed_logical_trials=[item["trial"] for item in manifest["retained_completed"]]
        + [logical[item["trial"]] for item in raw["completed"]],
        retained_completed=manifest["retained_completed"],
        new_effective_replies=raw["effective_replies"],
        retained_effective_replies=manifest["prior_effective_replies"],
        effective_replies=manifest["prior_effective_replies"] + raw["effective_replies"],
        probe_baseline_guard=manifest["probe_baseline_guard"],
        prior_partial_effective_replies=manifest["prior_partial_effective_replies"],
        planned_max_effective_replies=48,
        actual_max_effective_replies=48 + manifest["prior_partial_effective_replies"],
        absolute_deadline_utc=None,
        time_limit_cancelled_authorization=manifest["time_limit_cancelled_authorization"],
    )
    if value["effective_replies"] > value["actual_max_effective_replies"]:
        raise ValueError("Actual finite effective reply cap exceeded")
    return value


def execute(args: argparse.Namespace) -> None:
    output = output_path(args.name)
    manifest = core.read_json(output / "manifest.json")
    if manifest.get("offline_only") is not False or args.offline_only:
        raise ValueError("Offline preparation can never be executed")
    if manifest["name"] != args.name:
        raise ValueError("Continuation output identity mismatch")
    verify(manifest)
    runner = original_runner()
    original_save = runner.save_new

    def save(path: Path, value: Any) -> None:
        if path == runner.core.OUTPUT_ROOT / "priority-probe-execution-lease.json":
            path = runner.core.OUTPUT_ROOT / "priority-resume-execution-lease.json"
            value = {
                **value,
                "previous_final_ledger_sha256": manifest["previous_final_ledger_sha256"],
                "time_limit_cancelled_authorization": TIME_AUTHORIZATION,
            }
        elif path == output / "final-ledger.json":
            value = annotate_final(value, manifest)
        elif path == output / "started.json":
            value = {
                **value,
                "deadline": None,
                "time_limit_cancelled_authorization": TIME_AUTHORIZATION,
                "previous_stop_reason": manifest["prior_guard"]["stop_reason"],
                "probe_baseline_guard": manifest["probe_baseline_guard"],
            }
        elif path == output / "failure.json":
            value = {
                **value,
                "new_effective_replies": value["effective_replies"],
                "effective_replies": manifest["prior_effective_replies"]
                + value["effective_replies"],
            }
        original_save(path, value)

    runner.verify = verify
    runner.save_new = save
    runner.wait_decision = wait_decision
    runner.core.carried_guard = lambda prior, verify_frozen=lambda: None: resume_guard(
        prior, manifest["probe_baseline_guard"], verify_frozen=verify_frozen
    )
    # Original function body owns App/Writer/SDK lifecycle, source reads and trial loop.
    runner.execute(args)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["dry-run", "prepare", "execute"])
    parser.add_argument("--previous", required=True)
    parser.add_argument("--name", default="priority-probe-resume-01")
    parser.add_argument("--offline-only", action="store_true")
    args = parser.parse_args()
    if args.mode == "execute":
        execute(args)
    elif args.mode == "prepare":
        prepare(args)
    else:
        manifest, ledger = previous_carrier(Path(args.previous).resolve())
        print(
            json.dumps(
                {
                    "provider_calls": 0,
                    "credential_read": False,
                    "database_connected": False,
                    "retained_complete": len(ledger["completed"]),
                    "fresh_trials": len(manifest["schedule"]) - len(ledger["completed"]),
                    "prior_guard": ledger["guard"],
                    "fixed_cumulative_limits": fixed_limits(manifest["prior_guard"]),
                    "time_limit_cancelled_authorization": TIME_AUTHORIZATION,
                    "absolute_deadline_utc": None,
                    "duration_limit_seconds": None,
                },
                ensure_ascii=False,
            )
        )


if __name__ == "__main__":
    main()
