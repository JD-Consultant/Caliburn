"""Manual profile changes preserve fixed revisions and the existing admission boundary."""

from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.features.executions import service as executions
from caliburn.features.executions.models import ExecutionKind, ExecutionScope
from caliburn.features.job_description import service
from caliburn.features.job_description.models import ReviseJdProfile

pytestmark = pytest.mark.postgres


def create_file(client: TestClient) -> str:
    response = client.post(
        "/api/job-files",
        json={"command_id": str(uuid4()), "display_name": "合成職務", "employee_name": "合成員工"},
    )
    assert response.status_code == 201
    return str(response.json()["job_file_id"])


def test_profile_starts_empty_and_partial_change_keeps_other_fields(client: TestClient) -> None:
    file_id = create_file(client)
    url = f"/api/job-files/{file_id}/jd/profile"
    original = client.get(url)
    assert original.status_code == 200
    assert original.json()["profile"] == {
        "job_title": None,
        "organization_unit": None,
        "reports_to": None,
        "purpose": None,
    }
    command = {
        "command_id": str(uuid4()),
        "expected_revision_id": original.json()["revision_id"],
        "changes": [
            {"action": "set_field", "field": "job_title", "value": "前端工程師"},
            {"action": "set_field", "field": "purpose", "value": "交付約定範圍的網站前端。"},
        ],
    }
    revised = client.post(url, json=command)
    assert revised.status_code == 200
    assert revised.json()["revision_id"] != original.json()["revision_id"]
    assert revised.json()["profile"] == {
        **original.json()["profile"],
        "job_title": "前端工程師",
        "purpose": "交付約定範圍的網站前端。",
    }
    assert client.get(url).json() == revised.json()
    cleared = client.post(
        url,
        json={
            "command_id": str(uuid4()),
            "expected_revision_id": revised.json()["revision_id"],
            "changes": [{"action": "clear_field", "field": "purpose"}],
        },
    )
    assert cleared.status_code == 200
    assert cleared.json()["profile"]["job_title"] == "前端工程師"
    assert cleared.json()["profile"]["purpose"] is None


def command(revision_id: str, value: str = "前端工程師") -> dict:
    return {
        "command_id": str(uuid4()),
        "expected_revision_id": revision_id,
        "changes": [{"action": "set_field", "field": "job_title", "value": value}],
    }


def test_original_result_replayed_after_newer_edit_and_active_turn(client: TestClient) -> None:
    file_id = create_file(client)
    url = f"/api/job-files/{file_id}/jd/profile"
    original = client.get(url).json()
    first_command = command(original["revision_id"])
    first = client.post(url, json=first_command)
    assert first.status_code == 200
    second = client.post(url, json=command(first.json()["revision_id"], "維護工程師"))
    assert second.status_code == 200
    accepted = client.post(
        f"/api/job-files/{file_id}/inputs", json={"command_id": str(uuid4()), "text": "目前工作"}
    )
    assert accepted.status_code == 202
    assert client.post(url, json=first_command).json() == first.json()
    assert client.get(url).json() == second.json()


def test_stale_new_command_and_changed_replay_payload_are_rejected(client: TestClient) -> None:
    file_id = create_file(client)
    url = f"/api/job-files/{file_id}/jd/profile"
    original = client.get(url).json()
    first_command = command(original["revision_id"])
    first = client.post(url, json=first_command)
    assert first.status_code == 200
    stale = client.post(url, json=command(original["revision_id"], "舊基準修改"))
    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "jd_revision_stale"
    for changed in (
        {"expected_revision_id": first.json()["revision_id"]},
        {"changes": [{"action": "clear_field", "field": "job_title"}]},
    ):
        conflict = client.post(url, json={**first_command, **changed})
        assert conflict.status_code == 409
        assert conflict.json()["detail"]["code"] == "jd_command_conflict"
    assert client.get(url).json() == first.json()


@pytest.mark.parametrize(
    "invalid_change",
    [
        {"action": "set_field", "field": "employee_name", "value": "不改姓名"},
        {"action": "set_field", "field": "display_name", "value": "不改檔案"},
        {"action": "clear_field", "field": "job_title"},  # Duplicates the valid first change.
        {"action": "set_field", "field": "purpose", "value": ""},
        {"action": "set_field", "field": "purpose", "value": " \n\t"},
        {"action": "set_field", "field": "purpose", "value": "\u3000"},
        {"action": "set_field", "field": "purpose", "value": "abc\x00"},
        {"action": "set_field", "field": "purpose", "value": None},
        {"action": "set_field", "field": "purpose", "value": 7},
        {"action": "clear_field", "field": "purpose", "value": "unexpected"},
        {"action": "clear_field", "field": "purpose", "path": "other_field"},
    ],
)
def test_invalid_later_change_does_not_leave_first_change(
    client: TestClient, database_connection: psycopg.Connection, invalid_change: dict
) -> None:
    file_id = create_file(client)
    url = f"/api/job-files/{file_id}/jd/profile"
    original = client.get(url).json()
    request = command(original["revision_id"])
    request["changes"].append(invalid_change)
    assert client.post(url, json=request).status_code == 422
    assert client.get(url).json() == original
    assert database_connection.execute("SELECT count(*) FROM jd_operations").fetchone() == (0,)
    assert database_connection.execute("SELECT count(*) FROM jd_revisions").fetchone() == (1,)


