"""Offline SDK tool serialization and error boundaries, not provider acceptance."""

import json
from pathlib import Path
from uuid import uuid4

import httpx2
import pytest
from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import async_sessionmaker

from caliburn.features.executions.models import ExecutionKind, ExecutionScope
from caliburn.features.work_memory.candidates import MemoryBatchPosition
from caliburn.features.work_memory.models import MemoryMapEntry
from caliburn.features.work_memory.revisions import MemoryLayer
from caliburn.transport.model_tools.memory_reads import MemoryReadTools
from caliburn.workflows.memory_reads import (
    CandidateMemoryRead,
    MemoryReadBinding,
    MemoryReadWorkflow,
    PublishedMemoryRead,
)


def make_tools(role: str) -> MemoryReadTools:
    reader = MemoryReadWorkflow(async_sessionmaker())
    scope = ExecutionScope(
        uuid4(),
        uuid4(),
        ExecutionKind.CONSULTANT_TURN if role == "consultant" else ExecutionKind.MEMORY_BATCH,
    )
    if role == "consultant":
        return MemoryReadTools(reader, PublishedMemoryRead(scope, None, 1))
    phase = MemoryLayer.WORK_SITUATION if role == "situation" else MemoryLayer.WORK_UNDERSTANDING
    return MemoryReadTools(
        reader,
        CandidateMemoryRead(
            scope,
            MemoryBatchPosition(
                scope.job_file_id,
                scope.execution_id,
                uuid4(),
                uuid4(),
                phase,
                uuid4(),
            ),
        ),
    )


@pytest.mark.parametrize("role", ["consultant", "situation", "understanding"])
def test_role_definitions_only_expose_model_choices(role: str) -> None:
    tools = make_tools(role)
    definitions = tools.definitions()
    assert [item["name"] for item in definitions] == list(tools.names)
    assert len(definitions) == (3 if role == "situation" else 5)
    for definition in definitions:
        assert definition["strict"] is True
        schema = definition["parameters"]
        assert schema["type"] == "object"
        assert schema["additionalProperties"] is False
        expected = (
            []
            if definition["name"].endswith("_map")
            else ["query" if definition["name"] == "read_interview" else "target_title"]
        )
        assert list(schema["properties"]) == expected
        assert schema.get("required", []) == expected


@pytest.mark.asyncio
async def test_direct_sdk_sends_the_generated_strict_definitions_without_app_scope() -> None:
    definitions = make_tools("consultant").definitions()
    response = json.loads(
        (Path(__file__).parents[1] / "fixtures/native-response.json").read_text(encoding="utf-8")
    )
    captured = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        assert request.url.host == "openai.invalid"
        captured.append(json.loads(request.content))
        return httpx2.Response(200, json=response)

    async with AsyncOpenAI(
        api_key="synthetic-test-key",
        base_url="https://openai.invalid/v1/",
        max_retries=0,
        http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(respond)),
    ) as client:
        await client.responses.create(
            model="gpt-6-luna",
            input="合成離線工具序列化",
            store=False,
            tools=definitions,
            reasoning={"context": "all_turns"},
        )
    assert len(captured) == 1
    assert captured[0]["tools"] == definitions
    assert captured[0]["store"] is False
    assert "previous_response_id" not in captured[0]


@pytest.mark.asyncio
async def test_infrastructure_failure_propagates_to_runtime_not_fake_model_argument_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tools = make_tools("consultant")

    async def unavailable(
        binding: MemoryReadBinding, layer: MemoryLayer
    ) -> tuple[MemoryMapEntry, ...]:
        raise TimeoutError("synthetic storage timeout")

    monkeypatch.setattr(tools.reader, "read_map", unavailable)
    with pytest.raises(TimeoutError):
        await tools.invoke("read_work_situation_map", "{}")
    rejected = json.loads(await tools.invoke("read_work_situation_map", '{"scope":"forged"}'))
    assert rejected["code"] == "invalid_arguments"
