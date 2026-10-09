"""Optional reference capabilities route through the existing role tool boundaries."""

import json
from dataclasses import replace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from openai.types.responses import ResponseFunctionToolCall

from caliburn.adapters.memory_cpu import MemoryCpu
from caliburn.adapters.openai_responses import ResponseRequest
from caliburn.agents.job_consultant import runner as consultant_runner_module
from caliburn.agents.job_consultant.configuration import (
    ConsultantConfiguration,
    ToolDescriptionOverride,
)
from caliburn.agents.job_consultant.context_binding import TurnContext
from caliburn.agents.job_consultant.runner import ConsultantRunner
from caliburn.agents.job_consultant.tools import ConsultantTools, consultant_tool_definitions
from caliburn.agents.memory_analysis.runner import MemoryAnalysisRunner
from caliburn.agents.work_situation_analyst import runner as situation_runner_module
from caliburn.agents.work_understanding_analyst import runner as understanding_runner_module
from caliburn.features.executions.models import (
    ExecutionKind,
    ExecutionScope,
    ExecutionStateError,
    ExecutionWriter,
)
from caliburn.features.job_description.candidates import JdCandidatePosition, JdCandidateScope
from caliburn.features.work_memory.candidates import MemoryBatchPosition
from caliburn.features.work_memory.revisions import MemoryLayer
from caliburn.settings import ModelSettings
from caliburn.transport.model_tools.excluded_work_reads import ExcludedWorkReadTools
from caliburn.transport.model_tools.memory_analysis import (
    MemoryAnalysisTools,
    memory_analysis_tool_definitions,
)
from caliburn.transport.model_tools.occupation_references import (
    OccupationReferenceTools,
    occupation_reference_definitions,
)
from caliburn.workflows.memory_reads import CandidateMemoryRead, PublishedMemoryRead
from tests.contracts.test_tool_schema_strictness import SchemaWalk


def handler(names=()):
    result = Mock()
    result.names = names
    result.definitions.return_value = [{"name": name} for name in names]
    result.invoke = AsyncMock(return_value="read result")
    result.prepare = AsyncMock(return_value={"kind": "occupation_reference_state_change"})
    result.execute = AsyncMock(return_value="write result")
    return result


def reference_handler():
    result = handler(OccupationReferenceTools.names)
    result.read_names = OccupationReferenceTools.read_names
    result.write_names = OccupationReferenceTools.write_names
    return result


def call(name, arguments="{}"):
    return ResponseFunctionToolCall(
        type="function_call",
        name=name,
        arguments=arguments,
        call_id="native_call",
    )


def test_default_role_definitions_keep_reference_tools_disabled():
    assert set(OccupationReferenceTools.names).isdisjoint(
        item["name"] for item in consultant_tool_definitions()
    )
    for layer in MemoryLayer:
        assert "read_excluded_work" not in {
            item["name"] for item in memory_analysis_tool_definitions(layer)
        }


def test_enabled_consultant_adds_five_reference_contracts_only():
    default = consultant_tool_definitions()
    enabled = consultant_tool_definitions(occupation_references_enabled=True)
    assert enabled[: len(default)] == default
    assert tuple(item["name"] for item in enabled[len(default) :]) == OccupationReferenceTools.names
    assert "read_excluded_work" not in {item["name"] for item in enabled}


@pytest.mark.parametrize("layer", list(MemoryLayer))
def test_enabled_analyst_only_adds_exclusion_read(layer):
    default = memory_analysis_tool_definitions(layer)
    enabled = memory_analysis_tool_definitions(layer, excluded_work_enabled=True)
    assert [item for item in enabled if item["name"] != "read_excluded_work"] == default
    assert len(enabled) == len(default) + 1
    assert set(OccupationReferenceTools.names).isdisjoint(item["name"] for item in enabled)


def test_enabled_tool_templates_use_the_existing_closed_strict_schema_rules():
    definitions = [
        *consultant_tool_definitions(occupation_references_enabled=True),
        *memory_analysis_tool_definitions(MemoryLayer.WORK_SITUATION, excluded_work_enabled=True),
        *memory_analysis_tool_definitions(
            MemoryLayer.WORK_UNDERSTANDING, excluded_work_enabled=True
        ),
    ]
    for definition in definitions:
        assert definition["strict"] is True
        schema = definition["parameters"]
        SchemaWalk(schema.get("$defs", {})).visit(schema, definition["name"])


