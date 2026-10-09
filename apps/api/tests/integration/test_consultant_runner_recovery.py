"""The role must pass intact shared result handoffs back without another paid request."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import replace
from uuid import uuid4

import httpx2
import pytest
from fastapi.testclient import TestClient
from psycopg.errors import UndefinedTable

from caliburn.adapters.openai_responses import create_responses_client
from caliburn.agent_execution.tool_steps import (
    InputCountSaveError,
    PausedResponseLoop,
    ResponseStepSaveError,
)
from caliburn.agents.job_consultant.runner import ConsultantRunner
from caliburn.features.executions import service as executions
from caliburn.features.executions.budget_models import BudgetConflictError
from caliburn.features.executions.models import ExecutionStateError, ExecutionStatus
from caliburn.features.interviews.models import FormalInterviewExchange
from caliburn.settings import ModelSettings
from caliburn.workflows.consultant_completion import ConsultantCompletionWorkflow
from caliburn.workflows.consultant_controls import run_consultant_with_controls
from tests.fixtures.consultant_turn import start_consultant_turn as start
from tests.fixtures.response_loop import response_at
from tests.unit.test_result_save_retries import TransientResultFault

pytestmark = pytest.mark.postgres

ORIGINAL_REPLY = "這是保存失敗前已收到的原完整回應。"


def test_summary_upgrade_resumes_saved_preparation_before_database_adoption(client, monkeypatch):
    from caliburn.adapters.openai_responses import ResponseRequest
    from caliburn.features.executions import history
    from caliburn.workflows.context_history import RoleContextHistory

    writer = start(client)
    original_prepare = RoleContextHistory.prepare_history
    original_adopt = history.adopt_prepared_context

    async def legacy_prepare(self, **arguments):
        payload = arguments["template"].create_payload()
        payload["reasoning"].pop("summary", None)
        arguments["template"] = ResponseRequest.from_snapshot(payload)
        return await original_prepare(self, **arguments)

    async def interrupted_adoption(*args, **kwargs):
        raise RuntimeError("synthetic adoption interruption")

    async def scenario():
        async with faulting_runner(client, "unused-channel") as (runner, calls):
            # A previous binary saved preparation without a summary option, then died
            # before adopting its checkpoint reference into the business database.
            with monkeypatch.context() as old_binary:
                old_binary.setattr(RoleContextHistory, "prepare_history", legacy_prepare)
                old_binary.setattr(history, "adopt_prepared_context", interrupted_adoption)
                with pytest.raises(RuntimeError, match="adoption interruption"):
                    await runner.run(writer)
            assert calls == []
            result = await runner.run(writer)
            assert isinstance(result, FormalInterviewExchange)
            assert result.consultant_reply.interview_text == ORIGINAL_REPLY
            assert calls == ["/v1/responses/input_tokens", "/v1/responses"]
        assert history.adopt_prepared_context is original_adopt

    client.portal.call(scenario)


@asynccontextmanager
async def faulting_runner(
    client: TestClient, channel: str
) -> AsyncIterator[tuple[ConsultantRunner, list[str]]]:
    calls: list[str] = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        calls.append(request.url.path)
        if request.url.path.endswith("/input_tokens"):
            return httpx2.Response(
                200, json={"object": "response.input_tokens", "input_tokens": 500}
            )
        raw = response_at(1, final=True, tools=0).model_dump(mode="json")
        raw["service_tier"] = "default"
        raw["output"][1]["content"][0]["text"] = ORIGINAL_REPLY
        return httpx2.Response(200, json=raw)

    # Permanent saver errors escape shared bounded retry with the original typed handoff.
    # This saver becomes available on the next inspection, modelling a repaired boundary.
    saver = TransientResultFault(channel, error_type=UndefinedTable)
    sdk = create_responses_client(
        api_key="synthetic-not-a-real-key",
        timeout_seconds=5,
        http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(respond)),
    )
    try:
        yield (
            ConsultantRunner(
                client.app.state.database.sessions, saver, sdk, ModelSettings(api_key="synthetic")
            ),
            calls,
        )
    finally:
        await sdk.close()


@pytest.mark.parametrize(
    ("channel", "failure_type"),
    [("response_snapshot", ResponseStepSaveError), ("input_count", InputCountSaveError)],
)
def test_explicit_recovery_saves_original_result_without_repeating_outbound_work(
    client: TestClient,
    channel: str,
    failure_type: type[ResponseStepSaveError | InputCountSaveError],
) -> None:
    writer = start(client)

    async def scenario() -> None:
        async with faulting_runner(client, channel) as (runner, calls):
            with pytest.raises(failure_type) as failed:
                await runner.run(writer)
            recovery = failed.value.recovery
            original_calls = tuple(calls)
            async with client.app.state.database.sessions() as session:
                assert (
                    await executions.read_execution(session, writer.scope)
                ).status == ExecutionStatus.ACTIVE

            # Handoffs cannot pick another Step or double as pause-resume authority.
            with pytest.raises(ValueError, match="original Step"):
                await runner.run(
                    writer, recovery=replace(recovery, thread_id="not-the-original-step")
                )
            with pytest.raises(ValueError, match="original paused loop"):
                await runner.run(writer, recovery=recovery, resume_interrupt_id="not-authorized")
            assert tuple(calls) == original_calls

            with pytest.raises(BudgetConflictError, match="original pricing"):
                await replace(
                    runner, settings=ModelSettings(api_key="synthetic", model="gpt-6.1-sol")
                ).run(writer, recovery=recovery)
            assert tuple(calls) == original_calls

            result = await runner.run(writer, recovery=recovery)
            assert isinstance(result, FormalInterviewExchange)
            assert result.consultant_reply.interview_text == ORIGINAL_REPLY
            assert result.employee_input.interview_sequence == 2
            assert result.consultant_reply.interview_sequence == 3
            assert calls == ["/v1/responses/input_tokens", "/v1/responses"]
            async with client.app.state.database.sessions() as session:
                assert (
                    await executions.read_execution(session, writer.scope)
                ).status == ExecutionStatus.COMPLETED

    client.portal.call(scenario)


def test_held_result_cannot_restart_a_cancelled_turn(client: TestClient) -> None:
    writer = start(client)

    async def scenario() -> None:
        async with faulting_runner(client, "response_snapshot") as (runner, calls):
            with pytest.raises(ResponseStepSaveError) as failed:
                await runner.run(writer)
            completion = ConsultantCompletionWorkflow(client.app.state.database.sessions)
            await completion.stop(writer, ExecutionStatus.CANCELLED)
            with pytest.raises(ExecutionStateError):
                await run_consultant_with_controls(
                    writer,
                    sessions=runner.sessions,
                    checkpointer=runner.checkpointer,
                    run=runner.run,
                    recovery=failed.value.recovery,
                )
            assert calls == ["/v1/responses/input_tokens", "/v1/responses"]
            async with client.app.state.database.sessions() as session:
                assert (
                    await executions.read_execution(session, writer.scope)
                ).status == ExecutionStatus.CANCELLED

    client.portal.call(scenario)
    history = client.get(f"/api/job-files/{writer.scope.job_file_id}/interviews").json()
    assert len(history["messages"]) == 1


@pytest.mark.parametrize("pause_requested", [False, True])
@pytest.mark.parametrize(
    ("channel", "failure_type"),
    [("response_snapshot", ResponseStepSaveError), ("input_count", InputCountSaveError)],
)
def test_supervised_handoff_preserves_original_response_and_pending_pause(
    client: TestClient,
    pause_requested: bool,
    channel: str,
    failure_type: type[ResponseStepSaveError | InputCountSaveError],
) -> None:
    """A process-local saved-result handoff must survive the production control wrapper."""
    writer = start(client)

    async def scenario() -> None:
        async with faulting_runner(client, channel) as (runner, calls):
            with pytest.raises(failure_type) as failed:
                await run_consultant_with_controls(
                    writer,
                    sessions=runner.sessions,
                    checkpointer=runner.checkpointer,
                    run=runner.run,
                )
            async with runner.sessions.begin() as session:
                if pause_requested:
                    await executions.request_pause(session, writer.scope)
                replacement = await executions.claim_writer(
                    session, writer.scope, writer_id=uuid4(), replaces_writer_id=writer.writer_id
                )
            result = await run_consultant_with_controls(
                replacement,
                sessions=runner.sessions,
                checkpointer=runner.checkpointer,
                run=runner.run,
                recovery=failed.value.recovery,
            )
            if pause_requested:
                assert isinstance(result, PausedResponseLoop)
                async with runner.sessions() as session:
                    assert (
                        await executions.read_execution(session, writer.scope)
                    ).status == ExecutionStatus.PAUSED
                async with runner.sessions.begin() as session:
                    await executions.resume_execution(session, replacement)
                # Once adopted, the handoff is consumed. Explicit resume uses the
                # saved interrupt, not another copy of the earlier model result.
                result = await run_consultant_with_controls(
                    replacement,
                    sessions=runner.sessions,
                    checkpointer=runner.checkpointer,
                    run=runner.run,
                )
                assert isinstance(result, FormalInterviewExchange)
                assert result.consultant_reply.interview_text == ORIGINAL_REPLY
            else:
                assert isinstance(result, FormalInterviewExchange)
                assert result.consultant_reply.interview_text == ORIGINAL_REPLY
            assert calls == ["/v1/responses/input_tokens", "/v1/responses"]

    client.portal.call(scenario)
