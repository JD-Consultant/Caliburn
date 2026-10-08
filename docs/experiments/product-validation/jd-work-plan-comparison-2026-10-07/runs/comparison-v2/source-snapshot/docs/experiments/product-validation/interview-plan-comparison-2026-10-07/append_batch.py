"""Explicit bounded new batch carrying the interrupted batch's occupied budget.

Does not alter the original frozen harness or resume its unknown provider call.
The original request remains reserved. Run only after the isolated runtime probe
has passed and the root agent has released the paid continuation.
"""

import asyncio
import json
import platform
import time
from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256

import guard as experiment_guard
import run_batch
from append_stream import OwnedObservedStream
from guard import BatchGuard
from manifest import HERE, LIMITS, source_hashes

DEADLINE = datetime.fromisoformat("2026-10-07T01:30:34+00:00")
RUNTIME_VERSION = "3.14.7"
BASE_FREEZE = run_batch.freeze


def prior_evidence():
    prior = HERE / "formal"
    audit = json.loads((prior / "interruption-audit.json").read_text(encoding="utf-8"))
    manifest = json.loads((prior / "manifest.json").read_text(encoding="utf-8"))
    journal = prior / "warehouse-r1-P1/provider-trace.jsonl"
    rows = [
        json.loads(line) for line in journal.read_text(encoding="utf-8").splitlines()
    ]
    last = rows[-1]
    guard = audit["guard"]
    for key in [
        "spent_usd",
        "occupied_usd",
        "retained_reservations",
        "generations",
        "compacts",
        "outbound",
        "counted_input",
    ]:
        if guard[key] != last[key]:
            raise RuntimeError("Prior accounting disagrees with the original journal")
    original = manifest["source_sha256"]
    current = source_hashes()
    if any(current.get(path) != expected for path, expected in original.items()):
        raise RuntimeError("Original production, guides or frozen harness changed")
    if LIMITS["formal"] != manifest["limits"]:
        raise RuntimeError("Continuation may not extend an original finite boundary")
    return guard, {
        "prior_manifest_sha256": sha256(
            (prior / "manifest.json").read_bytes()
        ).hexdigest(),
        "prior_journal_sha256": sha256(journal.read_bytes()).hexdigest(),
        "prior_interruption_sha256": sha256(
            (prior / "interruption-audit.json").read_bytes()
        ).hexdigest(),
        "prior_accounting": guard,
        "original_deadline_utc": DEADLINE.isoformat(),
        "new_cases": "eight fresh paired journeys; interrupted attempt retained separately",
    }


def carried_guard(prior, *, now=None, clock=time.monotonic, **kwargs):
    anchor = clock()
    now = now or datetime.now(timezone.utc)
    remaining = (DEADLINE - now).total_seconds()
    if remaining <= 0:
        raise RuntimeError("Original batch deadline expired")
    guard = BatchGuard(**{**kwargs, "seconds": remaining, "clock": clock})
    guard.spent = Decimal(prior["spent_usd"])
    guard.attempts = {
        key: Decimal(value) for key, value in prior["retained_reservations"].items()
    }
    if guard.occupied != Decimal(prior["occupied_usd"]):
        raise RuntimeError("Prior reserve was released or changed")
    guard.generations = prior["generations"]
    guard.compacts = prior["compacts"]
    guard.outbound = prior["outbound"]
    guard.counted_input = prior["counted_input"]
    guard.started = anchor
    return guard


async def main():
    if platform.python_version() != RUNTIME_VERSION:
        raise RuntimeError(
            "This continuation requires the independently verified runtime"
        )
    prior, note = prior_evidence()

    def freeze(phase, destination):
        data = BASE_FREEZE(phase, destination)
        data["continuation"] = note
        data["production_runtime_unchanged"] = (
            "same CPython3.14.7 and locked dependencies/model/tools/guides"
        )
        data["experimental_delta"] = (
            "OwnedObservedStream owns and closes the consumed iterator; byte-transparent observation; "
            "original interrupted accounting and absolute deadline carried"
        )
        destination.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return data

    run_batch.freeze = freeze
    run_batch.BatchGuard = lambda **kwargs: carried_guard(prior, **kwargs)
    experiment_guard.ObservedStream = OwnedObservedStream
    await run_batch.main()


if __name__ == "__main__":
    asyncio.run(main(), loop_factory=asyncio.SelectorEventLoop)