@pytest.mark.parametrize("name", OccupationReferenceTools.read_names)
async def test_consultant_reference_reads_return_observation_without_preparing_write(name):
    refs = reference_handler()
    tools = ConsultantTools(*(handler() for _ in range(6)), occupation_references=refs)
    operation_id = uuid4()
    assert await tools.prepare(call(name, '{"query":"介面"}'), operation_id) == "read result"
    refs.invoke.assert_awaited_once_with(name, '{"query":"介面"}')
    refs.prepare.assert_not_awaited()
    refs.execute.assert_not_awaited()
    assert tuple(item["name"] for item in tools.definitions()) == tools.names


@pytest.mark.parametrize("name", OccupationReferenceTools.write_names)
async def test_consultant_reference_writes_preserve_saved_json_command_and_operation_id(name):
    refs = reference_handler()
    tools = ConsultantTools(*(handler() for _ in range(6)), occupation_references=refs)
    operation_id = uuid4()
    prepared = await tools.prepare(call(name, '{"add":["部署"],"remove":[]}'), operation_id)
    refs.prepare.assert_awaited_once_with(name, '{"add":["部署"],"remove":[]}', operation_id)
    refs.execute.assert_not_awaited()
    restored = json.loads(json.dumps(prepared))
    assert await tools.execute(restored) == "write result"
    refs.execute.assert_awaited_once_with(restored)


async def test_disabled_consultant_does_not_dispatch_reference_call_or_saved_command():
    jd_writes = handler()
    tools = ConsultantTools(handler(), handler(), jd_writes, handler(), handler(), handler())
    output = await tools.prepare(call("update_excluded_work"), uuid4())
    assert json.loads(output)["code"] == "scope_not_allowed"
    with pytest.raises(ValueError):
        await tools.execute({"kind": "occupation_reference_state_change"})
    jd_writes.execute.assert_not_awaited()


async def test_analyst_exclusion_tool_is_read_only_and_preserves_write_path():
    read = handler(("read_work_situation",))
    writes = handler(("create_work_situation",))
    excluded = handler(ExcludedWorkReadTools.names)
    tools = MemoryAnalysisTools(read, writes, excluded_work=excluded)
    assert await tools.prepare(call("read_excluded_work"), uuid4()) == "read result"
    excluded.invoke.assert_awaited_once_with("read_excluded_work", "{}")
    excluded.prepare.assert_not_awaited()
    writes.prepare.assert_not_awaited()
    assert tuple(item["name"] for item in tools.definitions()) == tools.names
    for name in OccupationReferenceTools.names:
        result = await tools.prepare(call(name), uuid4())
        assert json.loads(result)["code"] == "scope_not_allowed"


def request(definitions):
    return ResponseRequest(
        model="gpt-6-luna",
        instructions="saved role instructions",
        input_items=[],
        tools=definitions,
        reasoning_effort="high",
        max_output_tokens=1000,
    )


def consultant_context(enabled):
    writer = ExecutionWriter(
        ExecutionScope(uuid4(), uuid4(), ExecutionKind.CONSULTANT_TURN),
        uuid4(),
    )
    context = TurnContext(
        request(consultant_tool_definitions(occupation_references_enabled=enabled)),
        PublishedMemoryRead(writer.scope, None, 0),
        JdCandidatePosition(JdCandidateScope(writer.scope.execution_id, uuid4()), uuid4(), uuid4()),
        uuid4(),
    )
    return writer, context


@pytest.mark.parametrize("configured", [False, True])
async def test_old_consultant_request_never_initializes_references_when_configuration_changes(
    configured,
    monkeypatch,
):
    workflow_factory = Mock()
    monkeypatch.setattr(consultant_runner_module, "OccupationReferenceWorkflow", workflow_factory)
    writer, context = consultant_context(False)
    runner = ConsultantRunner(
        Mock(),
        Mock(),
        Mock(),
        ModelSettings(api_key="synthetic"),
        occupation_references=Mock() if configured else None,
    )
    tools = await runner._tools(writer, context, Mock())
    assert set(OccupationReferenceTools.names).isdisjoint(tools.names)
    workflow_factory.assert_not_called()


