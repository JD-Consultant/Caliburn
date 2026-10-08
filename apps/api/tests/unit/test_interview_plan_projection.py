"""A pins a complete native C and one plan projection before parent continuation."""

import json
from copy import deepcopy
from unittest.mock import AsyncMock, Mock
from uuid import uuid4, uuid7

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from caliburn.agent_execution.context_compaction import run_context_compaction
from caliburn.agents.job_consultant.interview_plan_projection import (
    _restore_binding,
    bind_interview_plan_compaction,
)
from caliburn.features.executions.history_models import AgentRole
from caliburn.features.executions.models import ExecutionKind, ExecutionScope, ExecutionWriter
from caliburn.features.interview_plans.models import PlanPosition, PlanSnapshot, PlanStateError
from caliburn.workflows.context_history import RoleContextHistory
from tests.unit.test_context_compaction import COMPACTED, options


def scenario(monkeypatch, saver=None):
    saver = saver or InMemorySaver()
    writer = ExecutionWriter(
        ExecutionScope(uuid4(), uuid4(), ExecutionKind.CONSULTANT_TURN), uuid4()
    )
    work = RoleContextHistory(Mock(), writer, AgentRole.JOB_CONSULTANT, saver)
    active = AsyncMock()
    monkeypatch.setattr(RoleContextHistory, "ensure_active", active)
    events = []
    args = options(events)
    parent_id = uuid4()
    args["thread_id"] = f"{work.response_thread_id}:compact:{parent_id}"

    async def original(request, count, source_id):
        assert source_id == parent_id
        assert request == args["request"]
        assert count == args["input_count"]
        return await run_context_compaction(saver, **args)

    plan = PlanSnapshot(
        PlanPosition(writer.scope.job_file_id, writer.scope.execution_id, uuid4()),
        "## 焦點\n退貨例外\n## 未釐清\n- 跳題前尚未問完的簽核界線\n",
    )
    reader = AsyncMock(return_value=plan)
    compact = bind_interview_plan_compaction(work, original, read_plan=reader)
    return work, args, parent_id, compact, reader, active, events


@pytest.mark.parametrize("body", [None, "", "## 未釐清\n- 誰決定退回\n"])
async def test_saved_projection_preserves_entire_c_and_never_reads_new_head(body, monkeypatch):
    work, args, parent_id, _, reader, _, events = scenario(monkeypatch)
    current = reader.return_value
    reader.return_value = PlanSnapshot(current.position, body)

    async def original(request, count, source_id):
        return await run_context_compaction(work.checkpointer, **args)

    compact = bind_interview_plan_compaction(work, original, read_plan=reader)
    result = await compact(args["request"], args["input_count"], parent_id)
    assert result[:-1] == COMPACTED["output"]
    assert json.loads(result[-1]["content"]) == {
        "data_kind": "consultant_interview_plan",
        "plan": body,
    }
    reader.return_value = PlanSnapshot(current.position, "later head must not replace projection")
    result[-1]["content"] = "caller mutation"
    restored = await compact(args["request"], args["input_count"], parent_id)
    assert restored[:-1] == COMPACTED["output"]
    assert json.loads(restored[-1]["content"])["plan"] == body
    assert reader.await_count == 1
    assert len([event for event in events if event[0] == "compact"]) == 1


async def test_failed_plan_read_resumes_saved_c_position_even_if_latest_changes(monkeypatch):
    work, args, parent_id, compact, reader, _, _ = scenario(monkeypatch)
    plan = reader.return_value
    reader.side_effect = ConnectionError("synthetic plan unavailable")
    with pytest.raises(ConnectionError, match="plan unavailable"):
        await compact(args["request"], args["input_count"], parent_id)
    # Add a later native checkpoint under the same thread to expose a latest-reader bug.
    config = {"configurable": {"thread_id": args["thread_id"], "checkpoint_ns": ""}}
    saved = await work.checkpointer.aget_tuple(config)
    later = deepcopy(saved.checkpoint)
    later["id"] = str(uuid7())
    later["channel_values"]["compaction_snapshot"]["output"].append(
        {"role": "user", "content": "later C is not the originally pinned C"}
    )
    await work.checkpointer.aput(config, later, saved.metadata, {})
    reader.side_effect = None
    reader.return_value = plan
    restored = await compact(args["request"], args["input_count"], parent_id)
    assert restored[:-1] == COMPACTED["output"]


async def test_inactive_work_delegates_native_recovery_before_any_plan_io(monkeypatch):
    work, args, parent_id, compact, reader, active, events = scenario(monkeypatch)
    active.side_effect = PermissionError("synthetic inactive")
    with pytest.raises(PermissionError, match="inactive"):
        await compact(args["request"], args["input_count"], parent_id)
    assert events[-1] == ("account", "cmp_synthetic")
    reader.assert_not_awaited()
    assert (
        await work.checkpointer.aget_tuple(
            {
                "configurable": {
                    "thread_id": f"{work.response_thread_id}:plan_projection:{parent_id}"
                }
            }
        )
        is None
    )


@pytest.mark.parametrize("wrong", ["missing", "scope"])
async def test_missing_or_wrong_scope_candidate_never_returns_projection(wrong, monkeypatch):
    _, args, parent_id, compact, reader, _, _ = scenario(monkeypatch)
    reader.return_value = (
        None
        if wrong == "missing"
        else PlanSnapshot(PlanPosition(uuid4(), uuid4(), uuid4()), "another Turn")
    )
    with pytest.raises(PlanStateError):
        await compact(args["request"], args["input_count"], parent_id)


class ProjectionAckFault(InMemorySaver):
    fail = True

    async def aput(self, config, checkpoint, metadata, new_versions):
        result = await super().aput(config, checkpoint, metadata, new_versions)
        if self.fail and checkpoint["channel_values"].get("projection"):
            raise ConnectionError("synthetic projection acknowledgement lost")
        return result


async def test_lost_projection_ack_restores_original_without_replanning(monkeypatch):
    saver = ProjectionAckFault()
    _, args, parent_id, compact, reader, _, events = scenario(monkeypatch, saver)
    body = reader.return_value.body
    with pytest.raises(ConnectionError, match="acknowledgement lost"):
        await compact(args["request"], args["input_count"], parent_id)
    saver.fail = False
    reader.side_effect = AssertionError("saved projection must not read a newer plan")
    restored = await compact(args["request"], args["input_count"], parent_id)
    assert restored[:-1] == COMPACTED["output"]
    assert json.loads(restored[-1]["content"])["plan"] == body
    assert len([event for event in events if event[0] == "compact"]) == 1


@pytest.mark.parametrize("version", [True, 1.0, "1"])
def test_projection_version_cannot_coerce_saved_json_type(version):
    scope = ExecutionScope(uuid4(), uuid4(), ExecutionKind.CONSULTANT_TURN)
    parent_id = uuid4()
    c_thread = "original-c-thread"
    binding = {
        "version": version,
        "job_file_id": str(scope.job_file_id),
        "execution_id": str(scope.execution_id),
        "source_request_id": str(parent_id),
        "compact_position": {"thread_id": c_thread, "checkpoint_id": "original-c"},
    }
    with pytest.raises(ValueError):
        _restore_binding(binding, scope, parent_id, c_thread)
