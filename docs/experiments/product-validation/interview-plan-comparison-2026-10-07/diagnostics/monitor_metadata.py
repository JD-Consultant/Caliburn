"""Read-only batch observations; no interview, JD, note body or credentials."""

import json
from datetime import UTC, datetime
from decimal import Decimal

from completion_batch_v2 import ARTIFACT_ROOT, SCHEDULED


def main():
    batch = ARTIFACT_ROOT / "formal-supplement-v2"
    manifest = json.loads((batch / "manifest.json").read_text(encoding="utf-8"))
    legacy = manifest["continuation"]["prior_accounting"]["retained_reservations"]
    events = []
    for line in (
        (ARTIFACT_ROOT / "formal-supplement-v2-console.log")
        .read_text(encoding="utf-8-sig")
        .splitlines()
    ):
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and "case" in value and "turn" in value:
            events.append(value)
    journals = []
    partial_rows = 0
    for path in batch.glob("*/provider-trace.jsonl"):
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                partial_rows += 1
                continue  # Observation only; final ledger audit still fails closed.
            if "outbound" in row:
                journals.append(row)
    journals.sort(key=lambda row: row["time"])
    latest = journals[-1] if journals else None
    complete = []
    for name in SCHEDULED:
        path = batch / name / "result.json"
        if not path.exists():
            continue
        result = json.loads(path.read_text(encoding="utf-8"))
        if result["closure_submitted"] and result["turns"][-1]["status"] == "completed":
            complete.append(name)
    result = {
        "observed_at": datetime.now(UTC).isoformat(),
        "new_completed_turns": sum(row["status"] == "completed" for row in events),
        "latest_turn": events[-1] if events else None,
        "completed_new_cases": complete,
        "retained_original_completed_cases": [SCHEDULED[0]],
        "journal_last_guard_snapshot_time": latest["time"] if latest else None,
        "journal_last_guard_snapshot": {
            key: latest[key]
            for key in [
                "case",
                "spent_usd",
                "occupied_usd",
                "retained_reservations",
                "generations",
                "compacts",
                "outbound",
                "counted_input",
                "stop_reason",
            ]
        }
        if latest
        else None,
        "partial_observed_journal_rows": partial_rows,
        "legacy_unknown_reserve_usd": str(
            sum((Decimal(value) for value in legacy.values()), Decimal(0))
        ),
    }
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
