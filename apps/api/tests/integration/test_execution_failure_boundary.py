"""Production supervisors settle escaped work failures through the real PG owners.

Role analysis is replaced at its entry boundary: no provider traffic is needed to
verify terminal status, candidate abandonment and admission after failure.
"""

import asyncio
import time
from collections.abc import Iterator
from contextlib import contextmanager
from functools import partial
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from caliburn.agent_execution.tool_steps import ModelStepLimitError
from caliburn.agents.job_consultant.runner import ConsultantRunner
from caliburn.bootstrap import create_app
from caliburn.features.executions import service as executions
from caliburn.features.executions.models import ExecutionStatus
from caliburn.features.job_description.models import ProfileField, ReviseJdProfile, SetProfileField
from caliburn.features.work_memory import batch_persistence
from caliburn.settings import DatabaseSettings, ModelSettings, Settings
from caliburn.workflows.consultant_completion import ConsultantCompletionWorkflow
from caliburn.workflows.execution_failures import run_with_failure_boundary
from caliburn.workflows.jd_candidates import JdCandidateWorkflow
from caliburn.workflows.memory_batch import MemoryBatchWorkflow
from caliburn.workflows.memory_consolidation import MemoryConsolidationWorkflow
from caliburn.workflows.model_requests import PriorModelAttemptError
from tests.integration.test_consultant_completion import complete, read_head, start_turn, transact
from tests.integration.test_consultant_http_execution import create_file

pytestmark = pytest.mark.postgres


@contextmanager
def supervised_client(settings: DatabaseSettings) -> Iterator[TestClient]:
    with TestClient(
        create_app(Settings(database=settings, model=ModelSettings(api_key="synthetic"))),
        base_url="http://127.0.0.1:8100",
        headers={"Origin": "http://127.0.0.1:8100"},
        backend_options={"loop_factory": asyncio.SelectorEventLoop},
    ) as client:
        yield client


@pytest.mark.parametrize("failure_type", [ValueError, PriorModelAttemptError])
def test_escaped_consultant_failure_discards_draft_and_allows_new_input(
    database_settings, monkeypatch, failure_type, caplog
):
    calls = []

    async def fail_analysis(self, writer, **kwargs):
        calls.append(writer.scope)
        candidates = JdCandidateWorkflow(self.sessions)
        initial = await candidates.start(writer)
        await candidates.edit(
            writer,
            initial.scope,
            ReviseJdProfile(
                uuid4(),
                initial.revision_id,
                (SetProfileField(ProfileField.JOB_TITLE, "未完成的修改"),),
            ),
        )
        raise failure_type("synthetic private detail")

    monkeypatch.setattr(ConsultantRunner, "run", fail_analysis)
    with supervised_client(database_settings) as client:
        file_id = create_file(client)
        baseline = client.get(f"/api/job-files/{file_id}/jd/profile").json()
        for text in ("第一次輸入", "失敗後的新輸入"):
            submitted = client.post(
                f"/api/job-files/{file_id}/inputs",
                json={"command_id": str(uuid4()), "text": text},
            )
            assert submitted.status_code == 202
            execution_id = submitted.json()["execution_id"]
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline:
                status = client.get(
                    f"/api/job-files/{file_id}/consultant-turns/{execution_id}"
                ).json()
                if status["status"] != "active":
                    break
                time.sleep(0.02)
            assert status["status"] == "failed", status
            assert status["candidate"] is None
        assert len(calls) == 2 and calls[0] != calls[1]
        assert client.get(f"/api/job-files/{file_id}/jd/profile").json() == baseline
        assert len(client.get(f"/api/job-files/{file_id}/interviews").json()["messages"]) == 1
    assert "synthetic private detail" not in caplog.text


