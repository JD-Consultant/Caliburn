"""Public status admits only the defined controls, without formal or internal identities."""

import json
from pathlib import Path
from uuid import uuid4

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource


def test_consultant_status_schema_rejects_private_or_invented_state() -> None:
    schema = json.loads(
        (Path(__file__).parents[2] / "contracts/http/consultant-turn.schema.json").read_text(
            encoding="utf-8"
        )
    )
    Draft202012Validator.check_schema(schema)
    registry = Registry().with_resources(
        (path.name, Resource.from_contents(json.loads(path.read_text(encoding="utf-8"))))
        for path in (Path(__file__).parents[2] / "contracts/http").glob("*.schema.json")
    )
    plan_path = Path(__file__).parents[2] / "contracts/tools/interview-plan.schema.json"
    registry = registry.with_resource(
        "../tools/interview-plan.schema.json",
        Resource.from_contents(json.loads(plan_path.read_text(encoding="utf-8"))),
    )
    validator = Draft202012Validator(schema, format_checker=FormatChecker(), registry=registry)
    original = {
        "job_file_id": str(uuid4()),
        "execution_id": str(uuid4()),
        "status": "active",
        "pause_requested": False,
        "input_text": "合成原話",
        "allowed_controls": [],
        "commentary": [],
        "plan_preview": None,
        "candidate": None,
    }
    for status in ("active", "paused", "completed", "cancelled", "failed"):
        validator.validate(original | {"status": status})
    for controls in (["pause", "cancel"], ["cancel"], ["resume", "cancel"]):
        validator.validate(original | {"allowed_controls": controls})
    validator.validate(original | {"pause_requested": True})
    assert not validator.is_valid(
        {key: value for key, value in original.items() if key != "pause_requested"}
    )
    for invalid in (
        {"reasoning": "private"},
        {"interview_sequence": 2},
        {"source_id": str(uuid4())},
        {"status": "saving"},
        {"pause_requested": "true"},
        {"pause_requested": None},
        {"allowed_controls": ["retry"]},
        {"allowed_controls": ["cancel", "cancel"]},
        {
            "commentary": [
                {"response_id": "r", "message_id": "m", "text": "公開", "reasoning": "private"}
            ]
        },
        {
            "commentary": [
                {"response_id": "r", "message_id": "m", "text": "公開", "interview_sequence": 2}
            ]
        },
    ):
        assert not validator.is_valid(original | invalid)
