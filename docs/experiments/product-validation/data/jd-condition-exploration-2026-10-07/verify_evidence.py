"""Recompute saved usage and verify immutable packages; never grade semantics."""

import hashlib
import json
import zipfile
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).resolve().parent


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


totals = {}
occupied = Decimal(0)
started = read_json(HERE / "live-01/started.json")
deadline = datetime.fromisoformat(started["started_at"]) + timedelta(seconds=1200)
initial_fixtures = None
packages = []
for phase, expected_turns in (("live-01", 16), ("live-02", 6)):
    directory = HERE / phase
    manifest = read_json(directory / "manifest.json")
    result = read_json(directory / "result.json")
    usage = result["accounting"]
    assert not (directory / "failure.json").exists()
    assert len(result["completed"]) == len(manifest["fixtures"]) == expected_turns
    assert result["completed"] == manifest["schedule"]
    assert usage["stop_reason"] is None
    assert usage["pending_request_sha256"] is None
    assert Decimal(usage["pending_reserved_usd"]) == 0
    assert manifest["model"] == "gpt-6-luna" and manifest["effort"] == "high"
    assert manifest["tools"]["old"] == manifest["tools"]["new"]
    assert Decimal(manifest["budget_usd"]) == Decimal("0.10") - occupied
    with zipfile.ZipFile(directory / "sources.zip") as archive:
        for name, expected in manifest["files"].items():
            assert hashlib.sha256(archive.read(name)).hexdigest() == expected, name
    packages.append({"phase": phase, "verified_files": len(manifest["files"])})
    identities = {
        (f["case_id"], f["arm"]): f["job_file_id"] for f in manifest["fixtures"]
    }
    if initial_fixtures is None:
        initial_fixtures = identities
    else:
        assert all(initial_fixtures[key] == value for key, value in identities.items())
        assert (
            datetime.fromisoformat(manifest["parent_boundary"]["deadline_utc"])
            == deadline
        )
    occupied += Decimal(usage["batch_occupied_usd"])
    assert occupied <= Decimal("0.10")
    for key in (
        "input_tokens",
        "output_tokens",
        "reasoning_tokens",
        "cached_input_tokens",
        "generation_calls",
        "count_calls",
        "compaction_calls",
    ):
        totals[key] = totals.get(key, 0) + usage[key]
    finished = datetime.fromisoformat(
        read_json(directory / "started.json")["started_at"]
    )
    finished += timedelta(seconds=usage["elapsed_seconds"])
    assert finished <= deadline

print(
    json.dumps(
        {"packages": packages, "totals": totals, "occupied_usd": str(occupied)},
        ensure_ascii=False,
        indent=2,
    )
)
