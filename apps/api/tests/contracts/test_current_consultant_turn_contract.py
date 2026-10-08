"""Discovery shares the public Turn shape, with a required nullable result."""

import json
from pathlib import Path
from uuid import uuid4

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from pydantic import ValidationError
from referencing import Registry, Resource

from caliburn.contracts.generated.current_consultant_turn import CurrentConsultantTurn


@pytest.fixture
def validator() -> Draft202012Validator:
    directory = Path(__file__).parents[2] / "contracts/http"
    schema = json.loads((directory / "current-consultant-turn.schema.json").read_text("utf-8"))
    Draft202012Validator.check_schema(schema)
    registry = Registry().with_resources(
        (path.name, Resource.from_contents(json.loads(path.read_text("utf-8"))))
        for path in directory.glob("*.schema.json")
    )
    registry = registry.with_resource(
        "tools/interview-plan.schema.json",
        Resource.from_contents(
            json.loads((directory.parent / "tools/interview-plan.schema.json").read_text("utf-8"))
        ),
    )
    return Draft202012Validator(schema, format_checker=FormatChecker(), registry=registry)


def public_turn() -> dict:
    return {
        "job_file_id": str(uuid4()),
        "execution_id": str(uuid4()),
        "status": "active",
        "pause_requested": False,
        "input_text": "原始輸入尚無正式序號",
        "allowed_controls": [],
        "commentary": [],
        "plan_preview": None,
        "candidate": None,
    }


@pytest.mark.parametrize("state", [None, "active", "pause_requested", "paused"])
def test_schema_and_generated_dto_preserve_discovery_result(
    validator: Draft202012Validator, state: str | None
) -> None:
    turn = None
    if state is not None:
        turn = public_turn() | {
            "status": "paused" if state == "paused" else "active",
            "pause_requested": state != "active",
        }
    payload = {"turn": turn}
    validator.validate(payload)
    assert CurrentConsultantTurn.model_validate(payload).model_dump(mode="json") == payload


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"turn": None, "writer_id": "private"},
        {"turn": {}},
        {"turn": public_turn() | {"reasoning": "private"}},
        {"turn": public_turn() | {"status": "pause_requested"}},
        {"turn": public_turn() | {"pause_requested": "true"}},
        {"turn": public_turn() | {"candidate": {"checkpoint": "private"}}},
    ],
)
def test_schema_and_generated_dto_reject_omission_private_payload_and_invented_state(
    validator: Draft202012Validator, payload: dict
) -> None:
    assert not validator.is_valid(payload)
    with pytest.raises(ValidationError):
        CurrentConsultantTurn.model_validate(payload)
