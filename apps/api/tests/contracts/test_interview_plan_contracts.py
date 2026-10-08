"""Nullable body semantics and result branches have one closed canonical wire."""

import json
from pathlib import Path
from uuid import uuid4

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from pydantic import ValidationError
from referencing import Registry, Resource

from caliburn.contracts.generated.interview_plan_view import InterviewPlanView
from caliburn.contracts.generated.tools.edit_interview_plan_arguments import (
    EditInterviewPlanArguments,
)
from caliburn.contracts.generated.tools.interview_plan import InterviewPlan
from caliburn.contracts.generated.tools.interview_plan_write_result import InterviewPlanWriteResult
from caliburn.contracts.generated.tools.read_interview_plan_arguments import (
    ReadInterviewPlanArguments,
)

CONTRACTS = Path(__file__).parents[2] / "contracts"


def validator(family: str, name: str) -> Draft202012Validator:
    schema = json.loads((CONTRACTS / family / f"{name}.schema.json").read_text(encoding="utf-8"))
    resources = [
        (prefix + path.name, Resource.from_contents(json.loads(path.read_text(encoding="utf-8"))))
        for source_family, prefix in (("http", ""), ("tools", "../tools/"))
        for path in (CONTRACTS / source_family).glob("*.schema.json")
    ]
    return Draft202012Validator(
        schema, registry=Registry().with_resources(resources), format_checker=FormatChecker()
    )


@pytest.mark.parametrize("body", [None, "", " \r\n原文\r\n"])
def test_read_and_http_preserve_null_empty_and_original_body(body: str | None) -> None:
    read = {"plan": body}
    validator("tools", "interview-plan").validate(read)
    assert InterviewPlan.model_validate(read).model_dump() == read
    view = {"job_file_id": str(uuid4()), "plan": body}
    validator("http", "interview-plan-view").validate(view)
    assert InterviewPlanView.model_validate(view).model_dump(mode="json") == view


def test_read_and_edit_arguments_expose_only_required_model_owned_parameters() -> None:
    assert ReadInterviewPlanArguments.model_validate({}).model_dump() == {}
    assert EditInterviewPlanArguments.model_validate({"diff": "@@\n+x\n*** End of File"}).diff
    for payload in ({"diff": ""}, {"diff": 1}, {"diff": "x", "revision_id": str(uuid4())}):
        with pytest.raises(ValidationError):
            EditInterviewPlanArguments.model_validate(payload)
    with pytest.raises(ValidationError):
        ReadInterviewPlanArguments.model_validate({"job_file_id": str(uuid4())})


def test_write_success_branches_require_actual_diff_only_when_updated() -> None:
    wire = validator("tools", "interview-plan-write-result")
    for result in ({"status": "unchanged"}, {"status": "updated", "diff": "actual difference"}):
        wire.validate(result)
        assert InterviewPlanWriteResult.model_validate(result).model_dump() == result
    for invalid in (
        {"status": "updated"},
        {"status": "updated", "diff": ""},
        {"status": "unchanged", "diff": None},
        {"status": "unchanged", "diff": "unnecessary"},
        {"status": "updated", "diff": "actual", "plan": "duplicate body"},
        {"status": "completed"},
    ):
        assert not wire.is_valid(invalid)
        with pytest.raises(ValidationError):
            InterviewPlanWriteResult.model_validate(invalid)


def test_turn_preview_is_required_nullable_and_does_not_repeat_scope() -> None:
    wire = validator("http", "consultant-turn")
    turn = {
        "job_file_id": str(uuid4()),
        "execution_id": str(uuid4()),
        "status": "active",
        "pause_requested": False,
        "input_text": "合成輸入",
        "allowed_controls": [],
        "commentary": [],
        "candidate": None,
    }
    assert not wire.is_valid(turn)
    for preview in (None, {"plan": None}, {"plan": ""}, {"plan": "原文"}):
        wire.validate(turn | {"plan_preview": preview})
    for preview in ({}, {"plan": 1}, {"plan": None, "execution_id": str(uuid4())}):
        assert not wire.is_valid(turn | {"plan_preview": preview})
