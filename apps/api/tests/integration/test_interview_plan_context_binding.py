"""Plan capability pins a full nullable note beside the original captured data."""

import asyncio
import json

import pytest
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import END, START, StateGraph
from psycopg.conninfo import make_conninfo

from caliburn.adapters.database import Database
from caliburn.adapters.graph_checkpointer import create_graph_serializer
from caliburn.adapters.openai_responses import ResponseRequest
from caliburn.agent_execution.context_compaction import CompactionRuntime
from caliburn.agents.job_consultant.context_binding import _CaptureState, capture_turn_context
from caliburn.agents.job_consultant.tools import consultant_tool_definitions
from caliburn.features.executions.history_models import AgentRole
from caliburn.features.executions.models import ExecutionStateError
from caliburn.features.interviews.models import InterviewReadScope
from caliburn.settings import DatabaseSettings
from caliburn.workflows.context_history import RoleContextHistory
from caliburn.workflows.interview_plans import start_interview_plan
from tests.fixtures.response_capacity import synthetic_capacity_limits
from tests.integration.test_compaction_accounting import runner as runner
from tests.integration.test_consultant_context_binding import start, template
from tests.unit.test_context_preparation import PreparationProbe

pytestmark = pytest.mark.postgres


def test_new_capability_captures_full_unformed_note_before_app_data_and_raw(
    database_settings: DatabaseSettings, runner: asyncio.Runner
) -> None:
    async def scenario() -> None:
        database = Database(database_settings)
        try:
            writer = await start(database, "合成盤點工作，先了解我的範圍")
            dsn = make_conninfo(
                database_settings.url, options=f"-c search_path={database_settings.schema}"
            )
            async with AsyncPostgresSaver.from_conn_string(dsn) as saver:
                saver.serde = create_graph_serializer()
                await saver.setup()
                work = RoleContextHistory(
                    database.sessions, writer, AgentRole.JOB_CONSULTANT, saver
                )
                role_template = ResponseRequest.from_snapshot(
                    {**template().create_payload(), "tools": consultant_tool_definitions()}
                )
                probe = PreparationProbe()
                prepared = await work.prepare_history(
                    template=role_template,
                    threshold_tokens=128_000,
                    count_input=probe.count,
                    runtime=CompactionRuntime(
                        probe.compact,
                        probe.account,
                        work.ensure_active,
                        synthetic_capacity_limits(),
                    ),
                )
                context = await capture_turn_context(
                    work, template=role_template, prepared_history=prepared
                )
                items = context.request.create_payload()["input"]
                assert len(items) == 3
                assert json.loads(items[-3]["content"]) == {
                    "data_kind": "consultant_interview_plan",
                    "plan": None,
                }
                assert json.loads(items[-2]["content"])["data_kind"] == "consultant_turn_reference"
                assert items[-1]["content"] == "合成盤點工作，先了解我的範圍"
                assert context.plan_position is not None
                # A different live template cannot replace the original capability or input.
                restored = await capture_turn_context(
                    work, template=template("new live role must not replace"), prepared_history=[]
                )
                assert restored.request.create_payload() == context.request.create_payload()
                assert restored.plan_position == context.plan_position
        finally:
            await database.close()

    runner.run(scenario())


