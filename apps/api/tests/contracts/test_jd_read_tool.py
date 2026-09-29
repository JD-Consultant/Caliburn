"""Generated input and all read-view dispatch; no provider or database calls here."""

import json
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import async_sessionmaker

from caliburn.contracts.generated.tools.read_jd_arguments import View
from caliburn.features.executions.models import ExecutionKind, ExecutionScope
from caliburn.features.job_description.candidate_service import JdCandidatePreview
from caliburn.features.job_description.candidates import JdCandidatePosition, JdCandidateScope
from caliburn.features.job_description.models import JdProfile
from caliburn.features.job_description.work_queries import JdWorkRevision
from caliburn.transport.model_tools.jd_reads import JdReadTools, jd_read_definitions
from caliburn.workflows.jd_reads import JdReadWorkflow
from caliburn.workflows.memory_reads import PublishedMemoryRead


def make_tools(*, limit: int = 1_000_000) -> JdReadTools:
    scope = ExecutionScope(UUID(int=1), UUID(int=2), ExecutionKind.CONSULTANT_TURN)
    return JdReadTools(
        JdReadWorkflow(async_sessionmaker()),
        PublishedMemoryRead(scope, None, 1),
        max_result_characters=limit,
    )


def test_definition_uses_generated_two_field_contract() -> None:
    tools = make_tools()
    (definition,) = tools.definitions()
    assert definition["name"] == "read_jd"
    assert tools.names == ("read_jd",)
    assert definition["strict"] is True
    schema = definition["parameters"]
    assert isinstance(schema, dict)
    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    assert schema["required"] == ["view", "read_ref"]
    properties = schema["properties"]
    assert isinstance(properties, dict)
    assert set(properties) == {"view", "read_ref"}
    definitions = schema["$defs"]
    assert isinstance(definitions, dict)
    assert properties["view"]["$ref"] == "#/$defs/View"
    assert len(definitions["View"]["enum"]) == 11


def test_unbound_definitions_need_no_binding_or_file_reads(monkeypatch: pytest.MonkeyPatch) -> None:
    def no_read(*args: object, **kwargs: object) -> str:
        raise AssertionError("Definitions must be built from the generated type in memory")

    monkeypatch.setattr(Path, "read_text", no_read)
    definitions = jd_read_definitions()
    assert len(definitions) == 1
    assert definitions == make_tools().definitions()
    definitions.clear()
    assert len(jd_read_definitions()) == 1


@pytest.mark.asyncio
async def test_illegal_selection_never_reaches_database() -> None:
    tools = make_tools()
    for arguments in (
        '{"view":"map"}',
        '{"view":"unknown","read_ref":null}',
        '{"view":"map","read_ref":null,"revision":"forged"}',
        '{"view":"item","read_ref":null}',
        '{"view":"work_tasks","read_ref":null}',
        '{"view":"full","read_ref":"task_forged"}',
        '{"view":"item","read_ref":42}',
        '{"view":"item","read_ref":" "}',
    ):
        result = json.loads(await tools.invoke("read_jd", arguments))
        assert result["code"] == "invalid_arguments"
    assert json.loads(await tools.invoke("read_jd_changes", "{}"))["code"] == "scope_not_allowed"


@pytest.mark.asyncio
async def test_empty_collections_full_markdown_capacity_and_storage_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tools = make_tools()
    scope = JdCandidateScope(tools.binding.scope.execution_id, UUID(int=3))
    candidate = JdCandidatePreview(
        JdCandidatePosition(scope, UUID(int=4), UUID(int=4)),
        JdProfile(purpose="原文🙂"),
        JdWorkRevision(UUID(int=4), (), (), (), (), (), ()),
    )

    async def read_candidate(binding: PublishedMemoryRead) -> JdCandidatePreview:
        return candidate

    async def no_sources(*args: object) -> tuple[()]:
        return ()

    monkeypatch.setattr(tools.reader, "read_candidate", read_candidate)
    monkeypatch.setattr(tools.reader, "read_sources", no_sources)
    for view in View:
        if view in (View.ITEM, View.WORK_TASKS):
            continue
        output = await tools.invoke("read_jd", json.dumps({"view": view.value, "read_ref": None}))
        if view == View.FULL:
            assert output == "# 職務說明書\n\n## 職務目的\n\n原文🙂\n"
        elif view == View.MAP:
            assert json.loads(output)["profile"]["job_purpose_preview"] == "原文🙂"
        elif view == View.PROFILE:
            assert json.loads(output)["purpose"] == "原文🙂"
        else:
            assert json.loads(output) == {"items": []}
    tiny = JdReadTools(tools.reader, tools.binding, max_result_characters=1)
    assert (
        json.loads(await tiny.invoke("read_jd", '{"view":"full","read_ref":null}'))["code"]
        == "read_limit_exceeded"
    )

    async def unavailable(binding: PublishedMemoryRead) -> JdCandidatePreview:
        raise TimeoutError("synthetic storage failure")

    monkeypatch.setattr(tools.reader, "read_candidate", unavailable)
    with pytest.raises(TimeoutError):
        await tools.invoke("read_jd", '{"view":"map","read_ref":null}')

    async def invalid_stored_result(binding: PublishedMemoryRead) -> JdCandidatePreview:
        raise ValidationError.from_exception_data(
            "StoredReadResult", [{"type": "string_type", "loc": ("job_title",), "input": 42}]
        )

    monkeypatch.setattr(tools.reader, "read_candidate", invalid_stored_result)
    with pytest.raises(ValidationError):
        await tools.invoke("read_jd", '{"view":"map","read_ref":null}')
