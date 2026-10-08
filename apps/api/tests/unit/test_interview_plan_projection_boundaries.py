"""Independent review probes for native projection recovery; no production edits."""

import json
from copy import deepcopy
from dataclasses import replace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4, uuid7

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from caliburn.agent_execution.context_compaction import run_context_compaction
from caliburn.agent_execution.tool_steps import run_response_loop
from caliburn.agents.job_consultant.interview_plan_projection import bind_interview_plan_compaction
from caliburn.features.executions.history_models import AgentRole
from caliburn.features.executions.models import ExecutionKind, ExecutionScope, ExecutionWriter
from caliburn.features.interview_plans.models import PlanPosition, PlanSnapshot
from caliburn.workflows.context_history import RoleContextHistory
from tests.fixtures.response_capacity import CapacityProbe, request_fixture
from tests.unit.test_context_compaction import COMPACTED, options
from tests.unit.test_interview_plan_projection import scenario


class StartAckFault(InMemorySaver):
    fail = True

    async def aput(self, config, checkpoint, metadata, new_versions):
        thread = config["configurable"]["thread_id"]
        if self.fail and ":plan_projection:" in thread:
            if "__start__" in checkpoint["channel_values"]:
                await super().aput(config, checkpoint, metadata, new_versions)
            raise ConnectionError("review projection start ACK lost")
        return await super().aput(config, checkpoint, metadata, new_versions)

    async def aput_writes(self, config, writes, task_id, task_path=""):
        if self.fail and ":plan_projection:" in config["configurable"]["thread_id"]:
            raise ConnectionError("review projection start pending writes unavailable")
        return await super().aput_writes(config, writes, task_id, task_path)


async def test_raw_start_ack_loss_preserves_original_exact_c(monkeypatch):
    saver = StartAckFault()
    work, args, parent_id, wrapped, reader, _, events = scenario(monkeypatch, saver)
    plan = reader.return_value
    with pytest.raises(ConnectionError, match="start ACK lost"):
        await wrapped(args["request"], args["input_count"], parent_id)
    reader.assert_not_awaited()
    projection_config = {
        "configurable": {"thread_id": f"{work.response_thread_id}:plan_projection:{parent_id}"}
    }
    pending = await saver.aget_tuple(projection_config)
    assert "__start__" in pending.checkpoint["channel_values"]
    c_config = {"configurable": {"thread_id": args["thread_id"], "checkpoint_ns": ""}}
    saved = await saver.aget_tuple(c_config)
    later = deepcopy(saved.checkpoint)
    later["id"] = str(uuid7())
    later["channel_values"]["compaction_snapshot"]["output"].append(
        {"role": "user", "content": "later C"}
    )
    await saver.aput(c_config, later, saved.metadata, {})
    saver.fail = False
    result = await wrapped(args["request"], args["input_count"], parent_id)
    assert result[:-1] == COMPACTED["output"]
    assert json.loads(result[-1]["content"])["plan"] == plan.body
    assert reader.await_count == 1
    assert len([event for event in events if event[0] == "compact"]) == 1


class ParentAdoptionFault(InMemorySaver):
    fail = True
    after_save = False
    parent_thread = ""

    async def aput(self, config, checkpoint, metadata, new_versions):
        thread = config["configurable"]["thread_id"]
        request = checkpoint["channel_values"].get("request_snapshot", {})
        has_plan = any(
            "consultant_interview_plan" in item.get("content", "")
            for item in request.get("input", [])
        )
        if self.fail and thread == self.parent_thread and has_plan:
            if self.after_save:
                await super().aput(config, checkpoint, metadata, new_versions)
            raise ConnectionError("review parent adoption unavailable")
        return await super().aput(config, checkpoint, metadata, new_versions)

    async def aput_writes(self, config, writes, task_id, task_path=""):
        if self.fail and config["configurable"]["thread_id"] == self.parent_thread:
            for name, value in writes:
                if name == "request_snapshot" and any(
                    "consultant_interview_plan" in item.get("content", "")
                    for item in value.get("input", [])
                ):
                    raise ConnectionError("review parent pending writes unavailable")
        return await super().aput_writes(config, writes, task_id, task_path)


@pytest.mark.parametrize("after_save", [False, True])
async def test_parent_adoption_reentry_uses_saved_projection(monkeypatch, after_save):
    saver = ParentAdoptionFault()
    saver.after_save = after_save
    writer = ExecutionWriter(
        ExecutionScope(uuid4(), uuid4(), ExecutionKind.CONSULTANT_TURN), uuid4()
    )
    work = RoleContextHistory(Mock(), writer, AgentRole.JOB_CONSULTANT, saver)
    saver.parent_thread = work.response_thread_id
    monkeypatch.setattr(RoleContextHistory, "ensure_active", AsyncMock())
    events = []
    args = options(events)
    probe = CapacityProbe([100, 160000, 100], final=False)

    async def original(request, count, source_id):
        return await run_context_compaction(
            saver,
            thread_id=f"{work.response_thread_id}:compact:{source_id}",
            request=request,
            input_count=count,
            runtime=args["runtime"],
        )

    plan = PlanSnapshot(
        PlanPosition(writer.scope.job_file_id, writer.scope.execution_id, uuid4()), "原換窗正文"
    )
    reader = AsyncMock(return_value=plan)
    wrapped = bind_interview_plan_compaction(work, original, read_plan=reader)
    runtime = replace(probe.runtime(), compact_window=wrapped)
    kwargs = dict(
        thread_id=work.response_thread_id, runtime=runtime, max_tool_calls=2, max_model_steps=3
    )
    with pytest.raises(ConnectionError, match="parent"):
        await run_response_loop(saver, request=request_fixture(), **kwargs)
    assert reader.await_count == 1
    saver.fail = False
    reader.side_effect = AssertionError("parent recovery must retain original projection")
    result = await run_response_loop(saver, request=None, **kwargs)
    assert result["next_action"] == "deliver_answer"
    model_input = probe.model_requests[1]["input"]
    assert model_input[:-1] == COMPACTED["output"]
    assert json.loads(model_input[-1]["content"])["plan"] == plan.body
    assert reader.await_count == 1
    assert len([event for event in events if event[0] == "compact"]) == 1
