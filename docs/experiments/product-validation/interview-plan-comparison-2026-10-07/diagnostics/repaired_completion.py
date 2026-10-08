"""Complete the three mechanical omissions without changing the frozen first revision."""

import asyncio
import inspect
import json
import time
from datetime import UTC, datetime
from pathlib import Path

import repaired_comparison as original

PRIOR = original.REPAIRED_ROOT / "formal-repaired-v2"
STATE_SHA = "97130882dc7d8600a3a5a6ad2be182fb5bfb88ad3d1447dfe5a595842878805d"
MANIFEST_SHA = "bbd4bf7bd2db6e66525a488817e115bd0e589ccd09ff3c6e1b96097c50c362e7"
RETAINED = [*original.RETAINED, "warehouse-r1-P2", "course_admin-r1-P2", "warehouse-r2-P2"]
FRESH = ["warehouse-r2-P1", "course_admin-r2-P2", "course_admin-r2-P1"]
OUTPUT = original.ARTIFACT_ROOT / "repaired-completion"
STOP = "semantic review timeout; no employee answer disclosed"
READ_GATE = original.read_gate
FREEZE = original.freeze_revision
WAIT_SOURCE = None


def review_expired(started, *, monotonic=None, now=None):
    current = time.monotonic() if monotonic is None else monotonic
    return current - started >= 300 or (now or datetime.now(UTC)) >= original.DEADLINE


def validate_complete(claimed, results):
    complete = {
        name
        for name, result in results.items()
        if result["closure_submitted"]
        and result["turns"]
        and result["turns"][-1]["status"] == "completed"
    }
    if (
        not isinstance(claimed, list)
        or len(set(claimed)) != len(claimed)
        or set(claimed) != complete
    ):
        raise ValueError("Claimed complete cases differ from actual completed common closures")
    return list(claimed)


def read_gate():
    inherited, note = READ_GATE()
    state_path, manifest_path = PRIOR / "batch-state.json", PRIOR / "manifest.json"
    if (
        original.file_hash(state_path) != STATE_SHA
        or original.file_hash(manifest_path) != MANIFEST_SHA
    ):
        raise ValueError("Original final state or frozen manifest changed")
    original.verify_revision(original.read_json(manifest_path))
    state = original.read_json(state_path)
    if state["all_scheduled_cases"] != original.SCHEDULED or state["guard"]["stop_reason"] != STOP:
        raise ValueError("Only the observed bounded semantic timeout can continue")
    evidence = note["prior_evidence_sha256"]
    evidence[str(state_path)], evidence[str(manifest_path)] = STATE_SHA, MANIFEST_SHA
    proof = original.read_json(original.P1_PROOF)
    retained_paths = {Path(item["case"]).name: Path(item["case"]) for item in proof["cases"]}
    results = {}
    for name in original.SCHEDULED:
        path = retained_paths.get(name, PRIOR / name) / "result.json"
        if path.exists():
            results[name] = original.read_json(path)
            evidence[str(path)] = original.file_hash(path)
    if validate_complete(state["completed_cases"], results) != RETAINED:
        raise ValueError(
            "Mechanical retained cases differ from the bounded three-case continuation"
        )
    journal = PRIOR / "warehouse-r2-P1/provider-trace.jsonl"
    last = json.loads(journal.read_text(encoding="utf-8").splitlines()[-1])
    prior = original.validate_accounting(state["guard"], inherited)
    for key in prior:
        if key != "stop_reason" and last[key] != prior[key]:
            raise ValueError("Final received journal and saved cumulative accounting differ")
    evidence[str(journal)] = original.file_hash(journal)
    note.update(
        {
            "retained_completed_cases": RETAINED,
            "new_scheduled_cases": FRESH,
            "prior_accounting": prior,
            "prior_stop_reason": STOP,
            "semantic_wait": "at most 300 seconds, bounded by unchanged absolute deadline",
        }
    )
    return prior, note


def bind_wait(run_batch):
    source = inspect.getsource(run_batch.journey)
    before = "if time.monotonic() - review_started >= 120:"
    after_wait = 'if not (review_directory / "decision.json").exists():\n                break'
    if (
        source.count(before) != 1
        or source.count("await asyncio.sleep(1)") != 1
        or source.count(after_wait) != 1
    ):
        raise ValueError("Frozen semantic wait seam changed")
    revised = source.replace(before, "if _review_expired(review_started):", 1).replace(
        "await asyncio.sleep(1)", "await asyncio.sleep(_review_sleep())", 1
    )
    revised = revised.replace(
        after_wait,
        'if _review_expired(review_started) or not (review_directory / "decision.json").exists():\n'
        f"                guard.stop_reason = {STOP!r}\n                break",
        1,
    )
    run_batch.__dict__["_review_expired"] = review_expired
    run_batch.__dict__["_review_sleep"] = lambda: min(
        1, max(0, (original.DEADLINE - datetime.now(UTC)).total_seconds())
    )
    exec(compile(revised, str(Path(__file__)) + ":bounded-wait", "exec"), run_batch.__dict__)
    return revised


def freeze(path, note):
    data = FREEZE(path, note)
    for source in [Path(__file__), Path(__file__).with_name("test_repaired_completion.py")]:
        relative = source.relative_to(original.ROOT).as_posix()
        target = path.parent / "source-snapshot" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
        data["revision_source_sha256"][relative] = original.file_hash(source)
    data["revision"] = "Bounded completion after semantic timeout; 5 retained, 3 fresh"
    data["semantic_review_wait_seconds"] = 300
    if WAIT_SOURCE is None:
        raise ValueError("Bounded original HTTP journey has not been prepared")
    adapted = path.parent / "source-snapshot/bounded-semantic-wait-journey.py"
    adapted.write_text(WAIT_SOURCE, encoding="utf-8")
    data["bounded_wait_journey_sha256"] = original.file_hash(adapted)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


async def main():
    global WAIT_SOURCE

    import run_batch

    WAIT_SOURCE = bind_wait(run_batch)
    original.RETAINED, original.FRESH, original.REPAIRED_ROOT = RETAINED, FRESH, OUTPUT
    original.read_gate, original.freeze_revision = read_gate, freeze
    await original.main()


if __name__ == "__main__":
    asyncio.run(main(), loop_factory=asyncio.SelectorEventLoop)
