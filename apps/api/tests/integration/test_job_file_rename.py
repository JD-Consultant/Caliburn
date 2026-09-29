"""Renames are scoped, freshness-checked commands, not repeated unconditional writes."""

from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.features.job_files import service
from caliburn.features.job_files.models import RenameJobFile

pytestmark = pytest.mark.postgres


def create_file(client: TestClient, name: str = "原名稱") -> dict:
    return client.post(
        "/api/job-files",
        json={"command_id": str(uuid4()), "display_name": name, "employee_name": "測試員工"},
    ).json()


def rename_command(name: str, revision: int = 1) -> dict:
    return {
        "command_id": str(uuid4()),
        "display_name": name,
        "expected_name_revision": revision,
    }


def test_rename_only_changes_label_and_preserves_original_creation(client: TestClient) -> None:
    creation = {"command_id": str(uuid4()), "display_name": "原名稱", "employee_name": "員工"}
    original = client.post("/api/job-files", json=creation).json()
    url = f"/api/job-files/{original['job_file_id']}"
    history = client.get(f"{url}/interviews").json()
    other = create_file(client, "新名稱")
    response = client.post(f"{url}/rename", json=rename_command("新名稱"))
    assert response.status_code == 200
    assert response.json() == {**original, "display_name": "新名稱", "name_revision": 2}
    assert client.get(url).json() == response.json()
    assert client.get(f"{url}/interviews").json() == history
    assert client.get(f"/api/job-files/{other['job_file_id']}").json() == other
    assert client.post("/api/job-files", json=creation).json() == original


def test_replaying_old_rename_returns_original_result_without_overwriting_newer_name(
    client: TestClient,
) -> None:
    file = create_file(client)
    url = f"/api/job-files/{file['job_file_id']}"
    first_command = rename_command("第一次改名")
    first = client.post(f"{url}/rename", json=first_command)
    assert first.status_code == 200
    second = client.post(f"{url}/rename", json=rename_command("第二次改名", 2))
    assert second.status_code == 200
    assert client.post(f"{url}/rename", json=first_command).json() == first.json()
    assert client.get(url).json() == second.json()


def test_old_revision_rejected_even_if_name_was_changed_back(client: TestClient) -> None:
    file = create_file(client)
    url = f"/api/job-files/{file['job_file_id']}/rename"
    assert client.post(url, json=rename_command("別的名稱")).status_code == 200
    assert client.post(url, json=rename_command("原名稱", 2)).status_code == 200
    stale = client.post(url, json=rename_command("舊分頁寫入"))
    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "stale_job_file_name"


def test_same_name_is_acknowledged_without_new_revision(client: TestClient) -> None:
    file = create_file(client)
    response = client.post(
        f"/api/job-files/{file['job_file_id']}/rename", json=rename_command("原名稱")
    )
    assert response.status_code == 200
    assert response.json() == file


def test_original_rename_command_cannot_be_reused_with_new_payload(client: TestClient) -> None:
    file = create_file(client)
    url = f"/api/job-files/{file['job_file_id']}/rename"
    command = rename_command("名稱甲")
    assert client.post(url, json=command).status_code == 200
    for change in ({"display_name": "名稱乙"}, {"expected_name_revision": 2}):
        response = client.post(url, json={**command, **change})
        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "rename_command_conflict"


def test_parallel_renames_from_same_base_have_one_winner(client: TestClient) -> None:
    file = create_file(client)
    url = f"/api/job-files/{file['job_file_id']}/rename"
    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(
            executor.map(lambda name: client.post(url, json=rename_command(name)), ["甲", "乙"])
        )
    assert sorted(response.status_code for response in responses) == [200, 409]
    winner = next(response for response in responses if response.status_code == 200)
    assert client.get(f"/api/job-files/{file['job_file_id']}").json() == winner.json()


def test_parallel_resends_keep_one_rename_result(
    client: TestClient,
    database_connection: psycopg.Connection,
) -> None:
    file = create_file(client)
    url = f"/api/job-files/{file['job_file_id']}/rename"
    command = rename_command("只改一次")
    with ThreadPoolExecutor(max_workers=4) as executor:
        responses = list(executor.map(lambda _: client.post(url, json=command), range(8)))
    assert all(response.status_code == 200 for response in responses)
    assert all(response.json() == responses[0].json() for response in responses)
    assert responses[0].json()["name_revision"] == 2
    assert database_connection.execute("SELECT count(*) FROM job_file_renames").fetchone() == (1,)


@pytest.mark.parametrize("value", ["", "  ", "\u3000", "\x00", "長" * 201, None, 7])
def test_invalid_rename_cannot_modify_file(client: TestClient, value: object) -> None:
    file = create_file(client)
    url = f"/api/job-files/{file['job_file_id']}"
    response = client.post(f"{url}/rename", json={**rename_command(""), "display_name": value})
    assert response.status_code == 422
    assert client.get(url).json() == file


def test_missing_file_returns_not_found_and_same_command_is_scoped_to_file(
    client: TestClient,
) -> None:
    command = rename_command("共用名稱")
    assert client.post(f"/api/job-files/{uuid4()}/rename", json=command).status_code == 404
    for _ in range(2):
        file = create_file(client)
        result = client.post(f"/api/job-files/{file['job_file_id']}/rename", json=command)
        assert result.status_code == 200
        assert result.json()["job_file_id"] == file["job_file_id"]


def test_rename_and_result_rollback_together(
    client: TestClient,
    database_connection: psycopg.Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Inject after the owner has applied all changes but before the workflow commits.
    rename = service.rename_job_file

    async def fail_after_rename(
        session: AsyncSession, job_file_id: UUID, command: RenameJobFile
    ) -> None:
        await rename(session, job_file_id, command)
        raise RuntimeError("Injected precommit failure")

    file = create_file(client)
    url = f"/api/job-files/{file['job_file_id']}"
    command = rename_command("新名稱")
    with monkeypatch.context() as patch:
        patch.setattr(service, "rename_job_file", fail_after_rename)
        with pytest.raises(RuntimeError, match="Injected"):
            client.post(f"{url}/rename", json=command)
    assert client.get(url).json() == file
    assert database_connection.execute("SELECT count(*) FROM job_file_renames").fetchone() == (0,)
    assert client.post(f"{url}/rename", json=command).status_code == 200


def test_database_keeps_name_counter_and_original_results_authoritative(
    client: TestClient,
    database_connection: psycopg.Connection,
) -> None:
    file = create_file(client)
    url = f"/api/job-files/{file['job_file_id']}"
    response = client.post(f"{url}/rename", json=rename_command("更新名稱"))
    assert response.status_code == 200
    for statement in (
        "UPDATE job_file_renames SET display_name = 'rewritten'",
        "DELETE FROM job_file_renames",
    ):
        with pytest.raises(psycopg.errors.CheckViolation):
            database_connection.execute(statement)
    database_connection.execute(
        "UPDATE job_files SET name_revision = 1 WHERE job_file_id = %s", (file["job_file_id"],)
    )
    assert client.get(url).json()["name_revision"] == 2


@pytest.mark.parametrize("revision", [0, -1, "1", True, None, 9007199254740992])
def test_invalid_freshness_does_not_bypass_the_check(client: TestClient, revision: object) -> None:
    file = create_file(client)
    url = f"/api/job-files/{file['job_file_id']}"
    response = client.post(
        f"{url}/rename", json={**rename_command("新名稱"), "expected_name_revision": revision}
    )
    assert response.status_code == 422
    assert client.get(url).json() == file