async def test_reference_enabled_saved_request_starts_candidate_before_exposing_handlers(
    monkeypatch,
):
    workflow = Mock(start=AsyncMock())
    workflow_factory = Mock(return_value=workflow)
    monkeypatch.setattr(consultant_runner_module, "OccupationReferenceWorkflow", workflow_factory)
    writer, context = consultant_context(True)
    reference_client = Mock()
    runner = ConsultantRunner(
        Mock(),
        Mock(),
        Mock(),
        ModelSettings(api_key="synthetic"),
        occupation_references=reference_client,
    )
    tools = await runner._tools(writer, context, Mock())
    workflow_factory.assert_called_once_with(runner.sessions, reference_client)
    workflow.start.assert_awaited_once_with(writer)
    assert set(OccupationReferenceTools.names) <= set(tools.names)


async def test_write_handler_preserves_the_captured_request(
    monkeypatch,
):
    workflow = Mock(start=AsyncMock())
    monkeypatch.setattr(
        consultant_runner_module,
        "OccupationReferenceWorkflow",
        Mock(return_value=workflow),
    )
    writer, context = consultant_context(True)
    saved = request(
        [
            *consultant_tool_definitions(),
            *occupation_reference_definitions(),
        ]
    )
    original_payload = saved.create_payload()
    runner = ConsultantRunner(
        Mock(),
        Mock(),
        Mock(),
        ModelSettings(api_key="synthetic"),
        occupation_references=Mock(),
    )
    tools = await runner._tools(writer, replace(context, request=saved), Mock())
    assert tools.occupation_references is not None
    assert saved.create_payload() == original_payload


@pytest.mark.parametrize(
    "names",
    [
        ("update_excluded_work",),
        ("select_occupation_references", "update_excluded_work"),
    ],
)
async def test_candidate_descriptions_keep_status_handlers_for_new_captured_requests(
    names, monkeypatch
):
    workflow = Mock(start=AsyncMock())
    monkeypatch.setattr(
        consultant_runner_module,
        "OccupationReferenceWorkflow",
        Mock(return_value=workflow),
    )
    writer, context = consultant_context(True)
    runner = ConsultantRunner(
        Mock(),
        Mock(),
        Mock(),
        ModelSettings(api_key="synthetic"),
        occupation_references=Mock(),
        configuration=ConsultantConfiguration(
            tool_descriptions=tuple(ToolDescriptionOverride(name, "候選寫入說明") for name in names)
        ),
    )
    saved = runner._template(stream=False)
    original_payload = saved.create_payload()
    tools = await runner._tools(writer, replace(context, request=saved), Mock())
    assert tools.occupation_references is not None
    assert saved.create_payload() == original_payload


async def test_saved_reference_request_with_missing_client_fails_before_history_model_work(
    monkeypatch,
):
    writer, context = consultant_context(True)
    history = Mock(
        resolve_template=AsyncMock(return_value=context.request),
        prepare_history=AsyncMock(),
    )
    monkeypatch.setattr(consultant_runner_module, "RoleContextHistory", Mock(return_value=history))
    monkeypatch.setattr(consultant_runner_module, "fix_execution_policy", AsyncMock())
    monkeypatch.setattr(ConsultantRunner, "_recover_completed", AsyncMock(return_value=None))
    model = Mock()
    model.executor.count_input = AsyncMock()
    model.executor.request_model = AsyncMock()
    monkeypatch.setattr(consultant_runner_module, "bind_model_runtime", Mock(return_value=model))
    runner = ConsultantRunner(Mock(), InMemorySaver(), Mock(), ModelSettings(api_key="synthetic"))
    with pytest.raises(ExecutionStateError):
        await runner.run(writer)
    history.resolve_template.assert_awaited_once()
    history.prepare_history.assert_not_awaited()
    model.executor.count_input.assert_not_awaited()
    model.executor.request_model.assert_not_awaited()


