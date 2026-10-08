"""Explicit unstarted-batch revision; prior ledgers and source bytes stay intact."""

import json
import time
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
ROOT = HERE.parents[3]
ARTIFACT_ROOT = Path(
    "C:/Users/chenb/.codex/visualizations/2026/10/06/"
    "01a11182-e198-7652-87d2-d90d10463ed1/caliburn-intplan-comparison"
)
DISK_AUDIT = ARTIFACT_ROOT / "recovery-disk-complete/disk-audit-v2.json"
HISTORICAL_DEADLINE = datetime.fromisoformat("2026-10-07T04:30:34+00:00")
DEADLINE = datetime.fromisoformat("2026-10-07T08:30:34+00:00")
LIMITS = {
    "limit_usd": "8.00",
    "seconds": 39600,
    "max_generations": 3000,
    "max_compacts": 32,
    "max_outbound": 7000,
    "max_counted_input": 180000000,
    "turns": 20,
}
RESOURCE_STOPS = {
    "batch counted input token limit reached",
    "batch generation attempt limit reached",
    "batch outbound attempt limit reached",
    "batch compact attempt limit reached",
    "batch deadline reached",
    "batch budget reached before compact",
    "batch budget reached",
}

SCHEDULED = [
    f"{profile}-r{repeat}-{group}"
    for repeat in [1, 2]
    for profile in ["warehouse", "course_admin"]
    for group in (["P1", "P2"] if repeat == 1 else ["P2", "P1"])
]


def validate_accounting(prior, inherited):
    """Keep cumulative consumption and every inherited unknown reservation."""
    counters = ["generations", "compacts", "outbound", "counted_input"]
    try:
        for state in [inherited, prior]:
            spent = Decimal(state["spent_usd"])
            occupied = Decimal(state["occupied_usd"])
            reserves = {
                key: Decimal(value) for key, value in state["retained_reservations"].items()
            }
            if (
                not spent.is_finite()
                or not occupied.is_finite()
                or spent < 0
                or any(not value.is_finite() or value <= 0 for value in reserves.values())
                or occupied != spent + sum(reserves.values(), Decimal(0))
                or any(type(state[key]) is not int or state[key] < 0 for key in counters)
            ):
                raise ValueError("Invalid accounting state")
        if (
            Decimal(prior["spent_usd"]) < Decimal(inherited["spent_usd"])
            or any(prior[key] < inherited[key] for key in counters)
            or any(
                prior["retained_reservations"].get(key) != amount
                for key, amount in inherited["retained_reservations"].items()
            )
        ):
            raise ValueError("Prior accounting consumption or reserve was reset")
    except (KeyError, TypeError, AttributeError, InvalidOperation) as error:
        raise ValueError("Invalid accounting evidence") from error
    return prior


def remaining_cases(results):
    """Preserve completed bounded interviews without consulting their quality."""
    if not isinstance(results, dict):
        raise ValueError("Ambiguous completion evidence")
    if set(results) - set(SCHEDULED):
        raise ValueError("Unknown completion case")
    remaining = []
    for name in SCHEDULED:
        if name not in results:
            remaining.append(name)
            continue
        result = results[name]
        if not isinstance(result, dict):
            raise ValueError("Ambiguous completion evidence")
        closure = result.get("closure_submitted")
        turns = result.get("turns")
        if type(closure) is not bool or not isinstance(turns, list):
            raise ValueError("Ambiguous completion evidence")
        if not turns:
            if closure:
                raise ValueError("Ambiguous completion evidence")
            remaining.append(name)
            continue
        last = turns[-1]
        if not isinstance(last, dict) or last.get("status") not in {
            "completed",
            "failed",
            "cancelled",
            "paused",
            "observation_timeout",
        }:
            raise ValueError("Ambiguous completion evidence")
        if not (closure and last["status"] == "completed"):
            remaining.append(name)
    return remaining


