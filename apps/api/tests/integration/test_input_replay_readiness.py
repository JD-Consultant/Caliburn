"""Existing input acceptance is readable without admitting new unavailable work."""

import asyncio
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient

from caliburn.adapters.process_lock import PostgresProcessLock
from caliburn.bootstrap import create_app
from caliburn.features.executions.models import ExecutionWriter
from caliburn.settings import DatabaseSettings, Settings
from caliburn.workflows.consultant_supervisor import ConsultantSupervisor

pytestmark = pytest.mark.postgres


@pytest.mark.parametrize("stopped_supervisor", [False, True])
def test_saved_input_replay_and_conflict_do_not_require_model_readiness(
    client: TestClient,
    database_settings: DatabaseSettings,
    database_connection: psycopg.Connection,
    stopped_supervisor: bool,
) -> None:
    client.base_url = "http://127.0.0.1:8100"
    file_id = client.post(
        "/api/job-files",
        json={"command_id": str(uuid4()), "display_name": "合成盤點", "employee_name": "合成員工"},
    ).json()["job_file_id"]
    payload = {"command_id": str(uuid4()), "text": " 每月一次。\n保留原文 "}
    original = client.post(f"/api/job-files/{file_id}/inputs", json=payload)
    assert original.status_code == 202

    async def must_not_run(writer: ExecutionWriter) -> None:
        raise AssertionError("Replay must not start another execution")

    with TestClient(
        create_app(Settings(database=database_settings)),
        base_url="http://127.0.0.1:8100",
        backend_options={"loop_factory": asyncio.SelectorEventLoop},
    ) as reconnected:
        if stopped_supervisor:
            reconnected.app.state.consultant_supervisor = ConsultantSupervisor(
                sessions=reconnected.app.state.database.sessions,
                run=must_not_run,
                process_lock=PostgresProcessLock(database_settings),
            )
        replay = reconnected.post(f"/api/job-files/{file_id}/inputs", json=payload)
        assert replay.status_code == 200, replay.text
        assert replay.json() == original.json()
        conflict = reconnected.post(
            f"/api/job-files/{file_id}/inputs", json=payload | {"text": payload["text"].strip()}
        )
        assert conflict.status_code == 409, conflict.text
        assert conflict.json()["detail"]["code"] == "input_command_conflict"
        refused = reconnected.post(
            f"/api/job-files/{file_id}/inputs", json=payload | {"command_id": str(uuid4())}
        )
        assert refused.status_code == 503, refused.text
        assert refused.json()["detail"]["code"] == (
            "consultant_unavailable" if stopped_supervisor else "model_not_configured"
        )

    assert database_connection.execute("SELECT count(*) FROM executions").fetchone() == (1,)
    assert database_connection.execute("SELECT count(*) FROM interview_inputs").fetchone() == (1,)
    assert database_connection.execute("SELECT count(*) FROM interview_texts").fetchone() == (2,)
    assert database_connection.execute("SELECT count(*) FROM formal_interviews").fetchone() == (1,)
