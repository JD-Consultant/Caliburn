"""Read-only role/endpoint accounting using the frozen guard's settlement rule."""

import argparse
import importlib.util
import json
from collections import Counter, defaultdict
from decimal import Decimal
from hashlib import sha256
from pathlib import Path

BASE = Path(__file__).resolve().parents[2] / "data/full-interview-rag-2026-10-06/batch_guard.py"
PRICING = Path(__file__).resolve().parents[5] / "apps/api/src/caliburn/adapters/openai_pricing.py"


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def observe(directory, guard_type):
    trace = directory / "provider-trace.jsonl"
    admissions, receipts, counts, role_counts = {}, {}, {}, Counter()
    rows = [json.loads(line) for line in trace.read_text(encoding="utf-8").splitlines()]
    for row in rows:
        if row["event"] == "count":
            counts[row["input_sha256"]] = row.get("role")
            role_counts[str(row.get("role"))] += 1
        elif row["event"] == "admitted":
            attempt = row["attempt"]
            if attempt in admissions:
                raise ValueError("Duplicate admitted attempt")
            names = {item.get("name") for item in row.get("request", {}).get("tools", [])}
            request_kind = row["endpoint"]
            if request_kind == "/v1/responses/compact":
                # The pinned transport records compact_roles from its exact original count.
                # Public snapshots omit opaque content, so do not rehash them as originals.
                inferred = row.get("role") if row.get("role") in {"A", "Memory"} else None
                stage = "unavailable: compact substage; role is transport original-count binding"
            elif "revise_jd_profile" in names:
                inferred, stage = "A", "Consultant A"
            elif "create_work_situation" in names and "create_work_understanding" not in names:
                inferred, stage = "Memory", "Memory work_situation"
            elif "create_work_understanding" in names and "create_work_situation" not in names:
                inferred, stage = "Memory", "Memory work_understanding"
            else:
                inferred, stage = None, "unavailable: request tools do not establish role"
            known_role = inferred if inferred == row.get("role") else "unavailable"
            admissions[attempt] = {"row": row, "role": known_role, "stage": stage}
        elif row["event"] == "received":
            if row["attempt"] in receipts:
                raise ValueError("Duplicate received attempt; cannot silently choose one")
            receipts[row["attempt"]] = row
    groups = defaultdict(
        lambda: {
            "admitted": 0,
            "known_usage": 0,
            "unknown_usage": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "known_usage_usd": Decimal(0),
            "retained_usd": Decimal(0),
        }
    )
    details = []
    for attempt, admission in admissions.items():
        row, receipt = admission["row"], receipts.get(attempt)
        if receipt is not None and (
            receipt.get("role") != row.get("role") or receipt["endpoint"] != row["endpoint"]
        ):
            raise ValueError("Received role/endpoint contradicts admitted attempt")
        reserve = Decimal(row["retained_reservations"][attempt])
        calculator = guard_type(limit=Decimal("1000000"))
        calculator.attempts = {attempt: reserve}
        calculator.settle(attempt, receipt.get("usage") if receipt else None)
        known = attempt not in calculator.attempts
        key = (admission["role"], row["endpoint"], admission["stage"])
        group = groups[key]
        group["admitted"] += 1
        group["known_usage" if known else "unknown_usage"] += 1
        group["known_usage_usd"] += calculator.spent
        group["retained_usd"] += sum(calculator.attempts.values(), Decimal(0))
        if known:
            group["input_tokens"] += receipt["usage"]["input_tokens"]
            group["output_tokens"] += receipt["usage"]["output_tokens"]
        details.append(
            {
                "attempt": attempt,
                "role": admission["role"],
                "request_kind": row["endpoint"],
                "stage": admission["stage"],
                "received": receipt is not None,
                "known_usage": known,
                "known_usage_usd": str(calculator.spent),
                "retained_usd": str(sum(calculator.attempts.values(), Decimal(0))),
            }
        )
    known_cost = sum((item["known_usage_usd"] for item in groups.values()), Decimal(0))
    first = next(row for row in rows if row["event"] == "admitted")
    last = next(row for row in reversed(rows) if "spent_usd" in row)
    delta = Decimal(last["spent_usd"]) - Decimal(first["spent_usd"])
    if delta != known_cost:
        raise ValueError("Summed per-attempt settlement does not match the saved ledger delta")
    baseline = {
        key: value
        for key, value in first["retained_reservations"].items()
        if key != first["attempt"]
    }
    return {
        "case_path": str(directory),
        "trace_sha256": sha256(trace.read_bytes()).hexdigest(),
        "count_requests_by_recorded_role": dict(role_counts),
        "groups": [
            {
                "role": key[0],
                "request_kind": key[1],
                "stage": key[2],
                **{k: str(v) if isinstance(v, Decimal) else v for k, v in value.items()},
            }
            for key, value in sorted(groups.items())
        ],
        "known_usage_usd": str(known_cost),
        "saved_ledger_delta_usd": str(delta),
        "ledger_delta_exact": True,
        "inherited_unknown_reservations": baseline,
        "final_global_reservations": last["retained_reservations"],
        "attempts": details,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location("frozen_settlement", BASE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result = {
        "cases": [observe(case, module.BatchGuard) for case in args.case],
        "method": (
            "Join admitted/received by attempt; verify recorded role with actual tool names "
            "or the pinned transport recorded original-count compact role; replay existing "
            "guard.settle on observed usage only"
        ),
        "source_hashes": {
            str(path): sha256(path.read_bytes()).hexdigest()
            for path in [Path(__file__), BASE, PRICING]
        },
        "limits": (
            "No key/provider/HTTP/DB/JD/blind review. Usage fees are estimates under the pinned "
            "guard rate table, not invoices. Counts are provider requests, not Memory pipeline "
            "executions. input_tokens route has no usage fee recorded and is not claimed free. "
            "Global inherited reservations are listed but not charged to these case costs. "
            "Compact role follows the transport exact original input-count binding; public "
            "snapshots omit opaque bytes, so this observer cannot independently rehash that "
            "original binding or identify pre-work versus mid-work from cost records alone."
        ),
    }
    with args.output.open("x", encoding="utf-8") as output:
        json.dump(result, output, ensure_ascii=False, indent=2)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "output_sha256": sha256(args.output.read_bytes()).hexdigest(),
                "cases": [
                    {k: case[k] for k in ["case_path", "known_usage_usd", "ledger_delta_exact"]}
                    for case in result["cases"]
                ],
            }
        )
    )


if __name__ == "__main__":
    main()
