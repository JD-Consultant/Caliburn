"""Continue selected paired files under the original time and spending boundary."""

import argparse
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from run_comparison import configure


def continue_selected(source_name: str, output_name: str, decision_name: str) -> None:
    comparison = configure()
    source = comparison.HERE / source_name
    output = comparison.HERE / output_name
    if not all(
        (comparison.HERE / name).resolve().parent == comparison.HERE.resolve()
        for name in (source_name, output_name, decision_name)
    ):
        raise ValueError("Only this experiment's named phases may be continued")
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
        raise ValueError("Unresolved or unfinished prior phase forbids continuation")
    comparison.verify_files(manifest["files"], root=comparison.ROOT)
    parent = manifest.get("parent_boundary")
    if parent is None:
        started = comparison.read_json(source / "started.json")
        if (
            Decimal(started["budget_usd"]) != Decimal("0.10")
            or started["seconds"] != 1200
        ):
            raise ValueError("Unexpected original authorization")
        deadline = datetime.fromisoformat(started["started_at"]) + timedelta(
            seconds=1200
        )
        prior_occupied = Decimal(0)
        prior_depth = 1
    else:
        deadline = datetime.fromisoformat(parent["deadline_utc"])
        prior_occupied = Decimal(parent["prior_occupied_usd"])
        prior_depth = parent["depth"]
    if prior_depth >= 3:
        raise ValueError("The frozen maximum of three turns has been reached")
    prior_occupied += Decimal(accounting["batch_occupied_usd"])
    remaining = Decimal("0.10") - prior_occupied
    seconds = int((deadline - datetime.now(UTC)).total_seconds())
    if remaining <= 0 or seconds < 1:
        raise ValueError("Original authorized boundary reached")
    decisions = comparison.read_json(comparison.HERE / decision_name)["decisions"]
    policy = comparison.read_json(comparison.HERE / "reply-policy.json")
    by_identity = {
        (item["case_id"], item["arm"]): item for item in manifest["fixtures"]
    }
    selected = []
    cases = []
    seen = set()
    for decision in decisions:
        identity = decision["case_id"], decision["arm"]
        if identity in seen or identity not in by_identity:
            raise ValueError("Invalid or repeated continuation identity")
        fixture = by_identity[identity]
        base_case_id = fixture.get("base_case_id", fixture["case_id"])
        answers = policy["answers"][base_case_id]
        expected = (
            policy["unknown_reply"]
            if decision["answer_kind"] == "unknown"
            else answers[decision["answer_kind"]]
        )
        if not decision["reason"] or not decision["question_quote"]:
            raise ValueError(
                "Each adaptive answer requires a recorded semantic decision"
            )
        selected.append(
            {
                **fixture,
                "base_case_id": base_case_id,
                "case_id": f"{base_case_id}__{identity[1]}",
                "before": comparison.read_json(
                    source / f"{identity[0]}-{identity[1]}-after.json"
                ),
            }
        )
        cases.append(
            {"case_id": f"{base_case_id}__{identity[1]}", "employee_input": expected}
        )
        seen.add(identity)
    if not selected:
        raise ValueError("No declared continuations")
    files = comparison.freeze_files(
        [
            *(comparison.ROOT / path for path in manifest["files"]),
            Path(__file__),
            comparison.HERE / decision_name,
            source / "manifest.json",
            source / "result.json",
            source / "started.json",
        ],
        root=comparison.ROOT,
        output=output,
    )
    # The shared executor looks up a case by case_id, not arm. Each adaptive
    # answer therefore gets a distinct phase label, while file/prompt identity stays fixed.
    fixtures = selected
    comparison.save_new(
        output / "manifest.json",
        {
            **manifest,
            "files": files,
            "cases": cases,
            "fixtures": fixtures,
            "schedule": [
                {"arm": item["arm"], "case_id": item["case_id"]} for item in fixtures
            ],
            "budget_usd": str(remaining),
            "seconds": seconds,
            "parent_boundary": {
                "deadline_utc": deadline.isoformat(),
                "prior_occupied_usd": str(prior_occupied),
                "depth": prior_depth + 1,
                "source_phase": source_name,
                "reason": "Frozen adaptive replies; same files/native history; original allowance",
            },
        },
    )
    comparison.OUTPUT = output
    print(
        f"CONTINUE {len(fixtures)} files; remaining ${remaining}; deadline {deadline}",
        flush=True,
    )
    comparison.execute()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source")
    parser.add_argument("output")
    parser.add_argument("decisions")
    arguments = parser.parse_args()
    continue_selected(arguments.source, arguments.output, arguments.decisions)
