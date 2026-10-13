"""Bounded pure DB recovery through bootstrap, real Agent, PG saver and SDK transport."""

import asyncio
import json
import sys
import time
from uuid import UUID, uuid4

import httpx2
import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg import errors
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSessionTransaction

from caliburn.adapters.openai_responses import create_responses_client
from caliburn.app_composition import AppComposition
from caliburn.bootstrap import create_app
from caliburn.features.executions import budgets, history
from caliburn.features.executions import service as executions
from caliburn.features.job_description import candidate_service
from caliburn.settings import ModelSettings, Settings
from caliburn.workflows.executions import model_requests
from tests.fixtures.response_loop import response_at
from tests.unit.test_response_streaming import WireStream

pytestmark = pytest.mark.postgres


@pytest.mark.parametrize(
    "failure",
    [
        "admission_ack",
        "account_ack",
        "saved_count_guard",
        "admission_rollback",
        "permanent",
        "exhausted",
        "completion_ack",
        "capture_ack",
        "preparation_ack",
        "failure_ack",
        "entry_guard",
        "completed_entry_read",
        "admission_wait_mix",
        "admission_wait_exhaust",
    ],
)
def test_consultant_recovers_original_database_operation_without_model_replay(
    database_settings, monkeypatch, failure
):
    sent = []
    counts = []
    admissions = []
    injected = []
    original_reserve = budgets.reserve_outbound_attempt
    original_account = budgets.record_attempt_cost
    original_read = executions.read_execution
    original_guard = executions.lock_active_writer
    original_exit = AsyncSessionTransaction.__aexit__
    original_complete = history.complete_context_histories
    original_capture = candidate_service.start_candidate
    original_adopt = history.adopt_prepared_context
    original_failure = budgets.record_attempt_failure
    failure_values = []
    admission_keys = []
    original_admit = model_requests.ModelRequestExecutor._admit_request

    def transient():
        return DBAPIError.instance(
            None, None, errors.ConnectionFailure(), psycopg.Error, connection_invalidated=True
        )

    async def reserve(session, writer, **kwargs):
        if failure in ("permanent", "exhausted"):
            injected.append(None)
            driver = (
                errors.InvalidPassword()
                if failure == "permanent"
                else errors.SerializationFailure()
            )
            raise DBAPIError.instance(None, None, driver, psycopg.Error)
        result = await original_reserve(session, writer, **kwargs)
        admissions.append((kwargs["attempt_id"], result.created))
        if failure == "admission_rollback" and not injected:
            injected.append(None)
            raise DBAPIError.instance(None, None, errors.SerializationFailure(), psycopg.Error)
        if (
            failure in ("admission_ack", "admission_wait_mix", "admission_wait_exhaust")
            and not injected
        ):
            session.info["recovery_test_ack"] = True
        return result

    async def account(session, scope, attempt_id, **kwargs):
        result = await original_account(session, scope, attempt_id, **kwargs)
        if failure == "account_ack" and not injected:
            session.info["recovery_test_ack"] = True
        return result

    async def guard(session, writer):
        if failure == "entry_guard" and not injected:
            injected.append(None)
            raise transient()
        if failure == "saved_count_guard" and counts and not sent and not injected:
            injected.append(None)
            raise transient()
        return await original_guard(session, writer)

    async def exit_transaction(self, *args):
        await original_exit(self, *args)
        if self.session.info.pop("recovery_test_ack", False) and not injected:
            injected.append(None)
            raise transient()

    async def complete(session, *args):
        result = await original_complete(session, *args)
        if failure == "completion_ack" and not injected:
            session.info["recovery_test_ack"] = True
        return result

    async def capture(session, *args):
        result = await original_capture(session, *args)
        if failure == "capture_ack" and not injected:
            session.info["recovery_test_ack"] = True
        return result

    async def adopt(session, *args):
        result = await original_adopt(session, *args)
        if failure == "preparation_ack" and not injected:
            session.info["recovery_test_ack"] = True
        return result

    async def record_failure(session, *args, **kwargs):
        result = await original_failure(session, *args, **kwargs)
        if failure == "failure_ack":
            failure_values.append(kwargs["failure"])
            if not injected:
                session.info["recovery_test_ack"] = True
        return result

    async def admit(self, outbound, reservation, attempt_id):
        if (
            failure in ("admission_wait_mix", "admission_wait_exhaust")
            and outbound.kind.value == "token_count"
        ):
            admission_keys.append(attempt_id)
            if len(admission_keys) == 2:
                raise model_requests._RetryNotReadyError(0)
            if len(admission_keys) == 3 or (
                failure == "admission_wait_exhaust" and len(admission_keys) == 4
            ):
                injected.append(None)
                raise transient()
        return await original_admit(self, outbound, reservation, attempt_id)

    monkeypatch.setattr(model_requests.ModelRequestExecutor, "_admit_request", admit)

    async def read(session, scope):
        if (
            failure == "completed_entry_read"
            and sys._getframe(1).f_code.co_name == "_read_completion_boundary"
            and not injected
        ):
            injected.append(None)
            raise DBAPIError.instance(None, None, errors.SerializationFailure(), psycopg.Error)
        return await original_read(session, scope)

    monkeypatch.setattr(executions, "read_execution", read)
    monkeypatch.setattr(history, "complete_context_histories", complete)
    monkeypatch.setattr(candidate_service, "start_candidate", capture)
    monkeypatch.setattr(history, "adopt_prepared_context", adopt)
    monkeypatch.setattr(budgets, "record_attempt_failure", record_failure)
    monkeypatch.setattr(budgets, "reserve_outbound_attempt", reserve)
    monkeypatch.setattr(budgets, "record_attempt_cost", account)
    monkeypatch.setattr(executions, "lock_active_writer", guard)
    monkeypatch.setattr(AsyncSessionTransaction, "__aexit__", exit_transaction)

    def respond(request):
        payload = json.loads(request.content)
        if request.url.path.endswith("/input_tokens"):
            counts.append(payload)
            return httpx2.Response(
                200, json={"object": "response.input_tokens", "input_tokens": 500}
            )
        sent.append(payload)
        if failure == "failure_ack" and len(sent) == 1:
            return httpx2.Response(
                429,
                headers={"retry-after": "0"},
                json={"error": {"code": "rate_limit_exceeded", "message": "synthetic"}},
            )
        raw = response_at(1, final=True).model_dump(mode="json")
        raw["model"] = payload["model"]
        raw["service_tier"] = "default"
        return httpx2.Response(
            200,
            headers={"content-type": "text/event-stream"},
            stream=WireStream([{"type": "response.completed", "response": raw}]),
        )

    def sdk(settings):
        return create_responses_client(
            api_key="synthetic",
            timeout_seconds=5,
            http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(respond)),
        )

    app = create_app(
        Settings(
            database=database_settings,
            model=ModelSettings(api_key="synthetic", max_attempts_per_request=1),
        ),
        composition=AppComposition(create_responses_client=sdk),
    )
    with TestClient(
        app,
        base_url="http://127.0.0.1:8100",
        headers={"Origin": "http://127.0.0.1:8100"},
        backend_options={"loop_factory": asyncio.SelectorEventLoop},
    ) as client:
        created = client.post(
            "/api/job-files",
            json={"command_id": str(uuid4()), "display_name": "恢復", "employee_name": "合成人員"},
        )
        file_id = created.json()["job_file_id"]
        accepted = client.post(
            f"/api/job-files/{file_id}/inputs",
            json={"command_id": str(uuid4()), "text": "合成恢復原話"},
        )
        execution_id = accepted.json()["execution_id"]
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            status = client.get(f"/api/job-files/{file_id}/consultant-turns/{execution_id}").json()
            if status["status"] != "active":
                break
            time.sleep(0.02)
        stopped = failure in ("permanent", "exhausted", "admission_wait_exhaust")
        assert status["status"] == ("failed" if stopped else "completed"), status
        assert len(client.get(f"/api/job-files/{file_id}/interviews").json()["messages"]) == (
            1 if stopped else 3
        )

        async def rows():
            from caliburn.features.executions.models import ExecutionKind, ExecutionScope

            scope = ExecutionScope(UUID(file_id), UUID(execution_id), ExecutionKind.CONSULTANT_TURN)
            async with app.state.database.sessions() as session:
                return await budgets.read_budget_usage(session, scope)

        usage = client.portal.call(rows)
        assert usage.outbound_attempts == (
            (1 if failure == "admission_wait_exhaust" else 0)
            if stopped
            else (3 if failure == "failure_ack" else 2)
        )
    assert len(injected) == (
        3
        if failure in ("exhausted", "admission_wait_exhaust")
        else (2 if failure == "admission_wait_mix" else 1)
    )
    assert len(counts) == (0 if stopped else 1)
    assert len(sent) == (0 if stopped else (2 if failure == "failure_ack" else 1))
    if failure in ("admission_wait_mix", "admission_wait_exhaust"):
        assert len(admission_keys) == 4 and len(set(admission_keys)) == 1
    if failure == "failure_ack":
        assert len(failure_values) == 2 and failure_values[0] == failure_values[1]
    if failure == "admission_ack":
        assert admissions[0][0] == admissions[1][0]
        assert admissions[0][1] is True and admissions[1][1] is False


