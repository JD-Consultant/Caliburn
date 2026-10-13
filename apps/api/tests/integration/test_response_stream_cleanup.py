"""Offline SDK + real PG + production runner/control/failure-boundary probe.

Run from apps/api with the explicitly isolated CALIBURN_TEST_DATABASE_URL.
No provider traffic; transport cleanup must preserve the original result disposition.
"""

import asyncio
import json
from functools import partial

import httpx2
import pytest
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg import AsyncConnection
from psycopg.conninfo import make_conninfo
from psycopg.rows import dict_row

from caliburn.adapters.graph_checkpointer import create_graph_serializer
from caliburn.adapters.openai_responses import create_responses_client
from caliburn.agent_execution.response_runtime import HeldModelResponse
from caliburn.agents.job_consultant.runner import ConsultantRunner
from caliburn.features.executions import budgets
from caliburn.features.executions import service as executions
from caliburn.features.executions.models import ExecutionStatus
from caliburn.settings import ModelSettings
from caliburn.transport.model_tools.memory_write_checkpoint import MEMORY_CHECKPOINT_TYPES
from caliburn.workflows.consultant_turns.completion import ConsultantCompletionWorkflow
from caliburn.workflows.consultant_turns.controls import run_consultant_with_controls
from caliburn.workflows.executions.failure_boundary import run_with_failure_boundary
from caliburn.workflows.executions.runner_failures import capture_runner_failure
from tests.fixtures.consultant_turn import start_consultant_turn
from tests.fixtures.response_loop import response_at
from tests.unit.test_response_streaming import WireStream