def test_empty_changes_are_not_an_implicit_clear(client: TestClient) -> None:
    file_id = create_file(client)
    url = f"/api/job-files/{file_id}/jd/profile"
    original = client.get(url).json()
    request = {**command(original["revision_id"]), "changes": []}
    assert client.post(url, json=request).status_code == 422
    assert client.get(url).json() == original


def test_same_value_reuses_revision_but_changed_back_creates_new_one(
    client: TestClient, database_connection: psycopg.Connection
) -> None:
    file_id = create_file(client)
    url = f"/api/job-files/{file_id}/jd/profile"
    empty = client.get(url).json()
    first = client.post(url, json=command(empty["revision_id"])).json()
    noop = client.post(url, json=command(first["revision_id"]))
    assert noop.status_code == 200
    assert noop.json() == first
    other = client.post(url, json=command(first["revision_id"], "維護工程師")).json()
    restored = client.post(url, json=command(other["revision_id"]))
    assert restored.status_code == 200
    assert restored.json()["profile"] == first["profile"]
    assert restored.json()["revision_id"] != first["revision_id"]
    assert database_connection.execute("SELECT count(*) FROM jd_revisions").fetchone() == (4,)
    assert database_connection.execute("SELECT count(*) FROM jd_operations").fetchone() == (4,)


def test_same_base_competing_edits_have_one_winner(client: TestClient) -> None:
    file_id = create_file(client)
    url = f"/api/job-files/{file_id}/jd/profile"
    original = client.get(url).json()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda value: client.post(url, json=command(original["revision_id"], value)),
                ["甲", "乙"],
            )
        )
    assert sorted(response.status_code for response in results) == [200, 409]
    winner = next(response for response in results if response.status_code == 200)
    assert client.get(url).json() == winner.json()


def test_eight_parallel_resends_have_one_effect(
    client: TestClient, database_connection: psycopg.Connection
) -> None:
    file_id = create_file(client)
    url = f"/api/job-files/{file_id}/jd/profile"
    request = command(client.get(url).json()["revision_id"])
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: client.post(url, json=request), range(8)))
    assert all(response.status_code == 200 for response in results)
    assert all(response.json() == results[0].json() for response in results)
    assert database_connection.execute("SELECT count(*) FROM jd_operations").fetchone() == (1,)
    assert database_connection.execute("SELECT count(*) FROM jd_revisions").fetchone() == (2,)


@pytest.mark.parametrize("paused", [False, True])
def test_active_or_paused_consultant_blocks_manual_write_but_not_reads_or_other_file(
    client: TestClient, paused: bool
) -> None:
    file_id = create_file(client)
    url = f"/api/job-files/{file_id}/jd/profile"
    original = client.get(url).json()
    accepted = client.post(
        f"/api/job-files/{file_id}/inputs", json={"command_id": str(uuid4()), "text": "目前工作"}
    ).json()
    if paused:

        async def pause() -> None:
            scope = ExecutionScope(
                UUID(file_id), UUID(accepted["execution_id"]), ExecutionKind.CONSULTANT_TURN
            )
            async with client.app.state.database.sessions.begin() as session:
                writer = await executions.claim_writer(session, scope, writer_id=uuid4())
                await executions.pause_execution(session, writer)

        client.portal.call(pause)
    rejected = client.post(url, json=command(original["revision_id"]))
    assert rejected.status_code == 409
    assert rejected.json()["detail"]["code"] == "consultant_turn_active"
    assert client.get(url).json() == original
    other_url = f"/api/job-files/{create_file(client)}/jd/profile"
    assert (
        client.post(
            other_url, json=command(client.get(other_url).json()["revision_id"])
        ).status_code
        == 200
    )