@pytest.mark.parametrize("boundary", ["b1_handoff", "b2_publication", "memory_tool"])
def test_memory_parent_recovers_original_handoff_publication_and_tool_receipt(
    database_settings, monkeypatch, boundary
):
    from caliburn.features.work_memory import candidate_service, consolidation_requests
    from tests.integration.test_consultant_memory_http_journey import (
        test_completed_notification_publishes_two_layers_and_next_turn_sees_maps,
    )

    injected = []
    recorded = []
    original_record = consolidation_requests.record_operation
    original_edit = candidate_service.edit_candidate
    original_exit = AsyncSessionTransaction.__aexit__

    async def record(session, **kwargs):
        result = await original_record(session, **kwargs)
        target = (boundary == "b1_handoff" and result.get("role") == "work_situation_analyst") or (
            boundary == "b2_publication" and result.get("role") == "work_understanding_analyst"
        )
        if target and not injected:
            recorded.append(result)
            session.info["memory_recovery_ack"] = True
        return result

    async def edit(session, command):
        result = await original_edit(session, command)
        if boundary == "memory_tool" and not injected:
            recorded.append(result)
            session.info["memory_recovery_ack"] = True
        return result

    async def exit_transaction(self, *args):
        await original_exit(self, *args)
        if self.session.info.pop("memory_recovery_ack", False) and not injected:
            injected.append(None)
            raise DBAPIError.instance(
                None, None, errors.ConnectionFailure(), psycopg.Error, connection_invalidated=True
            )

    monkeypatch.setattr(consolidation_requests, "record_operation", record)
    monkeypatch.setattr(candidate_service, "edit_candidate", edit)
    monkeypatch.setattr(AsyncSessionTransaction, "__aexit__", exit_transaction)
    test_completed_notification_publishes_two_layers_and_next_turn_sees_maps(database_settings)
    assert len(injected) == len(recorded) == 1


