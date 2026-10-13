"""Semantic source failures stay in the model repair loop, not an infrastructure retry."""

import json
from unittest.mock import AsyncMock, create_autospec
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from caliburn.features.executions.models import ExecutionKind, ExecutionScope, ExecutionWriter
from caliburn.features.job_description.model_references import JdModelReferences
from caliburn.features.work_memory.models import InvalidMemoryChangeError
from caliburn.transport.model_tools.jd_writes import JdWriteTools
from caliburn.workflows.job_description.item_creation import JdItemCreationWorkflow
from caliburn.workflows.job_description.item_deletion import JdItemDeletionWorkflow
from caliburn.workflows.job_description.item_movement import JdItemMovementWorkflow
from caliburn.workflows.job_description.item_revision import JdItemRevisionWorkflow
from caliburn.workflows.job_description.profile_writes import JdProfileWriteWorkflow
from caliburn.workflows.job_description.task_writes import JdTaskWriteWorkflow
from caliburn.workflows.work_memory.reads import PublishedMemoryRead


@pytest.mark.asyncio
async def test_invalid_memory_title_becomes_actionable_rejection() -> None:
    execute = AsyncMock()
    # 工具只需要用例行為；替身刻意沒有 sessions 等內部依賴。
    profile = create_autospec(JdProfileWriteWorkflow, instance=True, spec_set=True)
    profile.prepare = AsyncMock(side_effect=InvalidMemoryChangeError("invalid source title"))
    tasks = create_autospec(JdTaskWriteWorkflow, instance=True)
    scope = ExecutionScope(uuid4(), uuid4(), ExecutionKind.CONSULTANT_TURN)
    tools = JdWriteTools(
        profile,
        tasks,
        PublishedMemoryRead(scope, uuid4(), 3),
        ExecutionWriter(scope, uuid4()),
        references=JdModelReferences(async_sessionmaker(), scope.job_file_id),
        execute_edit=execute,
        creations=create_autospec(JdItemCreationWorkflow, instance=True),
        revisions=create_autospec(JdItemRevisionWorkflow, instance=True),
        deletions=create_autospec(JdItemDeletionWorkflow, instance=True),
        movements=create_autospec(JdItemMovementWorkflow, instance=True),
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
    execute.assert_not_awaited()
