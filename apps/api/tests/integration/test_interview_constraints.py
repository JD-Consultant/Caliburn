"""Database safety for immutable originals and file-bound formal identities."""

from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.postgres


@pytest.fixture
def first_file(client: TestClient) -> dict[str, object]:
    return client.post(
        "/api/job-files",
        json={"command_id": str(uuid4()), "display_name": "檔案", "employee_name": "員工"},
    ).json()


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE interview_texts SET interview_text = 'changed'",
        "DELETE FROM interview_texts",
        "UPDATE formal_interviews SET interview_sequence = 2",
        "DELETE FROM formal_interviews",
        "UPDATE job_files SET initial_display_name = 'changed'",
    ],
)
def test_originals_and_formal_identity_cannot_be_rewritten(
    first_file: dict[str, object], database_connection: psycopg.Connection, statement: str
) -> None:
    with pytest.raises(psycopg.errors.CheckViolation):
        database_connection.execute(statement)
    assert database_connection.execute("SELECT count(*) FROM formal_interviews").fetchone() == (1,)


def test_formal_source_cannot_point_to_another_job_file(
    client: TestClient, first_file: dict[str, object], database_connection: psycopg.Connection
) -> None:
    other_file = client.post(
        "/api/job-files",
        json={"command_id": str(uuid4()), "display_name": "另一檔案", "employee_name": "員工"},
    ).json()
    source_id = uuid4()
    database_connection.execute(
        "INSERT INTO interview_texts VALUES (%s, %s, 'employee', 'source')",
        (source_id, first_file["job_file_id"]),
    )
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        database_connection.execute(
            "INSERT INTO formal_interviews VALUES (%s, 2, %s)",
            (other_file["job_file_id"], source_id),
        )