def carried_guard(prior, *, verify_frozen=lambda: None, now=None, clock=time.monotonic):
    anchor = clock()
    now = now or datetime.now(UTC)
    remaining = (DEADLINE - now).total_seconds()
    if remaining <= 0:
        raise RuntimeError("Supplement deadline expired")
    validate_accounting(prior, prior)
    if Decimal(prior["occupied_usd"]) >= Decimal(LIMITS["limit_usd"]):
        raise ValueError("Supplement USD budget exhausted")
    for key, bound in [
        ("generations", "max_generations"),
        ("compacts", "max_compacts"),
        ("outbound", "max_outbound"),
        ("counted_input", "max_counted_input"),
    ]:
        if prior[key] >= LIMITS[bound]:
            raise ValueError(f"Supplement {key} exhausted")
    import sys

    sys.path.insert(0, str(HERE))
    from guard import BatchGuard

    guard = BatchGuard(
        limit=Decimal(LIMITS["limit_usd"]),
        seconds=remaining,
        clock=clock,
        max_generations=LIMITS["max_generations"],
        max_compacts=LIMITS["max_compacts"],
        max_outbound=LIMITS["max_outbound"],
        max_counted_input=LIMITS["max_counted_input"],
        verify_frozen=verify_frozen,
    )
    guard.spent = Decimal(prior["spent_usd"])
    guard.attempts = {key: Decimal(value) for key, value in prior["retained_reservations"].items()}
    for key in ["generations", "compacts", "outbound", "counted_input"]:
        setattr(guard, key, prior[key])
    guard.started = anchor
    return guard


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def file_hash(path):
    return sha256(path.read_bytes()).hexdigest()


def read_disk_audit(prior, state, inherited, files):
    """Only the exact disk-full incident may supplement its immutable journal."""
    audit = read_json(DISK_AUDIT)
    metadata_ref = audit["recovery_metadata"]
    metadata_path = Path(metadata_ref["path"])
    metadata = read_json(metadata_path)
    if (
        type(audit["version"]) is not int
        or audit["version"] != 1
        or audit["resource_interruption"] != "artifact_disk_full"
        or audit["prior_batch_path"] != str(prior.resolve())
        or audit["prior_accounting"] != state
        or audit["absolute_deadline_utc"] != HISTORICAL_DEADLINE.isoformat()
        or file_hash(metadata_path) != metadata_ref["sha256"]
        or metadata["credential_read"] is not False
        or metadata["provider_calls"] != 0
        or metadata["prior_server_closed"] is not True
        or metadata["recovery_server_closed"] is not True
        or metadata["prior_process_exit_code"] != 1
        or metadata["resource_interruption"] != "artifact_disk_full"
        or metadata["recovered_turn_status"] != "failed"
        or metadata["closure_submitted"] is not False
        or metadata["execution_status_counts"].get("active", 0) != 0
    ):
        raise ValueError("Contradictory disk recovery evidence")
    for path in files:
        reference = audit["original_evidence"].get(str(path.resolve()))
        if (
            reference is None
            or file_hash(path) != reference["sha256"]
            or file_hash(Path(reference["copy"])) != reference["sha256"]
        ):
            raise ValueError("Disk recovery does not preserve the original evidence")
    missing = audit["missing_case_completion"]
    if len(missing) != 1:
        raise ValueError("Ambiguous disk completion recovery")
    for name, result in missing.items():
        source = Path(result["source"])
        if (
            name not in SCHEDULED
            or result["closure_submitted"] is not False
            or result["turns"] != [{"turn": 12, "status": "failed"}]
            or read_json(source)["status"] != "failed"
            or file_hash(source) != result["source_sha256"]
        ):
            raise ValueError("Contradictory disk completion recovery")
        files.append(source)
    extra_reserves = {
        key: amount
        for key, amount in state["retained_reservations"].items()
        if key not in inherited["retained_reservations"]
    }
    basis = audit["reserve_basis"]
    reserve = (
        Decimal(basis["counted_input"]) * Decimal("0.125")
        + Decimal(basis["max_output_tokens"]) * Decimal("0.5")
    ) / 1000000
    if (
        basis != {"counted_input": 29361, "max_output_tokens": 16384}
        or len(extra_reserves) != 1
        or extra_reserves != audit["unjournaled_reservations"]
        or Decimal(next(iter(extra_reserves.values()))) != reserve
    ):
        raise ValueError("Contradictory disk reserve evidence")
    files.extend([DISK_AUDIT, metadata_path])
    return audit


