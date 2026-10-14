"""Schema-authored DTOs retain names, true speaker and strict formal ordering fields."""

import json
from uuid import uuid4

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from pydantic import BaseModel, ValidationError

from caliburn.transport.http.models.consultant import AcceptedInterviewInput, SubmitInterviewInput
from caliburn.transport.http.models.job_files import (
    CreateJobFileRequest,
    InterviewHistory,
    JobFileList,
    RecordUsageHeartbeatRequest,
    RenameJobFileRequest,
)
from tests.fixtures.http_contracts import http_schema


@pytest.mark.parametrize(
    ("model", "payload"),
    [
        (
            SubmitInterviewInput,
            {"command_id": str(uuid4()), "text": " 每月一次。\n也會協助其他工作。 "},
        ),
        (
            AcceptedInterviewInput,
            {
                name: str(uuid4())
                for name in ("job_file_id", "command_id", "source_id", "execution_id")
            },
        ),
        (
            CreateJobFileRequest,
            {"command_id": str(uuid4()), "display_name": "工作檔案", "employee_name": "員工"},
        ),
        (
            RenameJobFileRequest,
            {"command_id": str(uuid4()), "display_name": "新名稱", "expected_name_revision": 1},
        ),
        (RecordUsageHeartbeatRequest, {"elapsed_seconds": 20}),
        (
            JobFileList,
            {
                "job_files": [
                    {
                        "job_file_id": str(uuid4()),
                        "display_name": "工作檔案",
                        "name_revision": 1,
                        "employee_name": "員工",
                        "created_at": "2026-09-29T00:00:00Z",
                        "active_usage_seconds": 0,
                    }
                ]
            },
        ),
        (
            InterviewHistory,
            {
                "messages": [
                    {
                        "source_id": str(uuid4()),
                        "interview_sequence": 1,
                        "speaker": "app",
                        "interview_text": "您平常主要負責哪些工作？",
                        "execution_id": None,
                    }
                ]
            },
        ),
    ],
)
def test_http_contract_round_trip(model: type[BaseModel], payload: dict[str, object]) -> None:
    schema = http_schema(model)
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    validator.validate(payload)
    assert json.loads(model.model_validate(payload).model_dump_json()) == payload
    invalid = {**payload, "unexpected_field": "not allowed"}
    assert not validator.is_valid(invalid)
    with pytest.raises(ValidationError):
        model.model_validate(invalid)


@pytest.mark.parametrize("elapsed_seconds", [0, -1, 61, "20", True])
def test_usage_heartbeat_seconds_is_a_bounded_integer_not_a_coerced_value(
    elapsed_seconds: object,
) -> None:
    payload = {"elapsed_seconds": elapsed_seconds}
    schema = http_schema(RecordUsageHeartbeatRequest)
    assert not Draft202012Validator(schema).is_valid(payload)
    with pytest.raises(ValidationError):
        RecordUsageHeartbeatRequest.model_validate(payload)


@pytest.mark.parametrize("sequence", [0, -1, "1", True])
def test_formal_sequence_is_a_positive_integer_not_a_coerced_value(sequence: object) -> None:
    payload = {
        "messages": [
            {
                "source_id": str(uuid4()),
                "interview_sequence": sequence,
                "speaker": "employee",
                "interview_text": "員工原話",
                "execution_id": None,
            }
        ]
    }
    schema = http_schema(InterviewHistory)
    assert not Draft202012Validator(schema).is_valid(payload)
    with pytest.raises(ValidationError):
        InterviewHistory.model_validate(payload)


@pytest.mark.parametrize("execution_id", [None, str(uuid4())])
def test_history_reply_locator_round_trips_without_private_fields(execution_id: str | None) -> None:
    payload = {
        "messages": [
            {
                "source_id": str(uuid4()),
                "interview_sequence": 3,
                "speaker": "consultant",
                "interview_text": "正式答覆",
                "execution_id": execution_id,
            }
        ]
    }
    schema = http_schema(InterviewHistory)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    validator.validate(payload)
    assert json.loads(InterviewHistory.model_validate(payload).model_dump_json()) == payload
    for name, value in (
        ("execution_id", "not-a-uuid"),
        ("checkpoint_id", "private"),
        ("command_id", str(uuid4())),
    ):
        invalid = {"messages": [{**payload["messages"][0], name: value}]}
        assert not validator.is_valid(invalid)
        with pytest.raises(ValidationError):
            InterviewHistory.model_validate(invalid)


@pytest.mark.parametrize("text", ["", " \n\t", "\u3000", "abc\x00"])
def test_submission_wire_and_dto_agree_on_invalid_originals(text: str) -> None:
    payload = {"command_id": str(uuid4()), "text": text}
    schema = http_schema(SubmitInterviewInput)
    assert not Draft202012Validator(schema).is_valid(payload)
    with pytest.raises(ValidationError):
        SubmitInterviewInput.model_validate(payload)