@pytest.mark.parametrize("boundary", ["pause_ack", "resume_ack", "pause_intent_ack"])
def test_original_saved_step_pause_and_http_resume_survive_control_ack_loss(
    database_settings, monkeypatch, boundary
):
    import threading

    from tests.fixtures.response_transport import response_http_reply

    entered = threading.Event()
    release = asyncio.Event()
    model_calls = []
    injected = []
    original_exit = AsyncSessionTransaction.__aexit__
    original_pause = executions.pause_execution
    original_resume = executions.resume_execution
    original_intent = executions.request_pause

    async def change(session, target, original, *args):
        result = await original(session, *args)
        if target == boundary and not injected:
            session.info["control_ack_loss"] = True
        return result

    async def pause(session, *args):
        return await change(session, "pause_ack", original_pause, *args)

    async def resume(session, *args):
        return await change(session, "resume_ack", original_resume, *args)

    async def intent(session, *args):
        return await change(session, "pause_intent_ack", original_intent, *args)

    async def exit_transaction(self, *args):
        await original_exit(self, *args)
        if self.session.info.pop("control_ack_loss", False) and not injected:
            injected.append(None)
            raise DBAPIError.instance(None, None, errors.ConnectionFailure(), psycopg.Error)

    monkeypatch.setattr(executions, "pause_execution", pause)
    monkeypatch.setattr(executions, "resume_execution", resume)
    monkeypatch.setattr(executions, "request_pause", intent)
    monkeypatch.setattr(AsyncSessionTransaction, "__aexit__", exit_transaction)

    async def respond(request):
        if request.url.path.endswith("/input_tokens"):
            return httpx2.Response(
                200, json={"object": "response.input_tokens", "input_tokens": 500}
            )
        model_calls.append(request)
        entered.set()
        await release.wait()
        raw = response_at(1, final=True).model_dump(mode="json")
        raw["service_tier"] = "default"
        return response_http_reply(request, raw)

    def sdk(settings):
        return create_responses_client(
            api_key="synthetic",
            timeout_seconds=10,
            http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(respond)),
        )

    app = create_app(
        Settings(database=database_settings, model=ModelSettings(api_key="synthetic")),
        composition=AppComposition(create_responses_client=sdk),
    )
    with TestClient(
        app,
        base_url="http://127.0.0.1:8100",
        headers={"Origin": "http://127.0.0.1:8100"},
        backend_options={"loop_factory": asyncio.SelectorEventLoop},
    ) as client:
        file_id = client.post(
            "/api/job-files",
            json={"command_id": str(uuid4()), "display_name": "控制恢復", "employee_name": "合成"},
        ).json()["job_file_id"]
        execution_id = client.post(
            f"/api/job-files/{file_id}/inputs",
            json={"command_id": str(uuid4()), "text": "合成控制原話"},
        ).json()["execution_id"]
        path = f"/api/job-files/{file_id}/consultant-turns/{execution_id}"
        assert entered.wait(5)
        assert client.post(path + "/pause").status_code == 200
        client.portal.call(release.set)
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            state = client.get(path).json()
            if state["status"] == "paused":
                break
            time.sleep(0.02)
        assert state["status"] == "paused", state
        assert client.post(path + "/resume").status_code == 200
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            state = client.get(path).json()
            if state["status"] != "active":
                break
            time.sleep(0.02)
        assert state["status"] == "completed", state
        assert len(client.get(f"/api/job-files/{file_id}/interviews").json()["messages"]) == 3
    assert len(injected) == len(model_calls) == 1