def read_prior(prior, *, current_sources=None):
    """Read a finished batch's original ledgers without accessing any JD body."""
    state_path = prior / "batch-state.json"
    if not state_path.exists():
        raise ValueError("Prior batch has no final state")
    state = read_json(state_path)
    if not isinstance(state, dict) or state.get("all_scheduled_cases") != SCHEDULED:
        raise ValueError("Prior batch has not saved its final schedule")
    manifest_path = prior / "manifest.json"
    manifest = read_json(manifest_path)
    if current_sources is None:
        from manifest import source_hashes

        current_sources = source_hashes()
    if current_sources != manifest["source_sha256"]:
        raise ValueError("Original production, guides or harness source changed")
    inherited = manifest["continuation"]["prior_accounting"]
    accounting = validate_accounting(state["guard"], inherited)
    results = {}
    files = [state_path, manifest_path]
    missing_results = []
    for name in SCHEDULED:
        case = prior / name
        if not case.exists():
            continue
        result_path = case / "result.json"
        if not result_path.exists():
            missing_results.append(name)
            continue
        results[name] = read_json(result_path)
        files.append(result_path)
    rows = []
    for path in sorted(prior.glob("*/provider-trace.jsonl")):
        if path.parent.name not in SCHEDULED:
            raise ValueError("Unknown journal case")
        case_rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        if any(row.get("case") != path.parent.name for row in case_rows):
            raise ValueError("Journal scope does not match its case")
        rows.extend(case_rows)
        files.append(path)
    disk = None
    if missing_results:
        if not DISK_AUDIT.exists():
            raise ValueError("Started case has missing completion evidence")
        disk = read_disk_audit(prior, accounting, inherited, files)
        if set(missing_results) != set(disk["missing_case_completion"]):
            raise ValueError("Disk audit does not explain every missing completion")
        results.update(disk["missing_case_completion"])
    todo = remaining_cases(results)
    if todo and accounting.get("stop_reason") not in RESOURCE_STOPS and disk is None:
        raise ValueError("Prior batch lacks a supported resource stop")
    rows.sort(key=lambda row: row["time"])
    admitted = [row for row in rows if row["event"] == "admitted"]
    received = [row for row in rows if row["event"] == "received"]
    admits = {row["attempt"]: row for row in admitted}
    receipts = {row["attempt"]: row for row in received}
    if (
        len(admits) != len(admitted)
        or len(receipts) != len(received)
        or set(receipts) - set(admits)
    ):
        raise ValueError("Duplicate or foreign journal attempt")
    for attempt in admits:
        receipt = receipts.get(attempt)
        retained = attempt in accounting["retained_reservations"]
        if (receipt is None or receipt.get("usage") is None) != retained:
            raise ValueError("Journal usage and retained reservation disagree")
    expected = {
        "generations": inherited["generations"]
        + sum(row["endpoint"] == "/v1/responses" for row in admitted),
        "compacts": inherited["compacts"]
        + sum(row["endpoint"] == "/v1/responses/compact" for row in admitted),
        "counted_input": inherited["counted_input"]
        + sum(row["input_tokens"] for row in rows if row["event"] == "count"),
    }
    delta = disk["conservative_unjournaled_counter_delta"] if disk else {}
    if any(accounting[key] != value + delta.get(key, 0) for key, value in expected.items()):
        raise ValueError("Final counters disagree with original journals")
    last_spent = received[-1]["spent_usd"] if received else inherited["spent_usd"]
    if Decimal(last_spent) != Decimal(accounting["spent_usd"]):
        raise ValueError("Final spent disagrees with original journal")
    states = [row for row in rows if "outbound" in row]
    if states:
        last = states[-1]
        expected_outbound = last["outbound"] + sum(
            row["event"] == "count" and row["time"] > last["time"] for row in rows
        )
    else:
        expected_outbound = inherited["outbound"] + sum(row["event"] == "count" for row in rows)
    gap = accounting["outbound"] - expected_outbound
    # These two source branches increment outbound, then reject the returned count
    # before writing a count event. No billed generation is hidden by this gap.
    if disk:
        if (
            delta != {"generations": 1, "compacts": 0, "counted_input": 0, "outbound": 1}
            or disk["journal_known_counters"] != {**expected, "outbound": expected_outbound}
            or gap != 1
            or Decimal(disk["last_received_spent_usd"]) != Decimal(last_spent)
            or disk["journal_attempts"] != {"admitted": len(admitted), "received": len(received)}
        ):
            raise ValueError("Disk audit contradicts exact journal reconstruction")
    elif gap != 0 and not (
        gap == 1
        and accounting["stop_reason"]
        in {"batch counted input token limit reached", "batch deadline reached"}
    ):
        raise ValueError("Final outbound counter is ambiguous")
    note = {
        "prior_batch": prior.name,
        "prior_accounting": accounting,
        "prior_stop_reason": "artifact_disk_full" if disk else accounting["stop_reason"],
        "retained_completed_cases": [name for name in SCHEDULED if name not in todo],
        "new_scheduled_cases": todo,
        "prior_evidence_sha256": {str(path.resolve()): file_hash(path) for path in files},
        "outbound_reconstruction": {
            "journal_known": expected_outbound,
            "unrecorded_reserved_generation_attempts": gap if disk else 0,
            "unrecorded_rejected_count_attempts": 0 if disk else gap,
        },
    }
    if disk:
        note["disk_recovery"] = disk
    return accounting, note, todo


