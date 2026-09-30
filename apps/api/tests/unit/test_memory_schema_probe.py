"""Canonical role schemas and a bounded count-only probe; all transport here is fake."""

import json
from pathlib import Path
from unittest.mock import Mock
from uuid import uuid4

import httpx2
import pytest

from caliburn.adapters.openai_responses import create_responses_client
from caliburn.features.executions.models import ExecutionKind, ExecutionScope, ExecutionWriter
from caliburn.features.work_memory.candidates import MemoryBatchPosition
from caliburn.features.work_memory.revisions import MemoryLayer
from caliburn.transport.model_tools.memory_reads import MemoryReadTools
from caliburn.transport.model_tools.memory_writes import MemoryWriteTools
from caliburn.workflows.memory_analysis import tools as analysis_tools
from caliburn.workflows.memory_reads import CandidateMemoryRead
from scripts import probe_consultant_tool_schema as schema_probe


@pytest.mark.parametrize("layer", list(MemoryLayer))
def test_unbound_definitions_equal_runtime_tools_and_keep_role_permissions(layer) -> None:
    scope = ExecutionScope(uuid4(), uuid4(), ExecutionKind.MEMORY_BATCH)
    stage = MemoryBatchPosition(
        scope.job_file_id, scope.execution_id, uuid4(), uuid4(), layer, uuid4()
    )
    binding = CandidateMemoryRead(scope, stage)
    runtime = analysis_tools.MemoryAnalysisTools(
        MemoryReadTools(Mock(), binding),
        MemoryWriteTools(Mock(), Mock(), binding, ExecutionWriter(scope, uuid4())),
    )
    definitions = analysis_tools.memory_analysis_tool_definitions(layer)
    assert definitions == runtime.definitions()
    assert tuple(item["name"] for item in definitions) == runtime.names
    reads = ["read_work_situation_map", "read_work_situation"]
    if layer == MemoryLayer.WORK_UNDERSTANDING:
        reads += ["read_work_understanding_map", "read_work_understanding"]
    assert runtime.names == (
        *reads,
        "read_interview",
        *(f"{action}_{layer.value}" for action in ("create", "update", "delete")),
    )
    assert all(item["strict"] is True for item in definitions)


@pytest.mark.parametrize("role", ["work_situation_analyst", "work_understanding_analyst"])
@pytest.mark.parametrize("status", [200, 400, 503])
@pytest.mark.asyncio
async def test_probe_sends_one_count_with_canonical_definitions_and_never_retries(
    role, status, monkeypatch, capsys
) -> None:
    synthetic_key = "synthetic-only-do-not-print"
    key_file = Path("synthetic-never-read.env")
    requests = []

    def read_key(path):
        assert path == key_file
        return synthetic_key

    monkeypatch.setattr(schema_probe, "read_openai_api_key", read_key)

    def respond(request):
        requests.append(request)
        assert request.url == "https://api.openai.com/v1/responses/input_tokens"
        assert request.method == "POST"
        assert all(value == 30 for value in request.extensions["timeout"].values())
        payload = json.loads(request.content)
        layer = MemoryLayer(role.removesuffix("_analyst"))
        assert payload["tools"] == analysis_tools.memory_analysis_tool_definitions(layer)
        assert payload["instructions"] == "Synthetic schema validation only."
        assert payload["input"] == [{"role": "user", "content": "Validate the tool schema."}]
        assert "max_output_tokens" not in payload
        if status == 200:
            return httpx2.Response(
                200, json={"object": "response.input_tokens", "input_tokens": 42}
            )
        return httpx2.Response(
            status,
            headers={"x-should-retry": "true", "retry-after": "0"},
            json={
                "error": {
                    "message": f"synthetic schema rejection {synthetic_key}",
                    "code": "invalid_schema",
                }
            },
        )

    def client_factory(*, api_key, timeout_seconds):
        return create_responses_client(
            api_key=api_key,
            timeout_seconds=timeout_seconds,
            http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(respond)),
        )

    monkeypatch.setattr(schema_probe, "create_responses_client", client_factory)
    if status == 200:
        await schema_probe.probe(key_file, role=role)
    else:
        with pytest.raises(SystemExit, match="1"):
            await schema_probe.probe(key_file, role=role)
    output = capsys.readouterr().out
    assert synthetic_key not in output
    record = json.loads(output)
    assert record["role"] == role
    assert record["http_requests"] == 1
    assert record["generation_requests"] == record["retries"] == 0
    assert len(requests) == 1
    if status == 200:
        assert record["input_tokens"] == 42
        assert len(record["definitions_sha256"]) == 64
    else:
        assert record["status"] == status