def test_revision_result_and_head_rollback_together(
    client: TestClient, database_connection: psycopg.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    revise = service.revise_profile

    async def fail_after_write(
        session: AsyncSession, job_file_id: UUID, request: ReviseJdProfile
    ) -> None:
        await revise(session, job_file_id, request)
        raise RuntimeError("Injected after JD writes")

    file_id = create_file(client)
    url = f"/api/job-files/{file_id}/jd/profile"
    original = client.get(url).json()
    request = command(original["revision_id"])
    with monkeypatch.context() as patch:
        patch.setattr(service, "revise_profile", fail_after_write)
        with pytest.raises(RuntimeError, match="Injected"):
            client.post(url, json=request)
    assert client.get(url).json() == original
    assert database_connection.execute("SELECT count(*) FROM jd_operations").fetchone() == (0,)
    assert database_connection.execute("SELECT count(*) FROM jd_revisions").fetchone() == (1,)
    assert client.post(url, json=request).status_code == 200


def test_initial_jd_and_opening_share_creation_transaction(
    client: TestClient, database_connection: psycopg.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    create = service.create_empty_jd

    async def fail_after_initial_jd(session: AsyncSession, job_file_id: UUID) -> None:
        await create(session, job_file_id)
        raise RuntimeError("Injected after empty JD")

    monkeypatch.setattr(service, "create_empty_jd", fail_after_initial_jd)
    with pytest.raises(RuntimeError, match="Injected"):
        create_file(client)
    for table in (
        "job_files",
        "interview_texts",
        "formal_interviews",
        "job_descriptions",
        "jd_revisions",
    ):
        assert database_connection.execute(
            psycopg.sql.SQL("SELECT count(*) FROM {}").format(psycopg.sql.Identifier(table))
        ).fetchone() == (0,)


def test_history_is_fixed_and_cross_file_heads_cannot_be_substituted(
    client: TestClient, database_connection: psycopg.Connection
) -> None:
    file_id = create_file(client)
    url = f"/api/job-files/{file_id}/jd/profile"
    original = client.get(url).json()
    assert client.post(url, json=command(original["revision_id"])).status_code == 200
    assert database_connection.execute(
        "SELECT job_title FROM jd_revisions WHERE job_file_id = %s AND revision_id = %s",
        (file_id, original["revision_id"]),
    ).fetchone() == (None,)
    for statement in (
        "UPDATE jd_revisions SET purpose = 'rewritten'",
        "DELETE FROM jd_revisions",
        "UPDATE jd_operations SET kind = 'revise_profile'",
        "DELETE FROM jd_operations",
        "UPDATE job_descriptions SET initial_revision_id = current_revision_id",
    ):
        with pytest.raises(psycopg.errors.CheckViolation):
            database_connection.execute(statement)
    other = create_file(client)
    other_revision = client.get(f"/api/job-files/{other}/jd/profile").json()["revision_id"]
    rejected = client.post(url, json=command(other_revision))
    assert rejected.status_code == 409
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        database_connection.execute(
            "UPDATE job_descriptions SET current_revision_id = %s WHERE job_file_id = %s",
            (other_revision, file_id),
        )


def test_missing_file_has_no_implicit_jd_creation(client: TestClient) -> None:
    url = f"/api/job-files/{uuid4()}/jd/profile"
    assert client.get(url).status_code == 404
    assert client.post(url, json=command(str(uuid4()))).status_code == 404


def test_creation_replay_never_resets_an_edited_jd(
    client: TestClient, database_connection: psycopg.Connection
) -> None:
    request = {"command_id": str(uuid4()), "display_name": "合成職務", "employee_name": "合成員工"}
    created = client.post("/api/job-files", json=request)
    assert created.status_code == 201
    url = f"/api/job-files/{created.json()['job_file_id']}/jd/profile"
    first = client.get(url).json()
    edited = client.post(url, json=command(first["revision_id"]))
    assert edited.status_code == 200
    replayed = client.post("/api/job-files", json=request)
    assert replayed.status_code == 200
    assert replayed.json() == created.json()
    assert client.get(url).json() == edited.json()
    assert database_connection.execute("SELECT count(*) FROM job_descriptions").fetchone() == (1,)
    assert database_connection.execute("SELECT count(*) FROM jd_revisions").fetchone() == (2,)


def test_background_memory_does_not_block_manual_jd(client: TestClient) -> None:
    file_id = create_file(client)
    url = f"/api/job-files/{file_id}/jd/profile"

    async def start_memory() -> None:
        async with client.app.state.database.sessions.begin() as session:
            await executions.admit_execution(
                session, ExecutionScope(UUID(file_id), uuid4(), ExecutionKind.MEMORY_BATCH)
            )

    client.portal.call(start_memory)
    original = client.get(url).json()
    edited = client.post(url, json=command(original["revision_id"]))
    assert edited.status_code == 200
    assert client.get(url).json() == edited.json()