def verify_sources(data, base_verify):
    base_verify(data)
    for path, expected in data["supplement_source_sha256"].items():
        if file_hash(ROOT / path) != expected:
            raise RuntimeError("Frozen supplement source changed")
    for path, expected in data["continuation"]["prior_evidence_sha256"].items():
        if file_hash(Path(path)) != expected:
            raise RuntimeError("Frozen prior accounting evidence changed")


def freeze_supplement(destination, note, base_freeze):
    data = base_freeze("formal", destination)
    extras = [
        Path(__file__).resolve(),
        Path(__file__).with_name("completion_batch.py"),
        Path(__file__).with_name("test_completion_v2.py"),
        Path(__file__).with_name("test_completion_batch.py"),
        Path(__file__).with_name("test_completion_gates.py"),
        Path(__file__).with_name("recover_disk.py"),
        Path(__file__).with_name("audit_disk.py"),
        Path(__file__).with_name("outbound-scope-proof-v2.md"),
        HERE / "diagnostics/case1-operational-estimate.json",
    ]
    hashes = {}
    for path in extras:
        relative = str(path.relative_to(ROOT)).replace("\\", "/")
        contents = path.read_bytes()
        hashes[relative] = sha256(contents).hexdigest()
        target = destination.parent / "source-snapshot" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(contents)
    data.update(
        {
            "limits": LIMITS,
            "absolute_deadline_utc": DEADLINE.isoformat(),
            "deadline_revision": {
                "version": 2,
                "previous_absolute_deadline_utc": HISTORICAL_DEADLINE.isoformat(),
                "new_absolute_deadline_utc": DEADLINE.isoformat(),
                "reason": (
                    "Human confirmed synthetic payload/OpenAI destination after approval wait; "
                    "root explicitly revised this never-started batch deadline"
                ),
                "counters_and_reservations_reset": False,
                "seconds_metadata_semantics": (
                    "39600 is the total 11h from original formal freeze, not a fresh timer; "
                    "actual guard.seconds is absolute deadline minus sampled wall time, "
                    "with monotonic anchor taken before construction"
                ),
            },
            "continuation": note,
            "supplement_source_sha256": hashes,
            "production_runtime_unchanged": (
                "same CPython3.14.7, locked dependencies/model/tools/guides/arm/45K pressure policy"
            ),
            "experimental_deltas": [
                "existing OwnedObservedStream iterator ownership; original bytes unchanged",
                "explicit aggregate caps and absolute deadline; prior counters/reserves retained",
                "only artifact output binding points to approved C root",
                "immutable disk-full audit explains one unjournaled reserved admission",
            ],
            "formal_limit_calibration": (
                "Root-approved aggregate supplement after complete case1: "
                "USD8/3000gen/7000out/180Mcounted/32compact; absolute "
                "2026-10-07T08:30:34Z revision2; original caps and accounting untouched"
            ),
            "output_routes": {
                "batch": str(destination.parent),
                "reviews": str(ARTIFACT_ROOT / "reviews"),
                "blind_input": str(ARTIFACT_ROOT / "blind-input"),
                "source_here": str(HERE),
                "source_root": str(ROOT),
            },
            "case1_operational_estimate": {
                "path": str(HERE / "diagnostics/case1-operational-estimate.json"),
                "sha256": file_hash(HERE / "diagnostics/case1-operational-estimate.json"),
                "source_result_sha256": file_hash(
                    HERE / "formal-append/warehouse-r1-P1/result.json"
                ),
                "source_journal_sha256": file_hash(
                    HERE / "formal-append/warehouse-r1-P1/provider-trace.jsonl"
                ),
            },
            "selection_policy": (
                "retain every completed closure regardless of Memory/quality; "
                "fresh only resource-interrupted or unstarted original cases"
            ),
        }
    )
    evidence_copies = {}
    for source, expected in note["prior_evidence_sha256"].items():
        path = Path(source)
        target = destination.parent / "prior-evidence" / file_hash(path) / path.name
        target.parent.mkdir(parents=True, exist_ok=True)
        contents = path.read_bytes()
        if sha256(contents).hexdigest() != expected:
            raise RuntimeError("Prior evidence changed while freezing")
        target.write_bytes(contents)
        evidence_copies[source] = str(target)
    data["prior_evidence_snapshot"] = evidence_copies
    destination.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


