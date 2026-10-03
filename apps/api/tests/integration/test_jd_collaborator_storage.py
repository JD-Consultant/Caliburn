"""Fixed collaborator selections are relationally scoped and cannot be rewritten after adoption."""

from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.postgres


def create_file_with_collaborator(client: TestClient) -> tuple[str, dict]:
    created = client.post(
        "/api/job-files",
        json={
            "command_id": str(uuid4()),
            "display_name": "合成資料約束",
            "employee_name": "合成人物",
        },
    )
    assert created.status_code == 201
    file_id = created.json()["job_file_id"]
    url = f"/api/job-files/{file_id}/jd/collaborators"
    result = client.post(
        url,
        json={
            "command_id": str(uuid4()),
            "expected_revision_id": client.get(url).json()["revision_id"],
            "change": {"action": "create_collaborator", "name": "交付", "scope_text": None},
        },
    )
    assert result.status_code == 200
    return file_id, result.json()


def test_fixed_content_and_selection_cannot_be_updated_deleted_or_appended(
    client: TestClient, database_connection: psycopg.Connection
) -> None:
    file_id, result = create_file_with_collaborator(client)
    # Advance the head so the test also exercises protection of past adopted results.
    assert (
        client.post(
            f"/api/job-files/{file_id}/jd/profile",
            json={
                "command_id": str(uuid4()),
                "expected_revision_id": result["revision_id"],
                "changes": [{"action": "set_field", "field": "job_title", "value": "工程師"}],
            },
        ).status_code
        == 200
    )
    for statement in (
        "UPDATE jd_collaborator_revisions SET name = 'rewritten'",
        "DELETE FROM jd_collaborator_revisions",
        "UPDATE jd_collaborator_selections SET position = 99",
        "DELETE FROM jd_collaborator_selections",
    ):
        with pytest.raises(psycopg.errors.CheckViolation):
            database_connection.execute(statement)
    for revision_id in (
        result["revision_id"],
        database_connection.execute(
            "SELECT initial_revision_id FROM job_descriptions WHERE job_file_id = %s",
            (file_id,),
        ).fetchone()[0],
    ):
        with pytest.raises(psycopg.errors.CheckViolation, match="Cannot append"):
            database_connection.execute(
                "INSERT INTO jd_collaborator_selections "
                "(job_file_id, revision_id, collaborator_id, content_revision_id, position) "
                "SELECT job_file_id, %s, collaborator_id, content_revision_id, 1 "
                "FROM jd_collaborator_revisions",
                (revision_id,),
            )


def test_selection_constraints_reject_foreign_content_and_duplicate_identity_or_position(
    client: TestClient, database_connection: psycopg.Connection
) -> None:
    first_id, first = create_file_with_collaborator(client)
    second_id, second = create_file_with_collaborator(client)
    revision_id = uuid4()
    # Deliberately unadopted revision isolates FK/unique checks from the adoption guard.
    database_connection.execute(
        "INSERT INTO jd_revisions (job_file_id, revision_id, parent_revision_id) VALUES (%s,%s,%s)",
        (first_id, revision_id, first["revision_id"]),
    )
    insert_selection = (
        "INSERT INTO jd_collaborator_selections "
        "(job_file_id, revision_id, collaborator_id, content_revision_id, position) "
        "VALUES (%s,%s,%s,%s,%s)"
    )
    second_content = database_connection.execute(
        "SELECT content_revision_id FROM jd_collaborator_revisions WHERE job_file_id = %s",
        (second_id,),
    ).fetchone()[0]
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        database_connection.execute(
            insert_selection,
            (
                first_id,
                revision_id,
                second["collaborators"][0]["collaborator_id"],
                second_content,
                0,
            ),
        )
    first_collaborator = first["collaborators"][0]["collaborator_id"]
    first_content = database_connection.execute(
        "SELECT content_revision_id FROM jd_collaborator_revisions WHERE job_file_id = %s",
        (first_id,),
    ).fetchone()[0]
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        database_connection.execute(
            insert_selection,
            (
                first_id,
                second["revision_id"],
                first_collaborator,
                first_content,
                0,
            ),
        )
    with pytest.raises(psycopg.errors.CheckViolation):
        database_connection.execute(
            insert_selection,
            (
                first_id,
                revision_id,
                first_collaborator,
                first_content,
                -1,
            ),
        )
    database_connection.execute(
        insert_selection,
        (
            first_id,
            revision_id,
            first_collaborator,
            first_content,
            0,
        ),
    )
    revised_content = uuid4()
    database_connection.execute(
        "INSERT INTO jd_collaborator_revisions "
        "(job_file_id,collaborator_id,content_revision_id,name) "
        "VALUES (%s,%s,%s,'new content')",
        (first_id, first_collaborator, revised_content),
    )
    with pytest.raises(psycopg.errors.UniqueViolation):
        database_connection.execute(
            insert_selection,
            (
                first_id,
                revision_id,
                first_collaborator,
                revised_content,
                1,
            ),
        )
    other_collaborator, other_content = uuid4(), uuid4()
    database_connection.execute(
        "INSERT INTO jd_collaborator_revisions "
        "(job_file_id,collaborator_id,content_revision_id,name) "
        "VALUES (%s,%s,%s,'other group')",
        (first_id, other_collaborator, other_content),
    )
    with pytest.raises(psycopg.errors.UniqueViolation):
        database_connection.execute(
            insert_selection,
            (
                first_id,
                revision_id,
                other_collaborator,
                other_content,
                0,
            ),
        )
