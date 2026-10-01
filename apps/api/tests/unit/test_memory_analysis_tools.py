"""Role assembly preserves existing Memory contracts and checkpoint identities."""

from dataclasses import replace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from openai.types.responses import ResponseFunctionToolCall

from caliburn.adapters.graph_checkpointer import create_graph_serializer
from caliburn.features.work_memory.candidates import CreateMemoryObject, MemoryBatchPosition
from caliburn.features.work_memory.models import MemoryContent
from caliburn.features.work_memory.revisions import MemoryLayer
from caliburn.transport.model_tools.memory_analysis import (
    MEMORY_CHECKPOINT_TYPES,
    MemoryAnalysisTools,
)
from caliburn.transport.model_tools.memory_writes import PreparedMemoryToolCall
from caliburn.workflows.memory_analysis.results import AnalysisComplete, SituationGap, parse_outcome


def prepared() -> PreparedMemoryToolCall:
    stage = MemoryBatchPosition(*(uuid4() for _ in range(4)), MemoryLayer.WORK_SITUATION, uuid4())
    return PreparedMemoryToolCall(
        CreateMemoryObject(uuid4(), stage, stage.phase, MemoryContent("盤點", "月末核對", "原文")),
        '{"status":"created"}',
    )


@pytest.mark.asyncio
async def test_existing_contracts_route_reads_and_writes_without_call_id_as_operation() -> None:
    reads, writes = Mock(), Mock()
    reads.names = ("read_work_situation_map", "read_interview")
    writes.names = ("create_work_situation",)
    reads.definitions.return_value = [{"name": "read_work_situation_map"}]
    writes.definitions.return_value = [{"name": "create_work_situation"}]
    reads.invoke = AsyncMock(return_value='{"items":[]}')
    command = prepared()
    writes.prepare = AsyncMock(return_value=command)
    writes.execute = AsyncMock(return_value=command.success_output)
    tools = MemoryAnalysisTools(reads, writes)
    assert tools.definitions() == reads.definitions() + writes.definitions()
    operation_id = uuid4()
    call = ResponseFunctionToolCall(
        type="function_call",
        call_id="native-not-an-operation-id",
        name="read_interview",
        arguments="{}",
    )
    assert await tools.prepare(call, operation_id) == '{"items":[]}'
    call.name = "create_work_situation"
    assert await tools.prepare(call, operation_id) == command
    writes.prepare.assert_awaited_once_with(call.name, "{}", command_id=operation_id)
    call.name = "update_work_understanding"
    assert '"scope_not_allowed"' in await tools.prepare(call, operation_id)
    assert await tools.execute(command) == command.success_output


@pytest.mark.asyncio
async def test_official_serializer_and_malformed_nested_command_rejection() -> None:
    original = prepared()
    serde = create_graph_serializer(allowed_types=MEMORY_CHECKPOINT_TYPES)
    restored = serde.loads_typed(serde.dumps_typed(original))
    writes = Mock(execute=AsyncMock(return_value=original.success_output))
    tools = MemoryAnalysisTools(Mock(), writes)
    assert await tools.execute(restored) == original.success_output
    writes.execute.reset_mock()
    malformed = replace(original, command=replace(original.command, layer="work_situation"))
    for value in (None, {}, malformed, replace(original, command={})):
        with pytest.raises((TypeError, ValueError)):
            await tools.execute(value)
    writes.execute.assert_not_awaited()


def test_typed_final_result_does_not_turn_arbitrary_text_into_completion() -> None:
    assert isinstance(
        parse_outcome('{"status":"complete"}', MemoryLayer.WORK_SITUATION), AnalysisComplete
    )
    gap = (
        '{"status":"needs_situation","gaps":[{"target_title":"盤點","question":"誰核准？",'
        '"needed_clarification":"本人權限","interview_sequences":[2]}]}'
    )
    result = parse_outcome(gap, MemoryLayer.WORK_UNDERSTANDING)
    assert isinstance(result.gaps[0], SituationGap)
    for text, layer in [
        (gap, MemoryLayer.WORK_SITUATION),
        ("done", MemoryLayer.WORK_UNDERSTANDING),
        ('{"status":"needs_situation","gaps":[]}', MemoryLayer.WORK_UNDERSTANDING),
        ('{"status":"complete","understanding":"private"}', MemoryLayer.WORK_UNDERSTANDING),
    ]:
        with pytest.raises(ValueError):
            parse_outcome(text, layer)
