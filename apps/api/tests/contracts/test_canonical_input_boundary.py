"""Real HTTP and model-tool entrypoints accept the canonical wire before conversion."""

import json
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from caliburn.contracts.generated.create_job_file_request import CreateJobFileRequest
from caliburn.features.executions.models import ExecutionKind, ExecutionScope
from caliburn.features.job_files.models import JobFile, JobFileCreation
from caliburn.transport.http.job_files import get_job_file_workflow, router
from caliburn.transport.model_tools.memory_reads import MemoryReadTools
from caliburn.workflows.memory_reads import PublishedMemoryRead

PLAIN_UUID = "12345678-1234-4234-8234-1234567890ab"


@pytest.fixture
def http_boundary():
    commands = []
    job = JobFile(uuid4(), "工作", 1, "員工", datetime.now(UTC))

    async def rename(job_file_id, command):
        commands.append(command)
        return job

    async def create(command):
        commands.append(command)
        return JobFileCreation(job, True)

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_job_file_workflow] = lambda: SimpleNamespace(
        rename=rename, create=create
    )
    with TestClient(app) as client:
        yield client, commands, job.job_file_id


@pytest.mark.parametrize("value", [1, 1.0, 9007199254740991, 9007199254740991.0])
def test_http_integral_numbers_are_converted_only_after_wire_acceptance(http_boundary, value):
    client, commands, job_file_id = http_boundary
    response = client.post(
        f"/api/job-files/{job_file_id}/rename",
        json={"command_id": PLAIN_UUID, "display_name": "工作", "expected_name_revision": value},
    )
    assert response.status_code == 200
    assert type(commands[0].expected_name_revision) is int
    assert commands[0].expected_name_revision == value


@pytest.mark.parametrize("value", [True, "1", 1.5, None, 9007199254740992])
def test_http_conversion_does_not_accept_non_schema_integer(http_boundary, value):
    client, commands, job_file_id = http_boundary
    response = client.post(
        f"/api/job-files/{job_file_id}/rename",
        json={"command_id": PLAIN_UUID, "display_name": "工作", "expected_name_revision": value},
    )
    assert response.status_code == 422
    assert commands == []


@pytest.mark.parametrize(
    "value", [PLAIN_UUID.replace("-", ""), "urn:uuid:" + PLAIN_UUID, PLAIN_UUID + "-"]
)
def test_http_uuid_format_rejects_non_plain_uuid_before_workflow(http_boundary, value):
    client, commands, _ = http_boundary
    response = client.post(
        "/api/job-files",
        json={"command_id": value, "display_name": "工作", "employee_name": "員工"},
    )
    assert response.status_code == 422
    assert value not in response.text
    assert commands == []


@pytest.mark.parametrize("value", [PLAIN_UUID, PLAIN_UUID.upper()])
def test_http_plain_uuid_preserves_supported_case_variants(http_boundary, value):
    client, commands, _ = http_boundary
    response = client.post(
        "/api/job-files",
        json={"command_id": value, "display_name": "工作", "employee_name": "員工"},
    )
    assert response.status_code == 201
    assert commands[0].command_id == UUID(PLAIN_UUID)


def test_http_schema_error_does_not_echo_private_text_or_untrusted_property(http_boundary):
    client, commands, _ = http_boundary
    response = client.post(
        "/api/job-files",
        json={
            "command_id": PLAIN_UUID,
            "display_name": "員工私密正文",
            "employee_name": "員工",
            "不應洩露的未知欄位": "機密",
        },
    )
    assert response.status_code == 422
    assert "additionalProperties" in response.text
    assert all(text not in response.text for text in ["員工私密正文", "不應洩露的未知欄位", "機密"])
    assert commands == []


@pytest.mark.parametrize(
    ("value", "accepted"),
    [
        ("\u0085", False),
        ("\u001c", False),
        ("\ufeff", True),
        ("\n\t ", False),
        ("工作\n多行", True),
        ("工作\u0000", False),
    ],
)
def test_http_nonblank_policy_matches_domain_without_changing_text(http_boundary, value, accepted):
    client, commands, _ = http_boundary
    response = client.post(
        "/api/job-files",
        json={"command_id": PLAIN_UUID, "display_name": value, "employee_name": "員工"},
    )
    assert response.status_code == (201 if accepted else 422)
    if accepted:
        assert commands[0].display_name == value
    else:
        assert commands == []


def test_http_generated_representation_failure_is_internal_and_safe(http_boundary, monkeypatch):
    client, commands, _ = http_boundary

    def incompatible_dto(value, **_kwargs):
        raise ValidationError.from_exception_data(
            "RepresentationFailure",
            [{"type": "int_parsing", "loc": ("display_name",), "input": value["display_name"]}],
        )

    monkeypatch.setattr(CreateJobFileRequest, "model_validate", incompatible_dto)
    with TestClient(client.app, raise_server_exceptions=False) as failing_client:
        response = failing_client.post(
            "/api/job-files",
            json={"command_id": PLAIN_UUID, "display_name": "私密正文", "employee_name": "員工"},
        )
    assert response.status_code == 500
    assert "私密正文" not in response.text
    assert commands == []


@pytest.mark.parametrize(
    ("sequence", "accepted"),
    [
        (1, True),
        (1.0, True),
        (9007199254740991, True),
        (9007199254740991.0, True),
        (9007199254740992, False),
        (9007199254740992.0, False),
        (10000000000000000000, False),
        (1e19, False),
        (True, False),
        ("1", False),
        (1.5, False),
    ],
)
async def test_tool_integer_policy_matches_http(sequence, accepted):
    message = SimpleNamespace(
        interview_sequence=1, speaker=SimpleNamespace(value="employee"), interview_text="原話"
    )
    reader = SimpleNamespace(read_interview_messages=AsyncMock(return_value=[message]))
    scope = ExecutionScope(uuid4(), uuid4(), ExecutionKind.CONSULTANT_TURN)
    tools = MemoryReadTools(reader, PublishedMemoryRead(scope, None, 9007199254740991))
    result = json.loads(
        await tools.invoke(
            "read_interview", json.dumps({"query": {"kind": "messages", "sequences": [sequence]}})
        )
    )
    assert (result.get("status") != "rejected") is accepted
    if accepted:
        assert reader.read_interview_messages.await_args.args[1] == (int(sequence),)
        assert type(reader.read_interview_messages.await_args.args[1][0]) is int
    else:
        reader.read_interview_messages.assert_not_awaited()
        assert result["code"] == "invalid_arguments"
        assert "序號為正整數" in result["next_action"]
