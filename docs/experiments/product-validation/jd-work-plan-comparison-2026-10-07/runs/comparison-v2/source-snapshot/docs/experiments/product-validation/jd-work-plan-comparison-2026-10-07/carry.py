"""One explicit mechanical revision: validate prior raw accounting and carry it intact."""

import hashlib
import json
from decimal import Decimal

STATE_KEYS = [
    "spent_usd",
    "occupied_usd",
    "retained_reservations",
    "generations",
    "compacts",
    "outbound",
    "counted_input",
    "stop_reason",
    "batch_deadline",
    "limit_usd",
]
COUNTERS = ["generations", "compacts", "outbound", "counted_input"]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def settled_cost(usage, pricing):
    if not isinstance(usage, dict):
        # Missing provider usage is an unsettled accounting state, not caller misuse.
        raise RuntimeError("Unknown usage cannot be carried")  # noqa: TRY004
    inputs, outputs = usage.get("input_tokens"), usage.get("output_tokens")
    if (
        type(inputs) is not int
        or type(outputs) is not int
        or min(inputs, outputs) < 0
        or usage.get("total_tokens") != inputs + outputs
    ):
        raise RuntimeError("Invalid usage cannot be carried")
    rates = pricing[
        "long_context"
        if inputs > pricing["long_context_above_tokens"]
        else "short_context"
    ]
    details = usage.get("input_tokens_details") or {}
    cached, writes = details.get("cached_tokens"), details.get("cache_write_tokens")
    if (
        type(cached) is int
        and type(writes) is int
        and min(cached, writes) >= 0
        and cached + writes <= inputs
    ):
        weighted = (
            (inputs - cached - writes) * Decimal(rates["input_usd_per_million"])
            + cached * Decimal(rates["cached_input_usd_per_million"])
            + writes * Decimal(rates["cache_write_usd_per_million"])
        )
    else:
        weighted = inputs * Decimal(rates["cache_write_usd_per_million"])
    return (weighted + outputs * Decimal(rates["output_usd_per_million"])) / 1000000


def audit_raw(directory, manifest):
    rows = []
    for path in directory.glob("*/*/provider-trace.jsonl"):
        rows.extend(
            json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
        )
    if not rows:
        raise RuntimeError("Prior revision has no raw provider accounting")
    rows.sort(key=lambda item: item["time"])
    admitted = {}
    received = {}
    for row in rows:
        target = (
            admitted
            if row["event"] == "admitted"
            else received
            if row["event"] == "received"
            else None
        )
        if target is not None:
            if row["attempt"] in target:
                raise RuntimeError("Duplicate prior accounting attempt")
            target[row["attempt"]] = row
    if not admitted or set(admitted) != set(received):
        raise RuntimeError("Prior revision has an unfinished outbound attempt")
    initial = manifest.get("carry", {}).get("final_guard", {})
    known = Decimal(initial.get("spent_usd", "0"))
    generations = compacts = 0
    for attempt, row in admitted.items():
        if (
            row.get("request", {}).get("model") != manifest["model"]
            or row["endpoint"] != received[attempt]["endpoint"]
        ):
            raise RuntimeError("Prior request model or settlement endpoint mismatch")
        known += settled_cost(received[attempt].get("usage"), manifest["pricing"])
        if row["endpoint"] == "/v1/responses":
            generations += 1
        elif row["endpoint"] == "/v1/responses/compact":
            compacts += 1
        else:
            raise RuntimeError("Unexpected admitted endpoint")
    counts = [row for row in rows if row["event"] == "count"]
    if any(
        type(row.get("input_tokens")) is not int or row["input_tokens"] < 0
        for row in counts
    ):
        raise RuntimeError("Invalid prior input count")
    last = next(row for row in reversed(rows) if "spent_usd" in row)
    state = {key: last[key] for key in STATE_KEYS}
    if (
        state["stop_reason"]
        or state["retained_reservations"]
        or Decimal(state["occupied_usd"]) != Decimal(state["spent_usd"])
    ):
        raise RuntimeError("Prior stopped or unknown reservation cannot be carried")
    expected = {
        "generations": initial.get("generations", 0) + generations,
        "compacts": initial.get("compacts", 0) + compacts,
        "outbound": initial.get("outbound", 0) + len(counts) + len(admitted),
        "counted_input": initial.get("counted_input", 0)
        + sum(row["input_tokens"] for row in counts),
    }
    if Decimal(state["spent_usd"]) != known or any(
        state[key] != value for key, value in expected.items()
    ):
        raise RuntimeError(
            "Prior raw accounting differs from latest cumulative witness"
        )
    return state


def verify_evidence(directory, evidence):
    for relative, expected in evidence.items():
        original = directory / relative
        if (
            not original.resolve().is_relative_to(directory.resolve())
            or not original.is_file()
            or sha(original) != expected
        ):
            raise RuntimeError("Prior accounting evidence missing or changed")


def load_carry(directory):
    path = directory / "interruption-accounting.json"
    report = read(path)
    evidence = report["artifact_sha256"]
    required = {
        "manifest.json",
        "ledger.json",
        *[
            path.relative_to(directory).as_posix()
            for path in directory.glob("*/*/provider-trace.jsonl")
        ],
    }
    if not required <= evidence.keys():
        raise RuntimeError("Prior interruption evidence omits accounting originals")
    verify_evidence(directory, evidence)
    manifest = read(directory / "manifest.json")
    if (
        report["source_manifest_sha256"] != sha(directory / "manifest.json")
        or report["pricing_basis"] != manifest["pricing"]
    ):
        raise RuntimeError("Prior interruption manifest or pricing mismatch")
    state = audit_raw(directory, manifest)
    if (
        state != report["final_guard"]
        or Decimal(report["independent_known_cost_usd"]) != Decimal(state["spent_usd"])
        or report["in_flight_admitted_attempts"]
        or report["unknown_usage_attempts"]
    ):
        raise RuntimeError("Prior interruption report differs from raw accounting")
    return {
        "origin_batch": directory.name,
        "report_sha256": sha(path),
        "artifact_sha256": evidence,
        "final_guard": state,
        "prior_limits": manifest["limits"],
        "prior_pricing": manifest["pricing"],
        "reason": "Plan V4A EOF format clarification after interrupted mechanism pilot; two fresh pilots, no old sample replacement",
    }


def verify_carry(runs, carry):
    directory = runs / carry["origin_batch"]
    if (
        directory.parent.resolve() != runs.resolve()
        or sha(directory / "interruption-accounting.json") != carry["report_sha256"]
    ):
        raise RuntimeError("Prior interruption report changed")
    verify_evidence(directory, carry["artifact_sha256"])


def seed_guard(guard, state):
    if state.get("stop_reason") or state.get("retained_reservations"):
        raise RuntimeError(
            "Prior stopped or unknown reservation cannot seed a fresh revision"
        )
    spent, occupied = Decimal(state["spent_usd"]), Decimal(state["occupied_usd"])
    if not spent.is_finite() or spent < 0 or occupied != spent or spent >= guard.limit:
        raise RuntimeError("Prior accounting is outside the same research budget")
    for key in COUNTERS:
        value = state[key]
        if type(value) is not int or value < 0 or value >= getattr(guard, "max_" + key):
            raise RuntimeError("Prior usage is outside the same research allowance")
        setattr(guard, key, value)
    guard.spent = spent