@pytest.mark.parametrize(
    ("response_status", "cleanup", "expected_status"),
    [
        ("completed", "normal", "completed"),
        ("completed", "ordinary_error", "completed"),
        ("incomplete", "normal", "failed"),
        ("incomplete", "ordinary_error", "failed"),
        ("failed", "normal", "failed"),
        ("failed", "ordinary_error", "failed"),
        ("completed", "task_cancel", "active"),
        ("completed", "masked_task_cancel", "active"),
    ],
)
def test_terminal_cleanup_preserves_production_disposition(
    client, database_settings, response_status, cleanup, expected_status
):
    writer = start_consultant_turn(client)

    async def scenario():
        calls, settlements = [], []
        raw = response_at(1, final=True, tools=0).model_dump(mode="json")
        raw["status"] = response_status
        raw["service_tier"] = "default"
        raw["output"][1]["content"][0]["text"] = "合成完整終局答覆"
        if response_status == "failed":
            raw["error"] = {"code": "server_error", "message": "synthetic provider failure"}
        elif response_status == "incomplete":
            raw["incomplete_details"] = {"reason": "max_output_tokens"}
        closing = asyncio.Event()

        class ClosingStream(WireStream):
            async def aclose(self):
                if cleanup in ("task_cancel", "masked_task_cancel"):
                    self.closed = True
                    closing.set()
                    try:
                        await asyncio.Future()
                    except asyncio.CancelledError:
                        if cleanup == "masked_task_cancel":
                            raise OSError("synthetic close masks cancellation") from None
                        raise
                await super().aclose()

        wire = ClosingStream(
            [{"type": "response." + response_status, "response": raw}],
            close_error=OSError("synthetic transport close failure")
            if cleanup == "ordinary_error"
            else None,
        )

        def respond(request):
            calls.append(request.url.path)
            if request.url.path.endswith("/input_tokens"):
                return httpx2.Response(
                    200, json={"object": "response.input_tokens", "input_tokens": 500}
                )
            assert request.url.path == "/v1/responses"
            assert json.loads(request.content)["stream"] is True
            return httpx2.Response(200, headers={"content-type": "text/event-stream"}, stream=wire)

        sdk = create_responses_client(
            api_key="synthetic-not-a-real-key",
            timeout_seconds=5,
            http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(respond)),
        )
        dsn = make_conninfo(
            database_settings.url, options=f"-c search_path={database_settings.schema}"
        )
        try:
            async with await AsyncConnection.connect(
                dsn, autocommit=True, prepare_threshold=0, row_factory=dict_row
            ) as connection:
                saver = AsyncPostgresSaver(
                    connection, serde=create_graph_serializer(allowed_types=MEMORY_CHECKPOINT_TYPES)
                )
                await saver.setup()
                sessions = client.app.state.database.sessions
                runner = ConsultantRunner(
                    sessions,
                    saver,
                    sdk,
                    ModelSettings(api_key="synthetic"),
                    on_commentary=lambda *_: None,
                )
                completion = ConsultantCompletionWorkflow(sessions)

                async def settle(writer, error):
                    causes = []
                    while error is not None:
                        causes.append(type(error).__name__)
                        error = error.__cause__
                    settlements.append(causes)
                    return await completion.stop(writer, ExecutionStatus.FAILED)

                cancelled = False
                invocation = asyncio.create_task(
                    run_with_failure_boundary(
                        writer,
                        run=partial(
                            run_consultant_with_controls,
                            sessions=sessions,
                            checkpointer=saver,
                            run=runner.run,
                        ),
                        settle_failure=settle,
                    )
                )
                try:
                    if cleanup in ("task_cancel", "masked_task_cancel"):
                        await asyncio.wait_for(closing.wait(), timeout=5)
                        invocation.cancel()
                    await invocation
                except asyncio.CancelledError as error:
                    cancelled = True
                    assert invocation.cancelled()
                    handoff = capture_runner_failure(error).recovery
                    assert isinstance(handoff, HeldModelResponse)
                    assert handoff.update["response_snapshot"] == raw
                    held_attempt_id = handoff.update["response_attempt_id"]
                saved_responses = []
                response_attempts = []
                async for saved in saver.alist(None):
                    values = saved.checkpoint["channel_values"]
                    if values.get("response_snapshot"):
                        saved_responses.append(values["response_snapshot"])
                        response_attempts.append(values["response_attempt_id"])
                if cancelled:
                    response_attempts.append(held_attempt_id)
                else:
                    assert saved_responses
                assert all(response == raw for response in saved_responses)
                costs = []
                async with sessions() as session:
                    status = (await executions.read_execution(session, writer.scope)).status
                    for attempt_id in set(response_attempts):
                        attempt = await budgets.read_outbound_attempt(
                            session, writer.scope, attempt_id
                        )
                        costs.append(
                            str(attempt.reported_cost_usd)
                            if attempt.reported_cost_usd is not None
                            else None
                        )
                assert len(set(response_attempts)) == 1
                assert costs == ([None] if cancelled else ["0.000005200"])
                assert status.value == expected_status
                assert calls == ["/v1/responses/input_tokens", "/v1/responses"]
                assert cancelled is (cleanup in ("task_cancel", "masked_task_cancel"))
                assert not cancelled or not settlements
                evidence = {
                    "response_status": response_status,
                    "cleanup": cleanup,
                    "execution_status": status.value,
                    "settlements": settlements,
                    "cancelled": cancelled,
                    "count_calls": calls.count("/v1/responses/input_tokens"),
                    "model_calls": calls.count("/v1/responses"),
                    "exact_response_saved": bool(saved_responses),
                    "exact_response_held": cancelled,
                    "reported_model_costs": costs,
                }
        finally:
            await sdk.close()
        return evidence

    evidence = client.portal.call(scenario)
    messages = client.get(f"/api/job-files/{writer.scope.job_file_id}/interviews").json()[
        "messages"
    ]
    evidence["formal_history_message_count"] = len(messages)
    assert len(messages) == (3 if expected_status == "completed" else 1)
    print("NETWORK_POLICY_PROBE " + json.dumps(evidence, ensure_ascii=False, sort_keys=True))
