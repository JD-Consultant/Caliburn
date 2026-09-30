"""Accepting employee input is durable admission, never formal interview promotion."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import UUID, uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.bootstrap import create_app
from caliburn.features.executions import service as executions
from caliburn.features.executions.models import ExecutionKind, ExecutionScope, ExecutionStatus
from caliburn.features.interviews import service as interviews
from caliburn.features.interviews.models import SubmitInterviewInput
from caliburn.features.job_files import service as job_files
from caliburn.settings import DatabaseSettings, Settings

pytestmark = pytest.mark.postgres


def test_input_acceptance_preserves_original_without_granting_formal_sequence(
    client: TestClient, database_connection: psycopg.Connection
) -> None:
    created = client.post(
        "/api/job-files",
        json={"command_id": str(uuid4()), "display_name": "盤點", "employee_name": "林員工"},
    ).json()
    file_id = created["job_file_id"]
    payload = {"command_id": str(uuid4()), "text": " 每月一次。\n也會協助盤點。 "}
    response = client.post(f"/api/job-files/{file_id}/inputs", json=payload)
    assert response.status_code == 202, response.text
    accepted = response.json()
    assert accepted["job_file_id"] == file_id
    assert "interview_sequence" not in accepted
    assert database_connection.execute(
        "SELECT speaker, interview_text FROM interview_texts WHERE source_id = %s",
        (accepted["source_id"],),
    ).fetchone() == ("employee", payload["text"])
    assert [
        message["interview_sequence"]
        for message in client.get(f"/api/job-files/{file_id}/interviews").json()["messages"]
    ] == [1]
    replay = client.post(f"/api/job-files/{file_id}/inputs", json=payload)
    assert replay.status_code == 200
    assert replay.json() == accepted


def create_file(client: TestClient) -> str:
    return client.post(
        "/api/job-files",
        json={"command_id": str(uuid4()), "display_name": "盤點", "employee_name": "林員工"},
    ).json()["job_file_id"]


def test_concurrent_retransmissions_accept_one_input_and_one_execution(
    client: TestClient, database_connection: psycopg.Connection
) -> None:
    file_id = create_file(client)
    payload = {"command_id": str(uuid4()), "text": "每月一次"}
    with ThreadPoolExecutor(max_workers=4) as pool:
        responses = list(
            pool.map(
                lambda _: client.post(f"/api/job-files/{file_id}/inputs", json=payload), range(8)
            )
        )
    assert sorted(r.status_code for r in responses) == [200] * 7 + [202]
    assert all(r.json() == responses[0].json() for r in responses)
    assert database_connection.execute("SELECT count(*) FROM interview_inputs").fetchone() == (1,)
    assert database_connection.execute("SELECT count(*) FROM executions").fetchone() == (1,)


def test_different_concurrent_inputs_cannot_start_two_consultant_turns(
    client: TestClient, database_connection: psycopg.Connection
) -> None:
    file_id = create_file(client)
    with ThreadPoolExecutor(max_workers=4) as pool:
        responses = list(
            pool.map(
                lambda _: client.post(
                    f"/api/job-files/{file_id}/inputs",
                    json={"command_id": str(uuid4()), "text": "每月一次"},
                ),
                range(8),
            )
        )
    assert sorted(r.status_code for r in responses) == [202] + [409] * 7
    assert database_connection.execute("SELECT count(*) FROM interview_inputs").fetchone() == (1,)
    assert database_connection.execute("SELECT count(*) FROM interview_texts").fetchone() == (2,)


def test_command_scope_is_per_file_and_conflicting_payload_is_rejected(client: TestClient) -> None:
    first, second = create_file(client), create_file(client)
    payload = {"command_id": str(uuid4()), "text": "每月一次"}
    accepted = client.post(f"/api/job-files/{first}/inputs", json=payload)
    assert accepted.status_code == 202
    conflict = client.post(f"/api/job-files/{first}/inputs", json=payload | {"text": "每週一次"})
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "input_command_conflict"
    other = client.post(f"/api/job-files/{second}/inputs", json=payload)
    assert other.status_code == 202
    assert other.json()["source_id"] != accepted.json()["source_id"]
    assert other.json()["execution_id"] != accepted.json()["execution_id"]


def test_cancelled_input_replay_never_reactivates_or_grants_formal_eligibility(
    client: TestClient, database_connection: psycopg.Connection
) -> None:
    file_id = create_file(client)
    payload = {"command_id": str(uuid4()), "text": "每月一次"}
    accepted = client.post(f"/api/job-files/{file_id}/inputs", json=payload).json()
    scope = ExecutionScope(
        UUID(file_id), UUID(accepted["execution_id"]), ExecutionKind.CONSULTANT_TURN
    )

    async def cancel_at_domain_boundary() -> None:
        # No candidate/context exists yet. Full A rollback coordination belongs to T08.
        async with client.app.state.database.sessions.begin() as session:
            writer = await executions.claim_writer(session, scope, writer_id=uuid4())
            await executions.finish_execution(session, writer, ExecutionStatus.CANCELLED)

    client.portal.call(cancel_at_domain_boundary)
    retried = client.post(
        f"/api/job-files/{file_id}/inputs", json=payload | {"command_id": str(uuid4())}
    )
    assert retried.status_code == 202
    assert retried.json()["execution_id"] != accepted["execution_id"]
    assert retried.json()["source_id"] != accepted["source_id"]
    replay = client.post(f"/api/job-files/{file_id}/inputs", json=payload)
    assert replay.status_code == 200 and replay.json() == accepted
    assert database_connection.execute(
        "SELECT status FROM executions WHERE execution_id = %s", (accepted["execution_id"],)
    ).fetchone() == ("cancelled",)
    assert database_connection.execute(
        "SELECT interview_sequence FROM formal_interviews"
    ).fetchall() == [(1,)]
    assert database_connection.execute(
        "SELECT interview_text FROM interview_texts WHERE source_id = %s", (accepted["source_id"],)
    ).fetchone() == (payload["text"],)


def test_failure_after_original_write_rolls_back_admission_and_acceptance(
    client: TestClient, database_connection: psycopg.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    file_id = create_file(client)
    payload = {"command_id": str(uuid4()), "text": "每月一次"}
    original = interviews.accept_input

    async def fail_after_save(
        session: AsyncSession, command: SubmitInterviewInput, *, execution_id: UUID
    ) -> None:
        await original(session, command, execution_id=execution_id)
        raise RuntimeError("injected after acceptance write")

    with monkeypatch.context() as patch:
        patch.setattr(interviews, "accept_input", fail_after_save)
        with pytest.raises(RuntimeError, match="injected"):
            client.post(f"/api/job-files/{file_id}/inputs", json=payload)
    assert database_connection.execute("SELECT count(*) FROM executions").fetchone() == (0,)
    assert database_connection.execute("SELECT count(*) FROM interview_inputs").fetchone() == (0,)
    assert database_connection.execute("SELECT count(*) FROM interview_texts").fetchone() == (1,)
    assert client.post(f"/api/job-files/{file_id}/inputs", json=payload).status_code == 202


@pytest.mark.parametrize("invalid_text", ["", " \n\t", "\u3000", "text\x00", {}, 7])
def test_invalid_input_has_no_admission_effect(
    client: TestClient, database_connection: psycopg.Connection, invalid_text: object
) -> None:
    file_id = create_file(client)
    response = client.post(
        f"/api/job-files/{file_id}/inputs", json={"command_id": str(uuid4()), "text": invalid_text}
    )
    assert response.status_code == 422
    assert database_connection.execute("SELECT count(*) FROM executions").fetchone() == (0,)


def test_input_for_missing_file_is_not_accepted(client: TestClient) -> None:
    response = client.post(
        f"/api/job-files/{uuid4()}/inputs", json={"command_id": str(uuid4()), "text": "原文"}
    )
    assert response.status_code == 404


def test_acceptance_replays_after_app_instance_is_recreated(
    client: TestClient, database_settings: DatabaseSettings
) -> None:
    file_id = create_file(client)
    payload = {"command_id": str(uuid4()), "text": "每月一次"}
    original = client.post(f"/api/job-files/{file_id}/inputs", json=payload).json()
    with TestClient(
        create_app(Settings(database=database_settings)),
        base_url="http://127.0.0.1:8100",
        headers={"Origin": "http://127.0.0.1:8100"},
        backend_options={"loop_factory": asyncio.SelectorEventLoop},
    ) as reconnected:
        replay = reconnected.post(f"/api/job-files/{file_id}/inputs", json=payload)
        assert replay.status_code == 200
        assert replay.json() == original


def test_one_locked_file_does_not_prevent_another_file_accepting_input(
    client: TestClient, database_connection: psycopg.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    locked_file, other_file = create_file(client), create_file(client)
    entered = Event()
    original_lock = job_files.lock_job_file

    async def observe_lock(session: AsyncSession, job_file_id: UUID) -> None:
        if str(job_file_id) == locked_file:
            entered.set()
        await original_lock(session, job_file_id)

    monkeypatch.setattr(job_files, "lock_job_file", observe_lock)
    with ThreadPoolExecutor(max_workers=1) as pool:
        with database_connection.transaction():
            database_connection.execute(
                "SELECT job_file_id FROM job_files WHERE job_file_id = %s FOR UPDATE",
                (locked_file,),
            )
            blocked = pool.submit(
                client.post,
                f"/api/job-files/{locked_file}/inputs",
                json={"command_id": str(uuid4()), "text": "等待自己的檔案"},
            )
            assert entered.wait(5), "request did not reach the file lock"
            assert not blocked.done()
            assert (
                client.post(
                    f"/api/job-files/{other_file}/inputs",
                    json={"command_id": str(uuid4()), "text": "另一份檔案可繼續"},
                ).status_code
                == 202
            )
        assert blocked.result(timeout=5).status_code == 202


def test_acceptance_links_are_immutable_and_cannot_cross_job_files(
    client: TestClient, database_connection: psycopg.Connection
) -> None:
    first, second = create_file(client), create_file(client)
    client.post(
        f"/api/job-files/{first}/inputs", json={"command_id": str(uuid4()), "text": "甲的原文"}
    )
    second_input = client.post(
        f"/api/job-files/{second}/inputs", json={"command_id": str(uuid4()), "text": "乙的原文"}
    ).json()
    with pytest.raises(psycopg.errors.CheckViolation):
        database_connection.execute(
            "UPDATE interview_inputs SET source_id = %s WHERE job_file_id = %s",
            (second_input["source_id"], first),
        )
    with pytest.raises(psycopg.errors.CheckViolation):
        database_connection.execute("DELETE FROM interview_inputs WHERE job_file_id = %s", (first,))
    # Use unbound records so neither UNIQUE nor a missing identity masks the scope FK.
    first_source, second_source, first_execution, second_execution = [uuid4() for _ in range(4)]
    for file_id, source_id, execution_id in (
        (first, first_source, first_execution),
        (second, second_source, second_execution),
    ):
        database_connection.execute(
            "INSERT INTO interview_texts VALUES (%s, %s, 'employee', '獨立原文')",
            (source_id, file_id),
        )
        database_connection.execute(
            "INSERT INTO executions (execution_id, job_file_id, kind, status) "
            "VALUES (%s, %s, 'consultant_turn', 'failed')",
            (execution_id, file_id),
        )
    for source_id, execution_id in (
        (second_source, first_execution),
        (first_source, second_execution),
    ):
        with pytest.raises(psycopg.errors.ForeignKeyViolation):
            database_connection.execute(
                "INSERT INTO interview_inputs VALUES (%s, %s, %s, %s)",
                (first, uuid4(), source_id, execution_id),
            )
