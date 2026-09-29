"""Actual saver commits plus lost acknowledgements; all provider traffic is synthetic."""

import asyncio
import json
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import httpx2
import pytest
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.conninfo import make_conninfo
from psycopg.errors import ConnectionFailure

from caliburn.adapters.graph_checkpointer import create_graph_serializer
from caliburn.agent_execution.context_compaction import CompactionRuntime, prepare_context_history
from caliburn.agent_execution.result_save_retries import ResultSaveRetryPolicy
from caliburn.agent_execution.tool_steps import ResponseStepRuntime, run_response_loop
from caliburn.features.executions import budgets, service
from caliburn.settings import DatabaseSettings
from tests.fixtures.response_capacity import synthetic_capacity_limits
from tests.integration.test_compaction_accounting import (
    accounting_fixture,
    admitted_executor,
    compaction_fixture,
    request_fixture,
)
from tests.integration.test_compaction_accounting import file_id as file_id
from tests.integration.test_compaction_accounting import runner as runner

pytestmark = pytest.mark.postgres


class ResultAcknowledgementFault(AsyncPostgresSaver):
    fail_channel = "response_snapshot"
    fail_after_commit = True
    failed = False
    recovered = False

    async def aget_tuple(self, config):
        if self.failed:
            self.recovered = True
        return await super().aget_tuple(config)

    async def aput(self, config, checkpoint, metadata, new_versions):
        if not self.recovered and checkpoint["channel_values"].get(self.fail_channel) is not None:
            self.failed = True
            if self.fail_after_commit:
                await super().aput(config, checkpoint, metadata, new_versions)
            raise ConnectionFailure("synthetic lost result-save acknowledgement")
        return await super().aput(config, checkpoint, metadata, new_versions)

    async def aput_writes(self, config, writes, task_id, task_path=""):
        if not self.recovered and any(key == self.fail_channel for key, _ in writes):
            self.failed = True
            raise ConnectionFailure("synthetic unavailable pending writes")
        await super().aput_writes(config, writes, task_id, task_path)


@pytest.mark.parametrize("fail_after_commit", [False, True])
@pytest.mark.parametrize("channel", ["response_snapshot", "compaction_snapshot", "input_count"])
def test_saved_original_survives_automatic_recovery_and_saver_reopen(
    database_settings: DatabaseSettings,
    file_id: UUID,
    runner: asyncio.Runner,
    channel: str,
    fail_after_commit: bool,
) -> None:
    async def scenario():
        compacted = compaction_fixture()
        model = json.loads(
            (Path(__file__).parents[1] / "fixtures/native-response.json").read_text("utf-8")
        )
        model["output"] = model["output"][:2]
        model["output"][1]["phase"] = "final_answer"
        paths = []

        def respond(request):
            paths.append(request.url.path)
            if request.url.path.endswith("input_tokens"):
                return httpx2.Response(
                    200, json={"object": "response.input_tokens", "input_tokens": 128_000}
                )
            if request.url.path.endswith("compact"):
                return httpx2.Response(200, json=compacted)
            return httpx2.Response(200, json=model)

        accounting = replace(
            accounting_fixture(lambda _: Decimal("0.03")), observed_cost=lambda _: Decimal("0.02")
        )
        async with admitted_executor(database_settings, file_id, respond, accounting) as executor:

            async def active():
                async with executor.sessions.begin() as session:
                    await service.lock_active_writer(session, executor.writer)

            async def no_tools(*args):
                pytest.fail("The final fixture contains no tool calls")

            thread_id = str(uuid4())
            request = request_fixture()
            policy = ResultSaveRetryPolicy(3, 0, 0)
            if channel == "compaction_snapshot":
                runtime = CompactionRuntime(
                    executor.request_compaction,
                    executor.account_compaction,
                    active,
                    synthetic_capacity_limits(),
                )

                async def run(saver, first):
                    return await prepare_context_history(
                        saver,
                        thread_id=thread_id,
                        history_request=request,
                        threshold_tokens=128_000,
                        compact_requested=False,
                        count_input=executor.count_input,
                        runtime=runtime,
                        save_retry_policy=policy,
                    )

            else:
                runtime = ResponseStepRuntime(
                    executor.request_model,
                    no_tools,
                    no_tools,
                    active,
                    executor.account_response,
                    executor.count_input,
                    synthetic_capacity_limits(),
                )

                async def run(saver, first):
                    return await run_response_loop(
                        saver,
                        thread_id=thread_id,
                        request=request if first else None,
                        runtime=runtime,
                        max_tool_calls=2,
                        max_model_steps=2,
                        save_retry_policy=policy,
                    )

            dsn = make_conninfo(
                database_settings.url, options=f"-c search_path={database_settings.schema}"
            )
            async with ResultAcknowledgementFault.from_conn_string(
                dsn, serde=create_graph_serializer()
            ) as saver:
                await saver.setup()
                saver.fail_channel = channel
                saver.fail_after_commit = fail_after_commit
                result = await run(saver, True)
                assert saver.failed and saver.recovered
            original_paths = paths.copy()
            async with AsyncPostgresSaver.from_conn_string(
                dsn, serde=create_graph_serializer()
            ) as reopened:
                assert await run(reopened, False) == result
            assert paths == original_paths
            assert paths.count("/v1/responses/input_tokens") == 1
            if channel == "compaction_snapshot":
                assert result == compacted["output"]
                assert paths.count("/v1/responses/compact") == 1
            else:
                assert result["response_snapshot"] == model
                assert result["completed_steps"] == 1
                assert paths.count("/v1/responses") == 1
            async with executor.sessions() as session:
                usage = await budgets.read_budget_usage(session, executor.writer.scope)
            assert usage.outbound_attempts == 2, "Saving is not another remote attempt"
            assert usage.accounted_cost_usd == Decimal(
                "0.031" if channel == "compaction_snapshot" else "0.021"
            )

    runner.run(scenario())