async def test_partial_reference_bundle_is_rejected_before_candidate_initialization(monkeypatch):
    factory = Mock()
    monkeypatch.setattr(consultant_runner_module, "OccupationReferenceWorkflow", factory)
    writer, context = consultant_context(True)
    selected = [
        tool
        for tool in context.request.create_payload()["tools"]
        if tool["name"] != "update_excluded_work"
    ]
    runner = ConsultantRunner(
        Mock(),
        Mock(),
        Mock(),
        ModelSettings(api_key="synthetic"),
        occupation_references=Mock(),
    )
    with pytest.raises(ExecutionStateError):
        await runner._tools(writer, replace(context, request=request(selected)), Mock())
    factory.assert_not_called()


@pytest.mark.parametrize("name", OccupationReferenceTools.names)
async def test_duplicate_saved_reference_tool_rejects_before_candidate_initialization(
    name,
    monkeypatch,
):
    factory = Mock(return_value=Mock(start=AsyncMock()))
    monkeypatch.setattr(consultant_runner_module, "OccupationReferenceWorkflow", factory)
    writer, context = consultant_context(True)
    definitions = context.request.create_payload()["tools"]
    definitions.append(next(tool.copy() for tool in definitions if tool["name"] == name))
    runner = ConsultantRunner(
        Mock(),
        Mock(),
        Mock(),
        ModelSettings(api_key="synthetic"),
        occupation_references=Mock(),
    )
    with pytest.raises(ExecutionStateError):
        await runner._tools(writer, replace(context, request=request(definitions)), Mock())
    factory.assert_not_called()


@pytest.mark.parametrize(("configured", "saved_enabled"), [(True, False), (False, True)])
def test_memory_handlers_follow_saved_request_instead_of_today_enable_flag(
    configured, saved_enabled
):
    writer = ExecutionWriter(
        ExecutionScope(uuid4(), uuid4(), ExecutionKind.MEMORY_BATCH),
        uuid4(),
    )
    stage = MemoryBatchPosition(
        writer.scope.job_file_id,
        writer.scope.execution_id,
        uuid4(),
        uuid4(),
        MemoryLayer.WORK_SITUATION,
        uuid4(),
    )
    binding = CandidateMemoryRead(writer.scope, stage)
    saved_request = request(
        memory_analysis_tool_definitions(
            stage.phase,
            excluded_work_enabled=saved_enabled,
        )
    )
    runner = MemoryAnalysisRunner(
        Mock(),
        Mock(),
        Mock(),
        ModelSettings(api_key="synthetic"),
        excluded_work_enabled=configured,
        cpu=MemoryCpu(),
    )
    tools = runner._tools(writer, binding, saved_request)
    assert ("read_excluded_work" in tools.names) is saved_enabled
    assert set(OccupationReferenceTools.names).isdisjoint(tools.names)


@pytest.mark.parametrize("layer", list(MemoryLayer))
async def test_public_memory_runner_forwards_explicit_enablement_to_shared_runner(
    layer, monkeypatch
):
    module = (
        situation_runner_module
        if layer == MemoryLayer.WORK_SITUATION
        else understanding_runner_module
    )
    runner_type = (
        module.WorkSituationAnalystRunner
        if layer == MemoryLayer.WORK_SITUATION
        else module.WorkUnderstandingAnalystRunner
    )
    shared = Mock(run=AsyncMock(return_value="analysis result"))
    factory = Mock(return_value=shared)
    monkeypatch.setattr(module, "MemoryAnalysisRunner", factory)
    public = runner_type(
        Mock(),
        Mock(),
        Mock(),
        ModelSettings(api_key="synthetic"),
        cpu=MemoryCpu(),
        excluded_work_enabled=True,
    )
    writer = ExecutionWriter(ExecutionScope(uuid4(), uuid4(), ExecutionKind.MEMORY_BATCH), uuid4())
    stage = MemoryBatchPosition(
        writer.scope.job_file_id,
        writer.scope.execution_id,
        uuid4(),
        uuid4(),
        layer,
        uuid4(),
    )
    extra = {"situation_changes": []} if layer == MemoryLayer.WORK_UNDERSTANDING else {}
    assert await public.run(writer, stage, **extra) == "analysis result"
    factory.assert_called_once_with(
        public.sessions,
        public.checkpointer,
        public.client,
        public.settings,
        public.cpu,
        excluded_work_enabled=True,
    )