def test_http_cancel_during_database_backoff_cancels_task_without_outbound(
    database_settings, monkeypatch
):
    import threading

    from caliburn.adapters import database
    from tests.fixtures.response_transport import response_http_reply

    entered = threading.Event()
    injected = []
    sends = []
    original_retry = database.AsyncRetrying
    original_reserve = budgets.reserve_outbound_attempt
    allow_sends = False

    async def backoff(_seconds):
        entered.set()
        await asyncio.Event().wait()

    def retry(**kwargs):
        return original_retry(**kwargs, sleep=backoff)

    async def refuse_admission(*args, **kwargs):
        injected.append(None)
        raise DBAPIError.instance(None, None, errors.SerializationFailure(), psycopg.Error)

    def respond(request):
        if not allow_sends:
            pytest.fail("Cancelled admission cannot send any provider request")
        payload = json.loads(request.content)
        sends.append(payload)
        if request.url.path.endswith("/input_tokens"):
            return httpx2.Response(
                200, json={"object": "response.input_tokens", "input_tokens": 500}
            )
        raw = response_at(1, final=True).model_dump(mode="json")
        raw["service_tier"] = "default"
        return response_http_reply(request, raw)

    def sdk(settings):
        return create_responses_client(
            api_key="synthetic",
            timeout_seconds=5,
            http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(respond)),
        )

    monkeypatch.setattr(database, "AsyncRetrying", retry)
    monkeypatch.setattr(budgets, "reserve_outbound_attempt", refuse_admission)
    app = create_app(
        Settings(database=database_settings, model=ModelSettings(api_key="synthetic")),
        composition=AppComposition(create_responses_client=sdk),
    )
    with TestClient(
        app,
        base_url="http://127.0.0.1:8100",
        headers={"Origin": "http://127.0.0.1:8100"},
        backend_options={"loop_factory": asyncio.SelectorEventLoop},
    ) as client:
        file_id = client.post(
            "/api/job-files",
            json={"command_id": str(uuid4()), "display_name": "取消恢復", "employee_name": "合成"},
        ).json()["job_file_id"]
        execution_id = client.post(
            f"/api/job-files/{file_id}/inputs",
            json={"command_id": str(uuid4()), "text": "合成取消原話"},
        ).json()["execution_id"]
        path = f"/api/job-files/{file_id}/consultant-turns/{execution_id}"
        assert entered.wait(5)
        cancelled = client.post(path + "/cancel")
        assert cancelled.status_code == 200
        assert cancelled.json()["status"] == "cancelled"
        assert len(client.get(f"/api/job-files/{file_id}/interviews").json()["messages"]) == 1
        assert not app.state.consultant_supervisor.has_file_runner(UUID(file_id))
        assert sends == []
        monkeypatch.setattr(database, "AsyncRetrying", original_retry)
        monkeypatch.setattr(budgets, "reserve_outbound_attempt", original_reserve)
        allow_sends = True
        next_execution = client.post(
            f"/api/job-files/{file_id}/inputs",
            json={"command_id": str(uuid4()), "text": "取消後的新原話"},
        ).json()["execution_id"]
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            resumed = client.get(
                f"/api/job-files/{file_id}/consultant-turns/{next_execution}"
            ).json()
            if resumed["status"] != "active":
                break
            time.sleep(0.02)
        assert resumed["status"] == "completed", resumed
        assert client.get(path).json()["status"] == "cancelled"
        messages = client.get(f"/api/job-files/{file_id}/interviews").json()["messages"]
        assert [message["interview_sequence"] for message in messages] == [1, 2, 3]
        assert messages[1]["interview_text"] == "取消後的新原話"
        assert "合成取消原話" not in json.dumps(sends, ensure_ascii=False)
    assert len(injected) == 1
    assert len(sends) == 2
