"""The dormant exclusion read exposes content only, using the App's original binding."""

import json
from uuid import uuid4

import pytest

from caliburn.agents.job_consultant.tools import consultant_tool_definitions
from caliburn.features.executions.models import (
    ExecutionKind,
    ExecutionNotFoundError,
    ExecutionScope,
    ExecutionStateError,
)
from caliburn.features.interviews.models import (
    InterviewScopeError,
    InterviewSourceNotAvailableError,
)
from caliburn.features.occupation_references.models import ReferenceStateError
from caliburn.features.work_memory.candidates import (
    MemoryBatchPosition,
    MemoryCandidateStateError,
    MemoryPermissionError,
)
from caliburn.features.work_memory.revisions import MemoryLayer, MemoryRevisionNotFoundError
from caliburn.transport.model_tools.excluded_work_reads import (
    ExcludedWorkReadTools,
    excluded_work_read_definitions,
)
from caliburn.transport.model_tools.memory_analysis import memory_analysis_tool_definitions
from caliburn.workflows.memory_reads import CandidateMemoryRead, PublishedMemoryRead


class RecordingReader:
    def __init__(self, result=("正式環境部署", "薪資核算"), error=None):
        self.result = result
        self.error = error
        self.calls = []

    async def read(self, binding):
        self.calls.append(binding)
        if self.error is not None:
            raise self.error
        return self.result


def binding(kind):
    job_file_id, execution_id = uuid4(), uuid4()
    if kind == "published":
        scope = ExecutionScope(job_file_id, execution_id, ExecutionKind.CONSULTANT_TURN)
        return PublishedMemoryRead(scope, uuid4(), 12)
    scope = ExecutionScope(job_file_id, execution_id, ExecutionKind.MEMORY_BATCH)
    stage = MemoryBatchPosition(
        job_file_id,
        execution_id,
        uuid4(),
        uuid4(),
        MemoryLayer(kind),
        uuid4(),
    )
    return CandidateMemoryRead(scope, stage)


def test_zero_argument_schema_is_strict_and_tool_is_not_in_any_active_role_registry():
    reader = RecordingReader()
    tools = ExcludedWorkReadTools(reader, binding("published"))
    definitions = excluded_work_read_definitions()
    assert tools.definitions() == definitions
    assert tools.names == ("read_excluded_work",)
    assert len(definitions) == 1
    definition = definitions[0]
    assert definition["name"] == "read_excluded_work"
    assert definition["strict"] is True
    assert definition["parameters"] == {
        "title": "ReadExcludedWorkArguments",
        "type": "object",
        "additionalProperties": False,
        "properties": {},
        "required": [],
    }
    active = [
        *consultant_tool_definitions(),
        *memory_analysis_tool_definitions(MemoryLayer.WORK_SITUATION),
        *memory_analysis_tool_definitions(MemoryLayer.WORK_UNDERSTANDING),
    ]
    assert "read_excluded_work" not in {item["name"] for item in active}
    assert reader.calls == []


@pytest.mark.parametrize("kind", ["published", "work_situation", "work_understanding"])
async def test_read_passes_original_binding_and_returns_only_complete_excluded_scope_text(kind):
    original = binding(kind)
    scopes = ("只負責介面測試，不負責正式環境部署", " 薪資核算\n ")
    reader = RecordingReader(scopes)
    tools = ExcludedWorkReadTools(reader, original)
    result = json.loads(await tools.invoke("read_excluded_work", "{}"))
    assert reader.calls == [original]
    assert reader.calls[0] is original
    assert result == {"excluded_work": list(scopes)}


async def test_empty_exclusion_is_success_and_not_an_error():
    tools = ExcludedWorkReadTools(RecordingReader(()), binding("published"))
    assert json.loads(await tools.invoke("read_excluded_work", "{}")) == {"excluded_work": []}


@pytest.mark.parametrize(
    "arguments",
    [
        "[]",
        "null",
        '{"job_file_id":"other"}',
        '{"through_sequence":999}',
        '{"snapshot_id":"other"}',
        '{"stage_id":"other"}',
        '{"add":["部署"]}',
    ],
)
async def test_model_cannot_supply_scope_frontier_or_mutation_fields(arguments):
    reader = RecordingReader()
    tools = ExcludedWorkReadTools(reader, binding("published"))
    result = json.loads(await tools.invoke("read_excluded_work", arguments))
    assert result["code"] == "invalid_arguments"
    assert reader.calls == []


@pytest.mark.parametrize("name", ["update_excluded_work", "select_occupation_references", "other"])
async def test_read_facade_does_not_allow_mutations_or_other_tool_names(name):
    reader = RecordingReader()
    tools = ExcludedWorkReadTools(reader, binding("published"))
    result = json.loads(await tools.invoke(name, "{}"))
    assert result["code"] == "scope_not_allowed"
    assert reader.calls == []


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (ExecutionNotFoundError("private details"), "scope_not_allowed"),
        (ExecutionStateError("private details"), "scope_not_allowed"),
        (MemoryPermissionError("private details"), "scope_not_allowed"),
        (InterviewScopeError("private details"), "scope_not_allowed"),
        (MemoryCandidateStateError("private details"), "target_stale"),
        (MemoryRevisionNotFoundError("private details"), "source_not_available"),
        (InterviewSourceNotAvailableError("private details"), "source_not_available"),
        (ReferenceStateError("private details"), "source_not_available"),
    ],
)
async def test_expected_binding_failures_return_safe_rejection_not_an_empty_list(error, code):
    tools = ExcludedWorkReadTools(RecordingReader(error=error), binding("published"))
    raw = await tools.invoke("read_excluded_work", "{}")
    result = json.loads(raw)
    assert result["status"] == "rejected"
    assert result["code"] == code
    assert "excluded_work" not in result
    assert "private" not in raw


async def test_unexpected_persistence_failure_remains_a_runtime_error():
    error = RuntimeError("database offline")
    tools = ExcludedWorkReadTools(RecordingReader(error=error), binding("published"))
    with pytest.raises(RuntimeError) as raised:
        await tools.invoke("read_excluded_work", "{}")
    assert raised.value is error


async def test_capacity_limit_never_returns_a_truncated_exclusion_list():
    tools = ExcludedWorkReadTools(RecordingReader(), binding("published"), max_result_characters=5)
    result = json.loads(await tools.invoke("read_excluded_work", "{}"))
    assert result["code"] == "read_limit_exceeded"
    assert "excluded_work" not in result