@pytest.mark.parametrize("today_has_plan_tools", [False, True])
@pytest.mark.parametrize("has_template_checkpoint", [False, True])
def test_original_pending_graph_resumes_but_missing_capture_cannot_use_today(
    database_settings: DatabaseSettings,
    runner: asyncio.Runner,
    today_has_plan_tools: bool,
    has_template_checkpoint: bool,
) -> None:
    async def scenario() -> None:
        database = Database(database_settings)
        try:
            writer = await start(database, "不能以今天的工具重建已遺失原基準")
            dsn = make_conninfo(
                database_settings.url, options=f"-c search_path={database_settings.schema}"
            )
            async with AsyncPostgresSaver.from_conn_string(dsn) as saver:
                saver.serde = create_graph_serializer()
                await saver.setup()
                work = RoleContextHistory(
                    database.sessions, writer, AgentRole.JOB_CONSULTANT, saver
                )
                original = ResponseRequest.from_snapshot(
                    {**template().create_payload(), "tools": consultant_tool_definitions()}
                )
                probe = PreparationProbe()
                prepared = await work.prepare_history(
                    template=original,
                    threshold_tokens=128_000,
                    count_input=probe.count,
                    runtime=CompactionRuntime(
                        probe.compact,
                        probe.account,
                        work.ensure_active,
                        synthetic_capacity_limits(),
                    ),
                )
                if has_template_checkpoint:

                    async def unfinished_capture(state):
                        raise ConnectionError("synthetic capture result was never saved")

                    builder = StateGraph(_CaptureState)
                    builder.add_node("capture_context", unfinished_capture)
                    builder.add_edge(START, "capture_context")
                    builder.add_edge("capture_context", END)
                    graph = builder.compile(checkpointer=saver)
                    config = {
                        "configurable": {
                            "thread_id": f"{writer.scope.job_file_id}:{writer.scope.execution_id}"
                            ":job_consultant:initial_context",
                            "checkpoint_ns": "",
                        }
                    }
                    with pytest.raises(ConnectionError, match="never saved"):
                        await graph.ainvoke(
                            {"request_snapshot": {**original.create_payload(), "input": prepared}},
                            config,
                            durability="sync",
                        )
                    saved = await saver.aget_tuple(config)
                    assert "binding" not in saved.checkpoint["channel_values"]
                async with database.sessions.begin() as session:
                    base = await start_interview_plan(
                        session, writer, InterviewReadScope(writer.scope.job_file_id, 0)
                    )
                today = original if today_has_plan_tools else template("today has no plan tools")
                if has_template_checkpoint:
                    # The original unfinished graph resumes its own template, then forms
                    # its first complete binding; only the plan base was saved earlier.
                    restored = await capture_turn_context(
                        work, template=today, prepared_history=prepared
                    )
                    assert restored.plan_position == base.position
                    assert (
                        restored.request.create_payload()["tools"]
                        == original.create_payload()["tools"]
                    )
                else:
                    with pytest.raises(ExecutionStateError, match="without a recoverable initial"):
                        await capture_turn_context(work, template=today, prepared_history=prepared)
        finally:
            await database.close()

    runner.run(scenario())


def test_original_v1_capture_does_not_gain_plan_when_live_template_gains_tools(
    database_settings: DatabaseSettings, runner: asyncio.Runner
) -> None:
    async def scenario() -> None:
        database = Database(database_settings)
        try:
            writer = await start(database, "原先沒有規劃工具的合成訪談")
            dsn = make_conninfo(
                database_settings.url, options=f"-c search_path={database_settings.schema}"
            )
            async with AsyncPostgresSaver.from_conn_string(dsn) as saver:
                saver.serde = create_graph_serializer()
                await saver.setup()
                work = RoleContextHistory(
                    database.sessions, writer, AgentRole.JOB_CONSULTANT, saver
                )
                probe = PreparationProbe()
                prepared = await work.prepare_history(
                    template=template(),
                    threshold_tokens=128_000,
                    count_input=probe.count,
                    runtime=CompactionRuntime(
                        probe.compact,
                        probe.account,
                        work.ensure_active,
                        synthetic_capacity_limits(),
                    ),
                )
                original = await capture_turn_context(
                    work, template=template(), prepared_history=prepared
                )
                upgraded = ResponseRequest.from_snapshot(
                    {**template().create_payload(), "tools": consultant_tool_definitions()}
                )
                restored = await capture_turn_context(work, template=upgraded, prepared_history=[])
                assert restored.request.create_payload() == original.request.create_payload()
                assert restored.plan_position is None
        finally:
            await database.close()

    runner.run(scenario())
