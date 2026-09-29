"""Job-file creation has one durable opening and one result per original command."""

from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.features.interviews import service as interview_service

pytestmark = pytest.mark.postgres


def test_create_and_resend_keeps_one_file_and_one_formal_opening(client: TestClient) -> None:
    payload = {
        "command_id": str(uuid4()),
        "display_name": "產品團隊－前端工作",
        "employee_name": "測試員工",
    }
    first = client.post("/api/job-files", json=payload)
    assert first.status_code == 201
    repeated = client.post("/api/job-files", json=payload)
    assert repeated.status_code == 200
    assert repeated.json() == first.json()
    job_file = first.json()
    assert job_file["display_name"] == payload["display_name"]
    assert client.get("/api/job-files").json() == {"job_files": [job_file]}
    history = client.get(f"/api/job-files/{job_file['job_file_id']}/interviews")
    assert history.status_code == 200
    messages = history.json()["messages"]
    assert len(messages) == 1
    assert messages[0]["interview_sequence"] == 1
    assert messages[0]["speaker"] == "app"
    assert "目前主要負責哪些工作" in messages[0]["interview_text"]


def test_same_names_create_distinct_files_and_isolated_histories(client: TestClient) -> None:
    files = [
        client.post(
            "/api/job-files",
            json={"command_id": str(uuid4()), "display_name": "同名", "employee_name": "同名"},
        ).json()
        for _ in range(2)
    ]
    assert files[0]["job_file_id"] != files[1]["job_file_id"]
    histories = [
        client.get(f"/api/job-files/{file['job_file_id']}/interviews").json()["messages"]
        for file in files
    ]
    assert all(len(history) == 1 for history in histories)
    assert histories[0][0]["source_id"] != histories[1][0]["source_id"]
    assert client.get(f"/api/job-files/{uuid4()}/interviews").status_code == 404


def test_command_reuse_with_changed_payload_is_rejected(client: TestClient) -> None:
    payload = {"command_id": str(uuid4()), "display_name": "檔案 A", "employee_name": "員工 A"}
    first = client.post("/api/job-files", json=payload)
    assert first.status_code == 201
    changed = client.post("/api/job-files", json={**payload, "employee_name": "員工 B"})
    assert changed.status_code == 409
    assert changed.json()["detail"]["code"] == "creation_command_conflict"
    assert client.get("/api/job-files").json() == {"job_files": [first.json()]}


def test_creation_replay_does_not_return_a_later_rename(
    client: TestClient, database_connection: psycopg.Connection
) -> None:
    payload = {"command_id": str(uuid4()), "display_name": "建立時名稱", "employee_name": "員工"}
    original = client.post("/api/job-files", json=payload).json()
    database_connection.execute(
        "UPDATE job_files SET display_name = %s WHERE job_file_id = %s",
        ("後來的名稱", original["job_file_id"]),
    )
    assert client.post("/api/job-files", json=payload).json() == original
    current = client.get(f"/api/job-files/{original['job_file_id']}").json()
    assert current["display_name"] == "後來的名稱"


def test_concurrent_resends_commit_only_one_file_and_opening(client: TestClient) -> None:
    payload = {"command_id": str(uuid4()), "display_name": "同一命令", "employee_name": "員工"}
    with ThreadPoolExecutor(max_workers=4) as executor:
        responses = list(
            executor.map(lambda _: client.post("/api/job-files", json=payload), range(8))
        )
    assert sorted(response.status_code for response in responses) == [200] * 7 + [201]
    assert all(response.json() == responses[0].json() for response in responses)
    assert len(client.get("/api/job-files").json()["job_files"]) == 1
    job_file_id = responses[0].json()["job_file_id"]
    assert len(client.get(f"/api/job-files/{job_file_id}/interviews").json()["messages"]) == 1


def test_opening_failure_rolls_back_file_and_original_text_then_allows_same_command(
    client: TestClient, database_connection: psycopg.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    create_opening = interview_service.create_opening

    async def fail_after_opening(session: AsyncSession, job_file_id: UUID) -> None:
        await create_opening(session, job_file_id)
        raise RuntimeError("Injected failure before commit")

    payload = {"command_id": str(uuid4()), "display_name": "測試失敗", "employee_name": "員工"}
    with monkeypatch.context() as patch:
        patch.setattr(interview_service, "create_opening", fail_after_opening)
        with pytest.raises(RuntimeError, match="Injected failure"):
            client.post("/api/job-files", json=payload)
    assert client.get("/api/job-files").json() == {"job_files": []}
    assert database_connection.execute("SELECT count(*) FROM interview_texts").fetchone() == (0,)
    assert database_connection.execute("SELECT count(*) FROM formal_interviews").fetchone() == (0,)
    assert client.post("/api/job-files", json=payload).status_code == 201


def test_unqualified_originals_never_appear_in_formal_history(
    client: TestClient, database_connection: psycopg.Connection
) -> None:
    job_file_id = client.post(
        "/api/job-files",
        json={"command_id": str(uuid4()), "display_name": "檔案", "employee_name": "員工"},
    ).json()["job_file_id"]
    pending_source_id = uuid4()
    database_connection.execute(
        "INSERT INTO interview_texts VALUES (%s, %s, 'employee', %s)",
        (pending_source_id, job_file_id, "尚未成功完成的輸入"),
    )
    messages = client.get(f"/api/job-files/{job_file_id}/interviews").json()["messages"]
    assert [message["interview_sequence"] for message in messages] == [1]
    assert all(message["source_id"] != str(pending_source_id) for message in messages)


@pytest.mark.parametrize(
    "field_value", ["", "   ", "\n\t", "\u3000", "\u0000", "長" * 201, 42, None]
)
def test_invalid_name_is_rejected_before_creation(client: TestClient, field_value: object) -> None:
    response = client.post(
        "/api/job-files",
        json={"command_id": str(uuid4()), "display_name": field_value, "employee_name": "員工"},
    )
    assert response.status_code == 422
    assert client.get("/api/job-files").json() == {"job_files": []}
