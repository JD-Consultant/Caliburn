"""Verify saved packages, usage, file identity and bounds; never grade prose."""

import hashlib
import json
import zipfile
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).resolve().parent


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def verify() -> None:
    started = read_json(HERE / "live-02/started.json")
    reply_policy = read_json(HERE / "reply-policy.json")
    deadline = datetime.fromisoformat(started["started_at"]) + timedelta(seconds=1200)
    occupied = Decimal(0)
    totals: dict[str, int] = {}
    identities = {}
    packages = []
    for phase, expected in (("live-02", 16), ("live-03", 7), ("live-04", 1)):
        directory = HERE / phase
        manifest = read_json(directory / "manifest.json")
        result = read_json(directory / "result.json")
        usage = result["accounting"]
        assert not (directory / "failure.json").exists()
        assert len(result["completed"]) == len(manifest["fixtures"]) == expected
        assert result["completed"] == manifest["schedule"]
        assert manifest["model"] == "gpt-6-luna" and manifest["effort"] == "high"
        assert manifest["tools"]["old"] == manifest["tools"]["new"]
        assert usage["stop_reason"] is None
        assert usage["pending_request_sha256"] is None
        assert Decimal(usage["pending_reserved_usd"]) == 0
        assert Decimal(manifest["budget_usd"]) == Decimal("0.10") - occupied
        if phase != "live-02":
            parent = manifest["parent_boundary"]
            assert datetime.fromisoformat(parent["deadline_utc"]) == deadline
            assert Decimal(parent["prior_occupied_usd"]) == occupied
            assert parent["depth"] <= 3
        with zipfile.ZipFile(directory / "sources.zip") as archive:
            for name, expected_hash in manifest["files"].items():
                assert hashlib.sha256(archive.read(name)).hexdigest() == expected_hash
        for fixture in manifest["fixtures"]:
            base_case = fixture.get("base_case_id", fixture["case_id"])
            identity = base_case, fixture["arm"]
            if phase == "live-02":
                identities[identity] = fixture["job_file_id"]
            else:
                assert identities[identity] == fixture["job_file_id"]
            after = read_json(
                directory / f"{fixture['case_id']}-{fixture['arm']}-after.json"
            )
            before_ids = {
                task["task_id"] for task in fixture["before"]["work"]["tasks"]
            }
            after_ids = {task["task_id"] for task in after["work"]["tasks"]}
            assert before_ids <= after_ids
        trace_usage = dict.fromkeys(
            (
                "input_tokens",
                "output_tokens",
                "reasoning_tokens",
                "cached_input_tokens",
            ),
            0,
        )
        generation_responses = 0
        first_inputs = set()
        for line in (directory / "trace.jsonl").open(encoding="utf-8"):
            event = json.loads(line)
            if (
                phase == "live-02"
                and event["event"] == "request"
                and event["path"] == "/v1/responses"
            ):
                identity = event["case_id"], event["arm"]
                if identity not in first_inputs:
                    visible = json.dumps(event["payload"]["input"], ensure_ascii=False)
                    assert all(
                        answer["target_answer"] not in visible
                        for answer in reply_policy["answers"].values()
                    )
                    assert all(
                        fixture["case_id"] not in visible
                        for fixture in manifest["fixtures"]
                    )
                    first_inputs.add(identity)
            if event["event"] != "response" or event["path"] != "/v1/responses":
                continue
            assert event["http_status"] == 200
            payload = event["payload"]
            assert payload["status"] == "completed"
            raw_usage = payload["usage"]
            trace_usage["input_tokens"] += raw_usage["input_tokens"]
            trace_usage["output_tokens"] += raw_usage["output_tokens"]
            trace_usage["reasoning_tokens"] += raw_usage["output_tokens_details"][
                "reasoning_tokens"
            ]
            trace_usage["cached_input_tokens"] += raw_usage["input_tokens_details"][
                "cached_tokens"
            ]
            generation_responses += 1
        assert generation_responses == usage["generation_calls"]
        if phase == "live-02":
            assert len(first_inputs) == expected
        assert all(value == usage[key] for key, value in trace_usage.items())
        occupied += Decimal(usage["batch_occupied_usd"])
        assert occupied <= Decimal("0.10")
        for key in (
            *trace_usage,
            "generation_calls",
            "count_calls",
            "compaction_calls",
        ):
            totals[key] = totals.get(key, 0) + usage[key]
        phase_started = datetime.fromisoformat(
            read_json(directory / "started.json")["started_at"]
        )
        finished = phase_started + timedelta(seconds=usage["elapsed_seconds"])
        assert finished <= deadline
        packages.append(
            {
                "phase": phase,
                "turns": expected,
                "verified_files": len(manifest["files"]),
            }
        )
    print(
        json.dumps(
            {"packages": packages, "totals": totals, "occupied_usd": str(occupied)},
            indent=2,
        )
    )


if __name__ == "__main__":
    verify()
