"""Native pause persistence and execution eligibility meet through one thin binding."""

import asyncio
from dataclasses import replace
from uuid import uuid4

import pytest
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.conninfo import make_conninfo

from caliburn.adapters.database import Database
from caliburn.adapters.graph_checkpointer import create_graph_serializer
from caliburn.agent_execution.tool_steps import PausedResponseLoop, run_response_loop
from caliburn.features.executions import service as executions
from caliburn.features.executions.models import (
    ExecutionKind,
    ExecutionScope,
    ExecutionStateError,
    ExecutionStatus,
    StaleWriterError,
)
from caliburn.workflows.execution_controls import ConsultantExecutionControls
from tests.fixtures.response_capacity import CapacityProbe, request_fixture

pytestmark = pytest.mark.postgres


@pytest.mark.parametrize("after_pause", ["resume", "cancel", "replace"])
def test_saved_pause_reopens_without_generation_and_keeps_execution_fencing(
    database_settings, database_connection, after_pause
):
    file_id = uuid4()
    database_connection.execute(
        "INSERT INTO job_files (job_file_id,creation_command_id,initial_display_name,"
        "display_name,employee_name) VALUES (%s,%s,'控制','控制','合成人員')",
        (file_id, uuid4()),
    )

    async def scenario():
        database = Database(database_settings)
        try:
            scope = ExecutionScope(file_id, uuid4(), ExecutionKind.CONSULTANT_TURN)
            async with database.sessions.begin() as session:
                await executions.admit_execution(session, scope)
                writer = await executions.claim_writer(session, scope, writer_id=uuid4())
            binding = ConsultantExecutionControls(database.sessions, writer)
            provider = CapacityProbe([100, 100], final=False)

            async def model(request, request_id):
                # The control request must finish while model I/O is still active;
                # retaining an execution transaction across I/O would deadlock this.
                if not provider.model_requests:
                    async with asyncio.timeout(3), database.sessions.begin() as session:
                        await executions.request_pause(session, scope)
                        info = await executions.read_execution(session, scope)
                        assert info.status == ExecutionStatus.ACTIVE
                        assert info.pause_requested
                return await provider.model(request, request_id)

            options = dict(
                thread_id=str(scope.execution_id),
                runtime=replace(
                    provider.runtime(), request_model=model, ensure_active=binding.ensure_active
                ),
                controls=binding.loop_controls(),
                max_tool_calls=2,
                max_model_steps=2,
            )
            dsn = make_conninfo(
                database_settings.url, options=f"-c search_path={database_settings.schema}"
            )
            async with AsyncPostgresSaver.from_conn_string(
                dsn, serde=create_graph_serializer()
            ) as saver:
                await saver.setup()
                paused = await run_response_loop(saver, request=request_fixture(), **options)
            assert isinstance(paused, PausedResponseLoop)
            async with database.sessions.begin() as session:
                info = await executions.read_execution(session, scope)
                assert info.status == ExecutionStatus.PAUSED
                assert info.pause_requested
            async with AsyncPostgresSaver.from_conn_string(
                dsn, serde=create_graph_serializer()
            ) as saver:
                assert await run_response_loop(saver, request=None, **options) == paused
                assert len(provider.model_requests) == 1
                if after_pause == "cancel":
                    async with database.sessions.begin() as session:
                        await executions.finish_execution(
                            session, writer, ExecutionStatus.CANCELLED
                        )
                    with pytest.raises(ExecutionStateError):
                        await run_response_loop(saver, request=None, **options)
                    with pytest.raises(ExecutionStateError):
                        await run_response_loop(
                            saver, request=None, resume_interrupt_id=paused.interrupt_id, **options
                        )
                    assert len(provider.model_requests) == 1
                    return

                # Only explicit product resume may release the saved interrupt.
                async with database.sessions.begin() as session:
                    await executions.resume_execution(session, writer)
                    if after_pause == "replace":
                        await executions.claim_writer(
                            session, scope, writer_id=uuid4(), replaces_writer_id=writer.writer_id
                        )
                if after_pause == "replace":
                    with pytest.raises(StaleWriterError):
                        await run_response_loop(saver, request=None, **options)
                    assert len(provider.model_requests) == 1
                    return
                result = await run_response_loop(
                    saver, request=None, resume_interrupt_id=paused.interrupt_id, **options
                )
                assert not isinstance(result, PausedResponseLoop)
                assert result["next_action"] == "deliver_answer"
                assert result["completed_steps"] == 2
                assert provider.model_requests[1]["input"] == paused.state["input_items"]
                async with database.sessions.begin() as session:
                    info = await executions.read_execution(session, scope)
                    assert info.status == ExecutionStatus.ACTIVE  # Graph END is not a Turn commit.
                    assert not info.pause_requested
        finally:
            await database.close()

    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        runner.run(scenario())