@pytest.mark.parametrize("role", ["consultant", "memory"])
def test_terminal_settlement_acknowledgement_failure_is_not_settled_twice(
    client, database_settings, monkeypatch, role
):
    turn = start_turn(client)
    requests = MemoryConsolidationWorkflow(client.app.state.database.sessions)
    if role == "memory":
        client.portal.call(requests.request, turn.writer, uuid4())
        complete(client, turn)
    owner_type, method_name, runner_type = (
        (ConsultantCompletionWorkflow, "stop", ConsultantRunner)
        if role == "consultant"
        else (MemoryConsolidationWorkflow, "fail", MemoryBatchWorkflow)
    )
    original_settle = getattr(owner_type, method_name)
    settlements = []

    async def lost_settlement_ack(self, writer, *args, **kwargs):
        settlements.append(writer)
        await original_settle(self, writer, *args, **kwargs)
        raise ConnectionError("synthetic settlement acknowledgement lost")

    async def exhausted_work(self, writer, **kwargs):
        raise ModelStepLimitError("synthetic exhausted step budget")

    monkeypatch.setattr(owner_type, method_name, lost_settlement_ack)
    monkeypatch.setattr(runner_type, "run", exhausted_work)
    with supervised_client(database_settings) as running:
        supervisor = getattr(running.app.state, f"{role}_supervisor")
        deadline = time.monotonic() + 3
        while (
            not settlements or supervisor.has_file_runner(turn.writer.scope.job_file_id)
        ) and time.monotonic() < deadline:
            time.sleep(0.02)
        assert settlements
        assert not supervisor.has_file_runner(turn.writer.scope.job_file_id)
        # The one failed acknowledgement is followed by an owner read, not a second
        # settlement. A proven durable terminal outcome no longer needs a handoff.
        assert not supervisor.failures
    assert len(settlements) == 1
    if role == "memory":
        assert client.portal.call(requests.failure_reason, turn.writer.scope.job_file_id) == (
            "ModelStepLimitError"
        )


def test_completion_acknowledgement_failure_preserves_original_result(client):
    turn = start_turn(client)
    completion = ConsultantCompletionWorkflow(client.app.state.database.sessions)

    async def lose_acknowledgement(writer):
        await completion.complete(writer, turn.candidate, "已確認的正式答覆", turn.completed)
        raise ConnectionError("synthetic lost acknowledgement")

    result = client.portal.call(
        partial(
            run_with_failure_boundary,
            turn.writer,
            run=lose_acknowledgement,
            settle_failure=lambda writer, _error: completion.stop(writer, ExecutionStatus.FAILED),
        )
    )
    assert result.status == ExecutionStatus.COMPLETED
    assert read_head(client, turn) == turn.completed
    file_id = turn.writer.scope.job_file_id
    assert client.get(f"/api/job-files/{file_id}/jd/profile").json()["revision_id"] == str(
        turn.candidate.revision_id
    )
    history = client.get(f"/api/job-files/{file_id}/interviews").json()["messages"]
    assert [item["interview_sequence"] for item in history] == [1, 2, 3]
    assert history[-1]["interview_text"] == "已確認的正式答覆"


def test_application_shutdown_keeps_active_candidate_for_restart(
    client, database_settings, monkeypatch
):
    turn = start_turn(client)
    entered = []

    async def wait_for_shutdown(self, writer, **kwargs):
        entered.append(writer)
        await asyncio.Event().wait()

    monkeypatch.setattr(ConsultantRunner, "run", wait_for_shutdown)
    with supervised_client(database_settings):
        deadline = time.monotonic() + 3
        while not entered and time.monotonic() < deadline:
            time.sleep(0.02)
        assert len(entered) == 1
    status = client.get(
        f"/api/job-files/{turn.writer.scope.job_file_id}/consultant-turns/"
        f"{turn.writer.scope.execution_id}"
    ).json()
    assert status["status"] == "active"
    assert status["candidate"] is not None
    assert read_head(client, turn) == turn.prepared


def test_escaped_memory_failure_is_durable_and_does_not_block_interview(
    client, database_settings, monkeypatch, caplog
):
    turn = start_turn(client)
    requests = MemoryConsolidationWorkflow(client.app.state.database.sessions)
    client.portal.call(requests.request, turn.writer, uuid4())
    complete(client, turn)
    seen = []

    async def fail_analysis(self, writer):
        seen.append(writer)
        # Admission has already created the real candidate batch.
        await self.requests.read_work(writer.scope)
        raise ValueError("synthetic private detail")

    monkeypatch.setattr(MemoryBatchWorkflow, "run", fail_analysis)
    with supervised_client(database_settings):
        deadline = time.monotonic() + 3
        reason = None
        while time.monotonic() < deadline:
            reason = client.portal.call(requests.failure_reason, turn.writer.scope.job_file_id)
            if reason:
                break
            time.sleep(0.02)
        assert reason == "execution_interrupted"
    assert len(seen) == 1
    assert transact(client, lambda s: executions.read_execution(s, seen[0].scope)).status == (
        ExecutionStatus.FAILED
    )
    batch = transact(
        client,
        lambda s: batch_persistence.read_batch(
            s, seen[0].scope.job_file_id, seen[0].scope.execution_id
        ),
    )
    assert batch.status == "discarded"
    assert client.portal.call(requests.discover).ready_file_ids == ()
    accepted = client.post(
        f"/api/job-files/{turn.writer.scope.job_file_id}/inputs",
        json={"command_id": str(uuid4()), "text": "繼續補充工作"},
    )
    assert accepted.status_code == 202
    assert "synthetic private detail" not in caplog.text
