"""History preparation survives saver reconnects; SDK HTTP is entirely synthetic."""

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

from caliburn.adapters.graph_checkpointer import create_graph_serializer
from caliburn.adapters.openai_responses import ResponseRequest
from caliburn.adapters.response_serialization import snapshot_compaction
from caliburn.agent_execution.context_compaction import (
    CompactionRuntime,
    ReceivedCompaction,
    prepare_context_history,
)
from caliburn.agent_execution.tool_steps import ResponseStepRuntime, run_response_step
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


@pytest.mark.parametrize(
    "history_tokens,interrupt_accounting",
    [(128_000, False), (128_000, True), (127_999, False)],
    ids=["completed-compaction", "accounting-ack-lost", "no-compaction"],
)
def test_reopened_preparation_reuses_original_history_count_and_next_context(
    database_settings: DatabaseSettings,
    file_id: UUID,
    runner: asyncio.Runner,
    history_tokens: int,
    interrupt_accounting: bool,
) -> None:
    async def scenario() -> None:
        history_request = request_fixture()
        original_history = history_request.create_payload()["input"]
        compacted = compaction_fixture()
        expected_history = compacted["output"] if history_tokens == 128_000 else original_history
        final_response = json.loads(
            (Path(__file__).parents[1] / "fixtures/native-response.json").read_text("utf-8")
        )
        final_response["output"] = final_response["output"][:2]
        final_response["output"][1]["phase"] = "final_answer"
        http_requests = []
        accounted_attempts = []
        preparation_finished = False

        def respond(request: httpx2.Request) -> httpx2.Response:
            http_requests.append((request.url.path, json.loads(request.content)))
            if request.url.path == "/v1/responses/input_tokens":
                return httpx2.Response(
                    200,
                    json={
                        "object": "response.input_tokens",
                        "input_tokens": 100 if preparation_finished else history_tokens,
                    },
                )
            if request.url.path == "/v1/responses/compact":
                return httpx2.Response(200, json=compacted)
            assert request.url.path == "/v1/responses"
            assert preparation_finished, "Preparation must not generate a new model response"
            return httpx2.Response(200, json=final_response)

        policy = replace(
            accounting_fixture(lambda _: Decimal("0.03")),
            observed_cost=lambda _: Decimal("0.01"),
        )
        async with admitted_executor(database_settings, file_id, respond, policy) as executor:

            async def guard() -> None:
                async with executor.sessions.begin() as session:
                    await service.lock_active_writer(session, executor.writer)

            async def account(received: ReceivedCompaction) -> None:
                # Includes retained user items, opaque output, usage and unknown metadata.
                assert snapshot_compaction(received.response) == compacted
                accounted_attempts.append(received.attempt_id)
                await executor.account_compaction(received)
                if interrupt_accounting and len(accounted_attempts) == 1:
                    raise ConnectionError("synthetic accounting acknowledgement lost")

            runtime = CompactionRuntime(
                executor.request_compaction, account, guard, synthetic_capacity_limits()
            )
            options = dict(
                thread_id=str(uuid4()),
                history_request=history_request,
                threshold_tokens=128_000,
                compact_requested=False,
                count_input=executor.count_input,
                runtime=runtime,
            )
            dsn = make_conninfo(
                database_settings.url, options=f"-c search_path={database_settings.schema}"
            )
            async with AsyncPostgresSaver.from_conn_string(
                dsn, serde=create_graph_serializer()
            ) as saver:
                await saver.setup()
                if interrupt_accounting:
                    with pytest.raises(ConnectionError, match="accounting acknowledgement"):
                        await prepare_context_history(saver, **options)
                else:
                    assert await prepare_context_history(saver, **options) == expected_history

            expected_requests = [("/v1/responses/input_tokens", history_request.count_payload())]
            if history_tokens == 128_000:
                expected_requests.append(
                    (
                        "/v1/responses/compact",
                        {
                            "model": "gpt-6-luna",
                            "input": original_history,
                            "service_tier": "default",
                        },
                    )
                )
            assert http_requests == expected_requests

            # A new connection and Graph must use saved preparation, with identical arguments.
            async with AsyncPostgresSaver.from_conn_string(
                dsn, serde=create_graph_serializer()
            ) as saver:
                prepared = await prepare_context_history(saver, **options)
                assert prepared == expected_history
                assert await prepare_context_history(saver, **options) == expected_history
                assert http_requests == expected_requests
                assert len(accounted_attempts) == (
                    2 if interrupt_accounting else int(history_tokens == 128_000)
                )
                if interrupt_accounting:
                    assert accounted_attempts[0] == accounted_attempts[1]

                # Caller-supplied new-work data enters only after preparation returns.
                new_items = [{"role": "user", "content": "synthetic next-work input"}]
                next_request = ResponseRequest.from_snapshot(
                    {**history_request.create_payload(), "input": prepared + new_items}
                )
                preparation_finished = True

                async def no_tool(*args: object) -> str:
                    pytest.fail("This synthetic final response has no tool calls")

                result = await run_response_step(
                    saver,
                    thread_id=str(uuid4()),
                    request=next_request,
                    max_tool_calls=1,
                    runtime=ResponseStepRuntime(
                        executor.request_model,
                        no_tool,
                        no_tool,
                        guard,
                        executor.account_response,
                        executor.count_input,
                        synthetic_capacity_limits(),
                    ),
                )
                assert result["next_action"] == "deliver_answer"
                assert result["response_snapshot"] == final_response
                assert http_requests[len(expected_requests) :] == [
                    ("/v1/responses/input_tokens", next_request.count_payload()),
                    ("/v1/responses", next_request.create_payload()),
                ]
                assert http_requests[-1][1]["input"] == expected_history + new_items
                assert history_request.create_payload()["input"] == original_history

            async with executor.sessions.begin() as session:
                usage = await budgets.read_budget_usage(session, executor.writer.scope)
            assert usage.outbound_attempts == (4 if history_tokens == 128_000 else 3)
            assert usage.compactions == int(history_tokens == 128_000)
            assert usage.model_steps == 1
            assert usage.accounted_cost_usd == (
                Decimal("0.042") if history_tokens == 128_000 else Decimal("0.012")
            )

    runner.run(scenario())
