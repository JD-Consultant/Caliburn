"""Semantic source failures stay in the model repair loop, not an infrastructure retry."""

import json
from unittest.mock import AsyncMock, create_autospec
from uuid import uuid4

import pytest

from caliburn.features.executions.models import ExecutionKind, ExecutionScope, ExecutionWriter
from caliburn.features.work_memory.models import InvalidMemoryChangeError
from caliburn.transport.model_tools.jd_writes import JdWriteTools
from caliburn.workflows.jd_profile_writes import JdProfileWriteWorkflow
from caliburn.workflows.jd_task_writes import JdTaskWriteWorkflow
from caliburn.workflows.memory_reads import PublishedMemoryRead


@pytest.mark.asyncio
async def test_invalid_memory_title_becomes_actionable_rejection() -> None:
    profile = create_autospec(JdProfileWriteWorkflow, instance=True)
    profile.prepare = AsyncMock(side_effect=InvalidMemoryChangeError("invalid source title"))
    tasks = create_autospec(JdTaskWriteWorkflow, instance=True)
    scope = ExecutionScope(uuid4(), uuid4(), ExecutionKind.CONSULTANT_TURN)
    tools = JdWriteTools(
        profile, tasks, PublishedMemoryRead(scope, uuid4(), 3), ExecutionWriter(scope, uuid4())
    )
    result = await tools.prepare(
        "revise_jd_profile",
        json.dumps(
            {
                "changes": [
                    {
                        "action": "add_source",
                        "field": "purpose",
                        "source": {"kind": "work_situation", "target_title": " "},
                    }
                ]
            }
        ),
        uuid4(),
    )
    assert isinstance(result, str)
    assert "invalid_arguments" in result
    profile.execute.assert_not_called()
