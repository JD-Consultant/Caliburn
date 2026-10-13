"""Plan capability pins a full nullable note beside the original captured data."""

import asyncio
import json

import pytest
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.conninfo import make_conninfo

from caliburn.adapters.database import Database
from caliburn.adapters.graph_checkpointer import create_graph_serializer
from caliburn.adapters.openai_responses import ResponseRequest
from caliburn.agent_execution.context_compaction import CompactionRuntime
from caliburn.agents.job_consultant import context_binding
from caliburn.agents.job_consultant.context_binding import capture_turn_context
from caliburn.agents.job_consultant.tools import consultant_tool_definitions
from caliburn.features.executions.history_models import AgentRole
from caliburn.features.executions.models import ExecutionStateError
from caliburn.features.interviews.models import InterviewReadScope
from caliburn.settings import DatabaseSettings
from caliburn.workflows.consultant_turns.context import ConsultantContextWorkflow
from caliburn.workflows.executions.context_history import RoleContextHistory
from caliburn.workflows.interview_plans import start_interview_plan
from tests.fixtures.response_capacity import synthetic_capacity_limits
from tests.integration.test_compaction_accounting import runner as runner
from tests.integration.test_consultant_context_binding import start, template
from tests.integration.test_consultant_window_renewal import complete
from tests.unit.test_context_preparation import PreparationProbe

pytestmark = pytest.mark.postgres


def test_new_capability_captures_app_data_plan_and_numbered_input(
    database_settings: DatabaseSettings, runner: asyncio.Runner, monkeypatch: pytest.MonkeyPatch
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
                context = await capture_turn_context(
                    work,
                    data=ConsultantContextWorkflow(database.sessions),
                    template=role_template,
                    count_input=probe.count,
                    runtime=CompactionRuntime(
                        probe.compact,
                        probe.account,
                        work.ensure_active,
                        synthetic_capacity_limits(),
                    ),
                )
                items = context.request.create_payload()["input"]
                assert len(items) == 3
                app_data = json.loads(items[0]["content"])
                assert app_data["data_kind"] == "consultant_turn_reference"
                assert "jd_map" in app_data
                assert json.loads(items[1]["content"]) == {
                    "data_kind": "consultant_interview_plan",
                    "plan": None,
                }
                assert json.loads(items[-1]["content"]) == {
                    "interview_sequence": 2,
                    "speaker": "employee",
                    "text": "合成盤點工作，先了解我的範圍",
                }
                assert context.plan_position is not None
                assert context.reset_history is True
                assert probe.count_requests == []
                assert probe.compact_requests == []
                # A different live template cannot replace the original capability or input.
                restored = await capture_turn_context(
                    work,
                    data=ConsultantContextWorkflow(database.sessions),
                    template=template("new live role must not replace"),
                    count_input=probe.count,
                    runtime=CompactionRuntime(
                        probe.compact,
                        probe.account,
                        work.ensure_active,
                        synthetic_capacity_limits(),
                    ),
                )
                assert restored.request.create_payload() == context.request.create_payload()
                assert restored.plan_position == context.plan_position
                await complete(database, work, context, 1)
                following = await start(database, "下一輪同版訪談", writer.scope.job_file_id)
                next_work = RoleContextHistory(
                    database.sessions, following, AgentRole.JOB_CONSULTANT, saver
                )

                def reject_plan_projection(_body: str | None) -> None:
                    raise AssertionError("A retained window must not project the Plan again")

                monkeypatch.setattr(context_binding, "interview_plan_item", reject_plan_projection)
                next_context = await capture_turn_context(
                    next_work,
                    data=ConsultantContextWorkflow(database.sessions),
                    template=role_template,
                    count_input=probe.count,
                    runtime=CompactionRuntime(
                        probe.compact,
                        probe.account,
                        next_work.ensure_active,
                        synthetic_capacity_limits(),
                    ),
                )
                assert next_context.reset_history is False
                assert next_context.plan_position is not None
        finally:
            await database.close()

    runner.run(scenario())


@pytest.mark.parametrize("today_has_plan_tools", [False, True])
def test_missing_capture_cannot_rebuild_an_existing_plan(
    database_settings: DatabaseSettings,
    runner: asyncio.Runner,
    today_has_plan_tools: bool,
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
                async with database.sessions.begin() as session:
                    await start_interview_plan(
                        session, writer, InterviewReadScope(writer.scope.job_file_id, 0)
                    )
                current = ResponseRequest.from_snapshot(
                    {
                        **template().create_payload(),
                        "tools": consultant_tool_definitions() if today_has_plan_tools else [],
                    }
                )
                probe = PreparationProbe()
                with pytest.raises(ExecutionStateError, match="without a recoverable initial"):
                    await capture_turn_context(
                        work,
                        data=ConsultantContextWorkflow(database.sessions),
                        template=current,
                        count_input=probe.count,
                        runtime=CompactionRuntime(
                            probe.compact,
                            probe.account,
                            work.ensure_active,
                            synthetic_capacity_limits(),
                        ),
                    )
        finally:
            await database.close()

    runner.run(scenario())


def test_capture_without_plan_does_not_gain_it_when_live_template_gains_tools(
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
                original = await capture_turn_context(
                    work,
                    data=ConsultantContextWorkflow(database.sessions),
                    template=template(),
                    count_input=probe.count,
                    runtime=CompactionRuntime(
                        probe.compact,
                        probe.account,
                        work.ensure_active,
                        synthetic_capacity_limits(),
                    ),
                )
                upgraded = ResponseRequest.from_snapshot(
                    {**template().create_payload(), "tools": consultant_tool_definitions()}
                )
                restored = await capture_turn_context(
                    work,
                    data=ConsultantContextWorkflow(database.sessions),
                    template=upgraded,
                    count_input=probe.count,
                    runtime=CompactionRuntime(
                        probe.compact,
                        probe.account,
                        work.ensure_active,
                        synthetic_capacity_limits(),
                    ),
                )
                assert restored.request.create_payload() == original.request.create_payload()
                assert restored.plan_position is None
        finally:
            await database.close()

    runner.run(scenario())
