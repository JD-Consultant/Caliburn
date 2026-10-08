"""Preserve the exact disk-full ledgers and conservative unknown reservation."""

import json
import shutil
from decimal import Decimal
from pathlib import Path

from completion_batch import HERE, file_hash, read_json, validate_accounting

OUTPUT = Path(
    "C:/Users/chenb/.codex/visualizations/2026/10/06/"
    "01a11182-e198-7652-87d2-d90d10463ed1/caliburn-intplan-comparison/recovery-disk-complete"
)


def main():
    prior = HERE / "formal-append"
    raw = read_json(prior / "batch-state.json")
    inherited = read_json(prior / "manifest.json")["continuation"]["prior_accounting"]
    state = validate_accounting(raw["guard"], inherited)
    rows = []
    originals = [prior / "batch-state.json", prior / "manifest.json"]
    originals.extend(sorted(prior.glob("*/provider-trace.jsonl")))
    originals.extend(sorted(prior.glob("*/result.json")))
    for path in prior.glob("*/provider-trace.jsonl"):
        rows.extend(json.loads(line) for line in path.read_text(encoding="utf-8").splitlines())
    rows.sort(key=lambda row: row["time"])
    admitted = [row for row in rows if row["event"] == "admitted"]
    received = [row for row in rows if row["event"] == "received"]
    known = {
        "generations": inherited["generations"]
        + sum(row["endpoint"] == "/v1/responses" for row in admitted),
        "compacts": inherited["compacts"]
        + sum(row["endpoint"] == "/v1/responses/compact" for row in admitted),
        "counted_input": inherited["counted_input"]
        + sum(row["input_tokens"] for row in rows if row["event"] == "count"),
        "outbound": [row for row in rows if "outbound" in row][-1]["outbound"],
    }
    last_state = [row for row in rows if "outbound" in row][-1]
    known["outbound"] += sum(
        row["event"] == "count" and row["time"] > last_state["time"] for row in rows
    )
    delta = {key: state[key] - amount for key, amount in known.items()}
    assert delta == {"generations": 1, "compacts": 0, "counted_input": 0, "outbound": 1}
    assert Decimal(received[-1]["spent_usd"]) == Decimal(state["spent_usd"])
    new = {
        key: amount
        for key, amount in state["retained_reservations"].items()
        if key not in inherited["retained_reservations"]
    }
    assert len(new) == 1
    reserve = (Decimal(29361) * Decimal("0.125") + Decimal(16384) * Decimal("0.5")) / 1000000
    assert Decimal(next(iter(new.values()))) == reserve
    copies = {}
    for path in originals:
        target = OUTPUT / "original-bytes" / path.relative_to(HERE)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            assert file_hash(target) == file_hash(path)
        else:
            shutil.copyfile(path, target)
        copies[str(path.resolve())] = {"copy": str(target), "sha256": file_hash(path)}
    metadata = OUTPUT / "recovery-metadata.json"
    recovered = read_json(metadata)
    assert recovered["prior_process_exit_code"] == 1
    assert recovered["prior_server_closed"] and recovered["recovery_server_closed"]
    assert recovered["recovered_turn_status"] == "failed"
    assert not recovered["closure_submitted"] and recovered["provider_calls"] == 0
    audit = {
        "version": 1,
        "resource_interruption": "artifact_disk_full",
        "prior_batch_path": str(prior.resolve()),
        "prior_accounting": state,
        "journal_known_counters": known,
        "conservative_unjournaled_counter_delta": delta,
        "delta_from_last_journal_guard_state": {
            key: state[key] - last_state[key]
            for key in ["generations", "compacts", "counted_input", "outbound"]
        },
        "unjournaled_reservations": new,
        "reserve_basis": {"counted_input": 29361, "max_output_tokens": 16384},
        "last_received_spent_usd": received[-1]["spent_usd"],
        "journal_attempts": {"admitted": len(admitted), "received": len(received)},
        "dispatch_status": (
            "unknown; admission record failed before inner dispatch; reserve retained"
        ),
        "missing_case_completion": {
            "warehouse-r1-P2": {
                "closure_submitted": False,
                "turns": [{"turn": 12, "status": "failed"}],
                "source": str(OUTPUT / "recovered-turn-status.json"),
                "source_sha256": file_hash(OUTPUT / "recovered-turn-status.json"),
            }
        },
        "recovery_metadata": {"path": str(metadata), "sha256": file_hash(metadata)},
        "original_evidence": copies,
        "absolute_deadline_utc": "2026-10-07T04:30:34+00:00",
    }
    target = OUTPUT / "disk-audit-v2.json"
    if target.exists():
        raise RuntimeError("Audit already exists")
    target.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"audit": str(target), "sha256": file_hash(target), "delta": delta}))


if __name__ == "__main__":
    main()
