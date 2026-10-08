"""Configure one same-file continuation inside the original approved boundary."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from run_comparison import configure

comparison = configure()
source = comparison.OUTPUT
manifest = comparison.read_json(source / "manifest.json")
result = comparison.read_json(source / "result.json")
accounting = result["accounting"]
if (
    (source / "failure.json").exists()
    or len(result["completed"]) != len(manifest["fixtures"])
    or accounting["stop_reason"] is not None
    or accounting["pending_request_sha256"] is not None
    or Decimal(accounting["pending_reserved_usd"]) != 0
):
    raise ValueError("Unresolved or unfinished first phase forbids continuation")
comparison.verify_files(manifest["files"], root=comparison.ROOT)
started = comparison.read_json(source / "started.json")
if Decimal(started["budget_usd"]) != Decimal("0.10") or started["seconds"] != 1200:
    raise ValueError("Unexpected original authorization")
deadline = datetime.fromisoformat(started["started_at"]) + timedelta(seconds=1200)
remaining = Decimal("0.10") - Decimal(accounting["batch_occupied_usd"])
seconds = int((deadline - datetime.now(UTC)).total_seconds())
if remaining <= 0 or seconds < 1:
    raise ValueError("Original authorized boundary reached")
inputs = comparison.read_json(comparison.HERE / "continuation-inputs.json")[
    "employee_inputs"
]
fixtures = [f for f in manifest["fixtures"] if f["case_id"] in inputs]
if len(fixtures) != 6 or set(inputs) != {f["case_id"] for f in fixtures}:
    raise ValueError("Expected only the three paired warehouse continuations")
comparison.OUTPUT = comparison.HERE / "live-02"
files = comparison.freeze_files(
    [
        *(comparison.ROOT / path for path in manifest["files"]),
        Path(__file__),
        comparison.HERE / "continuation-inputs.json",
        comparison.HERE / "continuation-plan.md",
    ],
    root=comparison.ROOT,
    output=comparison.OUTPUT,
)
comparison.save_new(
    comparison.OUTPUT / "manifest.json",
    {
        **manifest,
        "files": files,
        "cases": [
            {**case, "employee_input": inputs[case["case_id"]]}
            for case in manifest["cases"]
            if case["case_id"] in inputs
        ],
        "fixtures": [
            {
                **fixture,
                "before": comparison.read_json(
                    source / f"{fixture['case_id']}-{fixture['arm']}-after.json"
                ),
            }
            for fixture in fixtures
        ],
        "schedule": [{"arm": f["arm"], "case_id": f["case_id"]} for f in fixtures],
        "budget_usd": str(remaining),
        "seconds": seconds,
        "parent_boundary": {
            "deadline_utc": deadline.isoformat(),
            "prior_occupied_usd": accounting["batch_occupied_usd"],
            "reason": "Posthoc scope/boundary clarification; same file/native history, no hidden answers, no new allowance",
        },
    },
)
print(
    f"CONTINUE 6 same files, remaining ${remaining}; original deadline {deadline}",
    flush=True,
)
comparison.execute()
