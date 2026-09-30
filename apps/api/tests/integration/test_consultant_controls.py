"""Real product transactions and native pause/resume, with synthetic model transport."""

import asyncio
import json
from functools import partial
from uuid import UUID, uuid4

import httpx2
import pytest
from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.conninfo import make_conninfo

from caliburn.adapters.graph_checkpointer import create_graph_serializer
from caliburn.adapters.openai_responses import create_responses_client
from caliburn.adapters.process_lock import PostgresProcessLock
from caliburn.agent_execution.tool_steps import PausedResponseLoop
from caliburn.agents.job_consultant.runner import ConsultantRunner
from caliburn.features.executions import budgets
from caliburn.features.executions import service as executions
from caliburn.features.executions.models import (
    ExecutionKind,
    ExecutionScope,
    ExecutionStateError,
    ExecutionStatus,
    ExecutionWriter,
)
from caliburn.features.job_description import candidate_service
from caliburn.features.job_description.candidates import CandidateStateError
from caliburn.settings import DatabaseSettings, ModelSettings
from caliburn.workflows.consultant_completion import ConsultantCompletionWorkflow
from caliburn.workflows.consultant_controls import ConsultantControlWorkflow
from caliburn.workflows.consultant_supervisor import ConsultantSupervisor
from tests.integration.test_consultant_completion import complete, start_turn
from tests.integration.test_execution_control import admit_scope
from tests.unit.test_response_loop import response_at

pytestmark = pytest.mark.postgres


def test_pause_and_cancel_before_first_writer(client: TestClient) -> None:
    scope = admit_scope(client)

    async def scenario() -> None:
        db = client.app.state.database

        async def run(writer: ExecutionWriter) -> None:
            pytest.fail("A control before startup cannot run the model")

        supervisor = ConsultantSupervisor(
            sessions=db.sessions,
            run=run,
            process_lock=PostgresProcessLock(db.settings),
        )
        controls = ConsultantControlWorkflow(db.sessions, InMemorySaver(), supervisor)
        pending = await controls.pause(scope)
        assert pending.status == ExecutionStatus.ACTIVE
        assert pending.pause_requested and pending.writer_id is None
        cancelled = await controls.cancel(scope)
        assert cancelled.status == ExecutionStatus.CANCELLED
        assert (await controls.cancel(scope)) == cancelled

    client.portal.call(scenario)


def test_cancel_fences_and_discards_before_local_task_is_interrupted(client: TestClient) -> None:
    turn = start_turn(client)

    async def scenario() -> None:
        db = client.app.state.database
        entered = asyncio.Event()
        observed: list[ExecutionStatus] = []

        async def run(writer: ExecutionWriter) -> None:
            entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                async with db.sessions() as session:
                    info = await executions.read_execution(session, writer.scope)
                    observed.append(info.status)
                    with pytest.raises(CandidateStateError):
                        await candidate_service.read_position(
                            session,
                            writer.scope.job_file_id,
                            writer.scope.execution_id,
                        )

        supervisor = ConsultantSupervisor(
            sessions=db.sessions,
            run=run,
            process_lock=PostgresProcessLock(db.settings),
        )
        controls = ConsultantControlWorkflow(db.sessions, InMemorySaver(), supervisor)
        try:
            await supervisor.start()
            await asyncio.wait_for(entered.wait(), 3)
            result = await controls.cancel(turn.writer.scope)
            assert result.status == ExecutionStatus.CANCELLED
            assert observed == [ExecutionStatus.CANCELLED]
        finally:
            await supervisor.close()

    client.portal.call(scenario)


def test_cancel_returns_completed_winner_without_rolling_back(client: TestClient) -> None:
    turn = start_turn(client)
    original = complete(client, turn)

    async def scenario() -> None:
        db = client.app.state.database

        async def run(writer: ExecutionWriter) -> None:
            pytest.fail("A terminal Turn cannot run")

        supervisor = ConsultantSupervisor(
            sessions=db.sessions,
            run=run,
            process_lock=PostgresProcessLock(db.settings),
        )
        controls = ConsultantControlWorkflow(db.sessions, InMemorySaver(), supervisor)
        assert (await controls.cancel(turn.writer.scope)).status == ExecutionStatus.COMPLETED

    client.portal.call(scenario)
    assert complete(client, turn) == original


def test_resume_cannot_release_paused_domain_without_native_interrupt(client: TestClient) -> None:
    scope = admit_scope(client)

    async def scenario() -> None:
        db = client.app.state.database
        async with db.sessions.begin() as session:
            writer = await executions.claim_writer(session, scope, writer_id=uuid4())
            # Incomplete caller acknowledgement is not proof of a native safe point.
            await executions.pause_execution(session, writer)

        async def run(writer: ExecutionWriter) -> None:
            pytest.fail("A missing original interrupt never authorizes a runner")

        supervisor = ConsultantSupervisor(
            sessions=db.sessions,
            run=run,
            process_lock=PostgresProcessLock(db.settings),
        )
        controls = ConsultantControlWorkflow(db.sessions, InMemorySaver(), supervisor)
        try:
            await supervisor.start()
            with pytest.raises(ExecutionStateError, match="native Step pause"):
                await controls.resume(scope)
            async with db.sessions() as session:
                info = await executions.read_execution(session, scope)
                assert info.status == ExecutionStatus.PAUSED
                assert info.writer_id == writer.writer_id
        finally:
            await supervisor.close()

    client.portal.call(scenario)


