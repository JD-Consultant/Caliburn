"""Real budget/checkpoint ownership around remote counting and generation admission."""

import asyncio
import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import httpx2
import psycopg
import pytest
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.conninfo import make_conninfo

from caliburn.adapters.database import Database
from caliburn.adapters.graph_checkpointer import create_graph_serializer
from caliburn.adapters.openai_responses import ResponseRequest, create_responses_client
from caliburn.agent_execution.tool_steps import (
    InputCountSaveError,
    ResponseStepRuntime,
    run_response_step,
)
from caliburn.features.executions import budgets, service
from caliburn.features.executions.budget_models import ExecutionBudget
from caliburn.features.executions.models import ExecutionKind, ExecutionScope
from caliburn.workflows.model_requests import ModelRequestAccounting, ModelRequestExecutor
from tests.fixtures.response_capacity import synthetic_capacity_limits

pytestmark = pytest.mark.postgres


class InputCountSaveFault(AsyncPostgresSaver):
    fail_after_commit = False

    async def aput(self, config, checkpoint, metadata, new_versions):
        if checkpoint["channel_values"].get("input_count"):
            if self.fail_after_commit:
                await super().aput(config, checkpoint, metadata, new_versions)
            raise ConnectionError("synthetic count checkpoint unavailable")
        return await super().aput(config, checkpoint, metadata, new_versions)

    async def aput_writes(self, config, writes, task_id, task_path=""):
        if any(name == "input_count" for name, _ in writes):
            raise ConnectionError("synthetic count pending writes unavailable")
        await super().aput_writes(config, writes, task_id, task_path)


@pytest.mark.parametrize("input_tokens", [488, 489])
@pytest.mark.parametrize("save_fault", [None, "before_save", "after_save"])
def test_saved_count_reconnects_without_recount_and_reserves_its_actual_outbound(
    database_settings, database_connection: psycopg.Connection, input_tokens: int, save_fault
):
    file_id = uuid4()
    database_connection.execute(
        "INSERT INTO job_files (job_file_id,creation_command_id,initial_display_name,"
        "display_name,employee_name) VALUES (%s,%s,'計數','計數','合成人員')",
        (file_id, uuid4()),
    )

    async def scenario():
        database = Database(database_settings)
        scope = ExecutionScope(file_id, uuid4(), ExecutionKind.CONSULTANT_TURN)
        paths = []
        payloads = []
        counts_at_http = []
        response = json.loads(
            (Path(__file__).parents[1] / "fixtures/native-response.json").read_text("utf-8")
        )
        response["output"] = response["output"][:2]
        response["output"][1]["phase"] = "final_answer"

        async def respond(request):
            # Different connection must see committed reservation, without a held lock.
            async with asyncio.timeout(3), database.sessions.begin() as session:
                await service.lock_active_writer(session, writer)
                counts_at_http.append(await budgets.read_budget_usage(session, scope))
            paths.append(request.url.path)
            payloads.append(json.loads(request.content))
            if request.url.path.endswith("input_tokens"):
                return httpx2.Response(
                    200, json={"object": "response.input_tokens", "input_tokens": input_tokens}
                )
            return httpx2.Response(200, json=response)

        try:
            async with database.sessions.begin() as session:
                await service.admit_execution(session, scope)
                writer = await service.claim_writer(session, scope, writer_id=uuid4())
                await budgets.fix_execution_budget(
                    session,
                    writer,
                    ExecutionBudget(
                        4,
                        2,
                        12,
                        2,
                        datetime.now(UTC) + timedelta(minutes=10),
                        Decimal("1"),
                        "synthetic-v1",
                    ),
                )
            async with create_responses_client(
                api_key="synthetic-only",
                timeout_seconds=5,
                http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(respond)),
            ) as client:
                # Explicit administrative reservation; do not call the counting endpoint free.
                accounting = ModelRequestAccounting(
                    "synthetic-v1",
                    Decimal("0.1"),
                    lambda _: Decimal("0.01"),
                    token_count_reservation_usd=Decimal("0.001"),
                )
                executor = ModelRequestExecutor(database.sessions, writer, client, accounting)

                async def guard():
                    async with database.sessions.begin() as session:
                        await service.lock_active_writer(session, writer)

                async def tool(*args):
                    pytest.fail("No tools in this fixture")

                async def fail_before_generation(*args):
                    raise ConnectionError("synthetic before generation admission")

                runtime = ResponseStepRuntime(
                    fail_before_generation,
                    tool,
                    tool,
                    guard,
                    executor.account_response,
                    executor.count_input,
                    {**synthetic_capacity_limits(), "context_window_tokens": 1000},
                )
                request = ResponseRequest(
                    model="gpt-6-luna",
                    instructions="synthetic",
                    input_items=[],
                    tools=[],
                    reasoning_effort="low",
                    max_output_tokens=512,
                )
                dsn = make_conninfo(
                    database_settings.url, options=f"-c search_path={database_settings.schema}"
                )
                options = dict(thread_id=str(uuid4()), max_tool_calls=2)
                if save_fault:
                    error = InputCountSaveError
                elif input_tokens == 488:
                    error = ConnectionError
                else:
                    error = ValueError
                saver_type = InputCountSaveFault if save_fault else AsyncPostgresSaver
                recovery = None
                async with saver_type.from_conn_string(
                    dsn, serde=create_graph_serializer()
                ) as saver:
                    await saver.setup()
                    if save_fault:
                        saver.fail_after_commit = save_fault == "after_save"
                    with pytest.raises(error) as failure:
                        await run_response_step(saver, request=request, runtime=runtime, **options)
                    if save_fault:
                        recovery = failure.value.recovery
                # Reopen the actual saver; original count is independent of this client instance.
                async with AsyncPostgresSaver.from_conn_string(
                    dsn, serde=create_graph_serializer()
                ) as saver:
                    resumed = replace(runtime, request_model=executor.request_model)
                    if input_tokens == 488:
                        result = await run_response_step(
                            saver, request=None, runtime=resumed, recovery=recovery, **options
                        )
                        assert result["next_action"] == "deliver_answer"
                    else:
                        with pytest.raises(ValueError, match="capacity"):
                            await run_response_step(
                                saver, request=None, runtime=resumed, recovery=recovery, **options
                            )
                assert paths == (
                    ["/v1/responses/input_tokens", "/v1/responses"]
                    if input_tokens == 488
                    else ["/v1/responses/input_tokens"]
                )
                assert payloads[0] == request.count_payload()
                assert counts_at_http[0].outbound_attempts == 1
                assert counts_at_http[0].model_steps == 0
                assert counts_at_http[0].accounted_cost_usd == Decimal("0.001")
                if input_tokens == 488:
                    assert payloads[1] == request.create_payload()
                    assert counts_at_http[1].accounted_cost_usd == Decimal("0.101")
                async with database.sessions.begin() as session:
                    usage = await budgets.read_budget_usage(session, scope)
                assert usage.model_steps == (1 if input_tokens == 488 else 0)
                assert usage.accounted_cost_usd == (
                    Decimal("0.011") if input_tokens == 488 else Decimal("0.001")
                )
        finally:
            await database.close()

    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        runner.run(scenario())
