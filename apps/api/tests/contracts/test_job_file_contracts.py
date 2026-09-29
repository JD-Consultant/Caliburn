"""Schema-authored DTOs retain names, true speaker and strict formal ordering fields."""

import json
from pathlib import Path
from uuid import uuid4

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from pydantic import BaseModel, ValidationError

from caliburn.contracts.generated.create_job_file_request import CreateJobFileRequest
from caliburn.contracts.generated.interview_history import InterviewHistory
from caliburn.contracts.generated.job_file_list import JobFileList

SCHEMAS = Path(__file__).parents[2] / "contracts/http"


@pytest.mark.parametrize(
    ("schema_name", "model", "payload"),
    [
        (
            "create-job-file-request",
            CreateJobFileRequest,
            {"command_id": str(uuid4()), "display_name": "工作檔案", "employee_name": "員工"},
        ),
        (
            "job-file-list",
            JobFileList,
            {
                "job_files": [
                    {
                        "job_file_id": str(uuid4()),
                        "display_name": "工作檔案",
                        "employee_name": "員工",
                        "created_at": "2026-09-29T00:00:00Z",
                    }
                ]
            },
        ),
        (
            "interview-history",
            InterviewHistory,
            {
                "messages": [
                    {
                        "source_id": str(uuid4()),
                        "interview_sequence": 1,
                        "speaker": "app",
                        "interview_text": "您平常主要負責哪些工作？",
                    }
                ]
            },
        ),
    ],
)
def test_http_contract_round_trip(
    schema_name: str, model: type[BaseModel], payload: dict[str, object]
) -> None:
    schema = json.loads((SCHEMAS / f"{schema_name}.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    validator.validate(payload)
    assert json.loads(model.model_validate(payload).model_dump_json()) == payload
    invalid = {**payload, "unexpected_field": "not allowed"}
    assert not validator.is_valid(invalid)
    with pytest.raises(ValidationError):
        model.model_validate(invalid)


@pytest.mark.parametrize("sequence", [0, -1, "1", True])
def test_formal_sequence_is_a_positive_integer_not_a_coerced_value(sequence: object) -> None:
    payload = {
        "messages": [
            {
                "source_id": str(uuid4()),
                "interview_sequence": sequence,
                "speaker": "employee",
                "interview_text": "員工原話",
            }
        ]
    }
    schema = json.loads((SCHEMAS / "interview-history.schema.json").read_text(encoding="utf-8"))
    assert not Draft202012Validator(schema).is_valid(payload)
    with pytest.raises(ValidationError):
        InterviewHistory.model_validate(payload)
