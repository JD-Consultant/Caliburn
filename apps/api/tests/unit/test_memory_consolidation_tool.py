"""Notification prepares a recoverable intent, never prematurely starts a batch."""

import json
from uuid import uuid4

import pytest

from caliburn.features.executions.models import ExecutionKind, ExecutionScope, ExecutionWriter
from caliburn.features.work_memory.consolidation_models import MemoryConsolidationIntent
from caliburn.transport.model_tools.memory_consolidation import MemoryConsolidationTools
from caliburn.workflows.memory_consolidation import MemoryConsolidationWorkflow


class RecordingRequests(MemoryConsolidationWorkflow):
    def __init__(self) -> None:
        self.commands = []

    async def request(self, writer, command_id):
        self.commands.append((writer, command_id))
        return MemoryConsolidationIntent(uuid4())


def bound_tools():
    writer = ExecutionWriter(
        ExecutionScope(uuid4(), uuid4(), ExecutionKind.CONSULTANT_TURN), uuid4()
    )
    requests = RecordingRequests()
    return MemoryConsolidationTools(requests, writer), requests, writer


async def test_prepared_intent_executes_only_after_checkpoint_with_same_app_identity():
    tool, requests, writer = bound_tools()
    operation_id = uuid4()
    prepared = tool.prepare("{}", operation_id)
    assert isinstance(prepared, dict)
    assert requests.commands == []
    restored = json.loads(json.dumps(prepared))
    result = await tool.execute(restored)
    assert json.loads(result) == {"message": "已記錄整理要求；本輪成功完成後由系統處理。"}
    assert requests.commands == [(writer, operation_id)]


@pytest.mark.parametrize("arguments", ['{"through_sequence":8}', '{"job_file_id":"other"}', "[]"])
async def test_model_cannot_choose_private_source_boundary(arguments):
    tool, requests, _ = bound_tools()
    result = tool.prepare(arguments, uuid4())
    assert isinstance(result, str)
    assert json.loads(result)["code"] == "invalid_arguments"
    assert requests.commands == []


async def test_saved_intent_from_another_execution_cannot_be_dispatched():
    tool, requests, _ = bound_tools()
    other, _, _ = bound_tools()
    prepared = other.prepare("{}", uuid4())
    with pytest.raises(ValueError):
        await tool.execute(prepared)
    assert requests.commands == []