def bind_output_routes(run_batch, experiment_guard, *, runtime):
    """Keep source anchors in S while the reused driver's output alias uses C."""
    if (
        runtime != "3.14.7"
        or Path(run_batch.__file__).resolve().parent != HERE
        or Path(experiment_guard.__file__).resolve().parent != HERE
        or run_batch.ROOT != ROOT
        or run_batch.HERE != HERE
    ):
        raise RuntimeError("Supplement runtime or imported harness source changed")
    # run_batch.HERE is only used for reviews/blind output during run_case/journey.
    # manifest.HERE, conditional_answers.HERE and run_batch.ROOT keep original S.
    run_batch.HERE = ARTIFACT_ROOT


async def main():
    import argparse
    import platform
    import re
    import socket
    import sys

    sys.path.insert(0, str(HERE))
    import guard as experiment_guard
    import run_batch
    from append_stream import OwnedObservedStream
    from manifest import freeze, verify

    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-name", default="formal-supplement-v2")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if re.fullmatch(r"[a-z][a-z0-9_-]{0,60}", args.batch_name) is None:
        raise ValueError("Invalid supplement directory name")
    bind_output_routes(run_batch, experiment_guard, runtime=platform.python_version())
    prior, note, todo = read_prior(HERE / "formal-append")
    with socket.socket() as probe:
        probe.settimeout(0.5)
        if probe.connect_ex(("127.0.0.1", 8177)) == 0:
            raise RuntimeError("Prior product server is still active")
    note["prior_server_shutdown"] = {
        "loopback_port": 8177,
        "listener_present": False,
        "observed_at": datetime.now(UTC).isoformat(),
    }
    if args.dry_run or not todo:
        print(
            json.dumps(
                {
                    "provider_calls": 0,
                    "credential_read": False,
                    "remaining_cases": todo,
                    "prior_accounting": prior,
                    "limits": LIMITS,
                    "deadline": DEADLINE.isoformat(),
                },
                ensure_ascii=False,
            )
        )
        return
    directory = ARTIFACT_ROOT / args.batch_name
    directory.mkdir()
    data = freeze_supplement(directory / "manifest.json", note, freeze)
    guard = carried_guard(prior, verify_frozen=lambda: verify_sources(data, verify))
    experiment_guard.ObservedStream = OwnedObservedStream
    verify_sources(data, verify)
    print(
        json.dumps(
            {
                "launch_directory": str(directory),
                "manifest_sha256": file_hash(directory / "manifest.json"),
            }
        ),
        flush=True,
    )
    processed = []
    completed = list(note["retained_completed_cases"])
    try:
        for name in todo:
            if guard.stop_reason:
                break
            profile, repeat, group = name.rsplit("-", 2)
            await run_batch.run_case(
                "formal", profile, group, int(repeat[1:]), directory / name, guard, data, 20
            )
            processed.append(name)
            result = read_json(directory / name / "result.json")
            if name not in remaining_cases({name: result}):
                completed.append(name)
            run_batch.save(
                directory / "batch-state.json",
                {
                    "completed_cases": completed,
                    "processed_new_cases": processed,
                    "guard": guard.state(),
                },
            )
    finally:
        run_batch.save(
            directory / "batch-state.json",
            {
                "completed_cases": completed,
                "processed_new_cases": processed,
                "all_scheduled_cases": SCHEDULED,
                "new_scheduled_cases": todo,
                "guard": guard.state(),
            },
        )


if __name__ == "__main__":
    import asyncio

    asyncio.run(main(), loop_factory=asyncio.SelectorEventLoop)