@pytest.mark.parametrize(
    ("restart_after_resume_commit", "pause_before_completion"),
    [(False, False), (True, False), (False, True)],
)
def test_resume_original_interrupt_without_new_model_request_or_budget(
    client: TestClient,
    database_settings: DatabaseSettings,
    restart_after_resume_commit: bool,
    pause_before_completion: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from caliburn.workflows.consultant_controls import run_consultant_with_controls

    created = client.post(
        "/api/job-files",
        json={
            "command_id": str(uuid4()),
            "display_name": "續作測試",
            "employee_name": "合成人員",
        },
    ).json()
    file_id = UUID(created["job_file_id"])
    accepted = client.post(
        f"/api/job-files/{file_id}/inputs",
        json={
            "command_id": str(uuid4()),
            "text": "我負責網站交付。",
        },
    ).json()
    scope = ExecutionScope(file_id, UUID(accepted["execution_id"]), ExecutionKind.CONSULTANT_TURN)

    async def scenario() -> None:
        db = client.app.state.database
        paused = asyncio.Event()
        returned = asyncio.Event()
        finished = asyncio.Event()
        sent: list[dict] = []
        completion_pause_requested = False
        original_complete = ConsultantCompletionWorkflow.complete

        async def pause_at_commit(owner, *args, **kwargs):
            nonlocal completion_pause_requested
            if pause_before_completion and not completion_pause_requested:
                completion_pause_requested = True
                await controls.pause(scope)
            return await original_complete(owner, *args, **kwargs)

        monkeypatch.setattr(ConsultantCompletionWorkflow, "complete", pause_at_commit)

        async def respond(request: httpx2.Request) -> httpx2.Response:
            if request.url.path.endswith("/input_tokens"):
                return httpx2.Response(
                    200, json={"object": "response.input_tokens", "input_tokens": 100}
                )
            sent.append(json.loads(request.content))
            if not pause_before_completion:
                await controls.pause(scope)
            raw = response_at(1, final=True).model_dump(mode="json")
            raw["service_tier"] = "default"
            return httpx2.Response(200, json=raw)

        dsn = make_conninfo(
            database_settings.url, options=f"-c search_path={database_settings.schema}"
        )
        async with AsyncPostgresSaver.from_conn_string(
            dsn, serde=create_graph_serializer()
        ) as saver:
            await saver.setup()
            sdk = create_responses_client(
                api_key="synthetic",
                timeout_seconds=5,
                http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(respond)),
            )
            runner = ConsultantRunner(db.sessions, saver, sdk, ModelSettings(api_key="synthetic"))

            async def held_run(writer: ExecutionWriter, *, resume_interrupt_id: str | None = None):
                result = await runner.run(writer, resume_interrupt_id=resume_interrupt_id)
                if isinstance(result, PausedResponseLoop):
                    paused.set()
                    await returned.wait()  # Deliberately hold the old invocation after ack.
                else:
                    finished.set()
                return result

            wrapped = partial(
                run_consultant_with_controls,
                sessions=db.sessions,
                checkpointer=saver,
                run=held_run,
            )
            supervisor = ConsultantSupervisor(
                sessions=db.sessions,
                run=wrapped,
                process_lock=PostgresProcessLock(db.settings),
            )
            controls = ConsultantControlWorkflow(db.sessions, saver, supervisor)
            resume_task = None
            replacement = None
            try:
                await supervisor.start()
                try:
                    await asyncio.wait_for(paused.wait(), 5)
                except TimeoutError:
                    assert not supervisor.failures, {
                        str(key.execution_id): type(error).__name__
                        for key, error in supervisor.failures.items()
                    }
                    raise
                async with db.sessions() as session:
                    before = await budgets.read_execution_budget(session, scope)
                    usage_before = await budgets.read_budget_usage(session, scope)
                if restart_after_resume_commit:
                    returned.set()
                    await supervisor.close()

                    class CrashBeforeWake(ConsultantSupervisor):
                        def allow_reentry(self, scope: ExecutionScope) -> None:
                            raise RuntimeError("synthetic crash after resume commit")

                    supervisor = CrashBeforeWake(
                        sessions=db.sessions,
                        run=wrapped,
                        process_lock=PostgresProcessLock(db.settings),
                    )
                    await supervisor.start()  # Paused executions are not dispatched.
                    controls = ConsultantControlWorkflow(db.sessions, saver, supervisor)
                    with pytest.raises(RuntimeError, match="after resume commit"):
                        await controls.resume(scope)
                    await supervisor.close()
                    replacement = ConsultantSupervisor(
                        sessions=db.sessions,
                        run=wrapped,
                        process_lock=PostgresProcessLock(db.settings),
                    )
                    await replacement.start()
                else:
                    resume_task = asyncio.create_task(controls.resume(scope))
                    await asyncio.sleep(0)
                    assert not resume_task.done()
                    async with db.sessions() as session:
                        assert (
                            await executions.read_execution(session, scope)
                        ).status == ExecutionStatus.PAUSED
                    returned.set()
                    await asyncio.wait_for(resume_task, 5)
                await asyncio.wait_for(finished.wait(), 5)
                async with db.sessions() as session:
                    after = await budgets.read_execution_budget(session, scope)
                    usage_after = await budgets.read_budget_usage(session, scope)
                    assert (
                        await executions.read_execution(session, scope)
                    ).status == ExecutionStatus.COMPLETED
                assert after == before
                assert usage_after == usage_before
                assert len(sent) == 1
            finally:
                returned.set()
                if resume_task is not None:
                    await asyncio.gather(resume_task, return_exceptions=True)
                if replacement is not None:
                    await replacement.close()
                await supervisor.close()
                await sdk.close()

    client.portal.call(scenario)
