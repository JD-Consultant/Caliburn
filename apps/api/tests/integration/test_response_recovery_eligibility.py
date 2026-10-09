"""Held results do not bypass PostgreSQL execution fencing or hold locks during model I/O."""

import asyncio
from dataclasses import replace
from pathlib import Path
from uuid import UUID, uuid4

import psycopg
import pytest
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from openai.types.responses import Response
from psycopg.conninfo import make_conninfo

from caliburn.adapters.database import Database
from caliburn.adapters.graph_checkpointer import create_graph_serializer
from caliburn.adapters.openai_responses import ResponseRequest
from caliburn.agent_execution.tool_steps import (
    ReceivedModelResponse,
    ResponseStepSaveError,
    _build_response_step,
    run_response_step,
)
from caliburn.features.executions import service as executions
from caliburn.features.executions.models import (
    ExecutionKind,
    ExecutionScope,
    ExecutionStateError,
    ExecutionStatus,
)
from caliburn.settings import DatabaseSettings
from tests.fixtures.response_capacity import synthetic_response_runtime

pytestmark = pytest.mark.postgres


async def account_response(received: ReceivedModelResponse) -> None:
    """Execution fencing fixture, without execution cost persistence."""


class EntireResponseSaveFault(AsyncPostgresSaver):
    async def aput(self, config, checkpoint, metadata, new_versions):
        if checkpoint["channel_values"].get("response_snapshot"):
            raise ConnectionError("synthetic checkpoint unavailable")
        return await super().aput(config, checkpoint, metadata, new_versions)

    async def aput_writes(self, config, writes, task_id, task_path=""):
        if any(name == "response_snapshot" for name, _ in writes):
            raise ConnectionError("synthetic pending writes unavailable")
        await super().aput_writes(config, writes, task_id, task_path)


@pytest.mark.parametrize(
    "interruption", ["cancel_during_model", "cancel_before_recovery", "replace"]
)
def test_late_or_held_response_requires_current_writer_before_tools(
    database_settings: DatabaseSettings,
    database_connection: psycopg.Connection,
    interruption: str,
) -> None:
    file_id = uuid4()
    database_connection.execute(
        "INSERT INTO job_files (job_file_id,initial_display_name,"
        "display_name,employee_name) VALUES (%s,'恢復','恢復','合成人員')",
        (file_id,),
    )

    async def scenario() -> None:
        database = Database(database_settings)
        try:
            scope = ExecutionScope(file_id, uuid4(), ExecutionKind.CONSULTANT_TURN)
            async with database.sessions.begin() as session:
                await executions.admit_execution(session, scope)
                writer = await executions.claim_writer(session, scope, writer_id=uuid4())
            events = []

            async def ensure_active():
                async with database.sessions.begin() as session:
                    await executions.lock_active_writer(session, writer)

            async def request(
                model_request: ResponseRequest, request_id: UUID, input_tokens: int
            ) -> ReceivedModelResponse:
                events.append("model")
                if interruption == "cancel_during_model":
                    # Must finish on an independent connection while the model is in flight.
                    # A transaction held across model I/O would deadlock this call.
                    async with asyncio.timeout(3), database.sessions.begin() as session:
                        await executions.finish_execution(
                            session, writer, ExecutionStatus.CANCELLED
                        )
                response = Response.model_validate_json(
                    (Path(__file__).parents[1] / "fixtures/native-response.json").read_text(
                        encoding="utf-8"
                    )
                )
                return ReceivedModelResponse(response=response, attempt_id=uuid4())

            async def prepare(call, operation_id):
                events.append("read")
                return "original result"

            async def execute(prepared):
                pytest.fail("Read-only fixture")

            runtime = synthetic_response_runtime(
                request_model=request,
                prepare_tool=prepare,
                execute_tool=execute,
                ensure_active=ensure_active,
                account_response=account_response,
            )
            model_request = ResponseRequest(
                model="gpt-6-luna",
                instructions="synthetic",
                input_items=[],
                tools=[],
                reasoning_effort="low",
                max_output_tokens=512,
            )
            thread_id = str(scope.execution_id)
            options = {"thread_id": thread_id, "runtime": runtime, "max_tool_calls": 16}
            config = {"configurable": {"thread_id": thread_id}}
            dsn = make_conninfo(
                database_settings.url, options=f"-c search_path={database_settings.schema}"
            )
            serde = create_graph_serializer()

            if interruption == "cancel_during_model":
                async with AsyncPostgresSaver.from_conn_string(dsn, serde=serde) as saver:
                    await saver.setup()
                    with pytest.raises(ExecutionStateError):
                        await run_response_step(saver, request=model_request, **options)
                    saved = await _build_response_step(saver, max_tool_calls=16).aget_state(config)
                    assert "response_snapshot" in saved.values
                    assert saved.next == ("prepare_tool",)
                assert events == ["model"]
                return

            async with EntireResponseSaveFault.from_conn_string(dsn, serde=serde) as saver:
                await saver.setup()
                with pytest.raises(ResponseStepSaveError) as failure:
                    await run_response_step(saver, request=model_request, **options)
            async with database.sessions.begin() as session:
                if interruption == "replace":
                    replacement = await executions.claim_writer(
                        session, scope, writer_id=uuid4(), replaces_writer_id=writer.writer_id
                    )
                else:
                    await executions.finish_execution(session, writer, ExecutionStatus.CANCELLED)
            async with AsyncPostgresSaver.from_conn_string(dsn, serde=serde) as saver:
                with pytest.raises(ExecutionStateError):
                    await run_response_step(
                        saver, request=None, recovery=failure.value.recovery, **options
                    )
                saved = await _build_response_step(saver, max_tool_calls=16).aget_state(config)
                assert "response_snapshot" not in saved.values
                assert events == ["model"]

                if interruption == "replace":

                    async def require_replacement():
                        async with database.sessions.begin() as session:
                            await executions.lock_active_writer(session, replacement)

                    resumed = await run_response_step(
                        saver,
                        thread_id=thread_id,
                        request=None,
                        recovery=failure.value.recovery,
                        runtime=replace(runtime, ensure_active=require_replacement),
                        max_tool_calls=16,
                    )
                    assert (
                        resumed["response_snapshot"]
                        == failure.value.recovery.update["response_snapshot"]
                    )
                    assert events == ["model", "read"]
        finally:
            await database.close()

    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        runner.run(scenario())
