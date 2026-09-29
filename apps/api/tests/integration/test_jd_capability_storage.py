"""PostgreSQL keeps fixed capability content, membership and task relations aligned."""

from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.postgres


def create_linked_capability(client: TestClient) -> tuple[str, dict]:
    created = client.post(
        "/api/job-files",
        json={"command_id": str(uuid4()), "display_name": "合成保存", "employee_name": "合成人"},
    )
    assert created.status_code == 201
    file_id = created.json()["job_file_id"]
    url = f"/api/job-files/{file_id}/jd"
    base = client.get(f"{url}/capabilities").json()
    response = client.post(
        f"{url}/capabilities",
        json={
            "command_id": str(uuid4()),
            "expected_revision_id": base["revision_id"],
            "change": {
                "action": "create_capability",
                "kind": "knowledge",
                "name": "資料介面",
                "description": None,
            },
        },
    )
    assert response.status_code == 200
    capability_id = response.json()["capabilities"][0]["capability_id"]
    task = client.post(
        f"{url}/tasks",
        json={
            "command_id": str(uuid4()),
            "expected_revision_id": response.json()["revision_id"],
            "change": {
                "action": "create_task",
                "area_id": None,
                "title": "串接",
                "description": None,
                "outcomes": [],
                "requirements": [],
            },
        },
    )
    assert task.status_code == 200
    linked = client.post(
        f"{url}/capabilities",
        json={
            "command_id": str(uuid4()),
            "expected_revision_id": task.json()["revision_id"],
            "change": {
                "action": "set_task_capability",
                "task_id": task.json()["tasks"][0]["task_id"],
                "capability_id": capability_id,
                "linked": True,
            },
        },
    )
    assert linked.status_code == 200
    return file_id, linked.json()


def test_fixed_history_cannot_change_or_gain_late_members(
    client: TestClient,
    database_connection: psycopg.Connection,
) -> None:
    file_id, original = create_linked_capability(client)
    later = client.post(
        f"/api/job-files/{file_id}/jd/profile",
        json={
            "command_id": str(uuid4()),
            "expected_revision_id": original["revision_id"],
            "changes": [{"action": "set_field", "field": "job_title", "value": "工程師"}],
        },
    )
    assert later.status_code == 200
    for table in ("jd_capability_revisions", "jd_capability_selections", "jd_task_capabilities"):
        for operation in ("UPDATE {} SET job_file_id=job_file_id", "DELETE FROM {}"):
            with pytest.raises(psycopg.errors.CheckViolation):
                database_connection.execute(
                    psycopg.sql.SQL(operation).format(psycopg.sql.Identifier(table))
                )
    for revision_id in (original["revision_id"], later.json()["revision_id"]):
        for table, columns in (
            ("jd_capability_selections", "capability_id,content_revision_id,position"),
            ("jd_task_capabilities", "task_id,capability_id,position"),
        ):
            with pytest.raises(psycopg.errors.CheckViolation, match="Cannot append"):
                database_connection.execute(
                    psycopg.sql.SQL(
                        "INSERT INTO {table} (job_file_id,revision_id,{columns}) "
                        "SELECT job_file_id,%s,{columns} FROM {table} LIMIT 1"
                    ).format(table=psycopg.sql.Identifier(table), columns=psycopg.sql.SQL(columns)),
                    (revision_id,),
                )


def test_relation_requires_members_in_same_file_and_revision(
    client: TestClient,
    database_connection: psycopg.Connection,
) -> None:
    file_id, original = create_linked_capability(client)
    foreign_id, foreign = create_linked_capability(client)
    revision_id = uuid4()
    database_connection.execute(
        "INSERT INTO jd_revisions (job_file_id,revision_id,parent_revision_id) VALUES (%s,%s,%s)",
        (file_id, revision_id, original["revision_id"]),
    )
    task_id = original["task_links"][0]["task_id"]
    capability_id = original["capabilities"][0]["capability_id"]
    statement = (
        "INSERT INTO jd_task_capabilities "
        "(job_file_id,revision_id,task_id,capability_id,position) VALUES (%s,%s,%s,%s,%s)"
    )
    # Merely existing in an older document is insufficient.
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        database_connection.execute(statement, (file_id, revision_id, task_id, capability_id, 0))
    database_connection.execute(
        "INSERT INTO jd_task_selections "
        "(job_file_id,revision_id,task_id,content_revision_id,area_id,position) "
        "SELECT job_file_id,%s,task_id,content_revision_id,area_id,position "
        "FROM jd_task_selections WHERE job_file_id=%s AND revision_id=%s",
        (revision_id, file_id, original["revision_id"]),
    )
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        database_connection.execute(statement, (file_id, revision_id, task_id, capability_id, 0))
    database_connection.execute(
        "INSERT INTO jd_capability_selections "
        "(job_file_id,revision_id,capability_id,content_revision_id,position) "
        "SELECT job_file_id,%s,capability_id,content_revision_id,position "
        "FROM jd_capability_selections WHERE job_file_id=%s AND revision_id=%s",
        (revision_id, file_id, original["revision_id"]),
    )
    database_connection.execute(statement, (file_id, revision_id, task_id, capability_id, 0))
    with pytest.raises(psycopg.errors.UniqueViolation):
        database_connection.execute(statement, (file_id, revision_id, task_id, capability_id, 1))
    with pytest.raises(psycopg.errors.CheckViolation):
        database_connection.execute(statement, (file_id, revision_id, task_id, capability_id, -1))
    for file_value, task_value, capability_value in (
        (file_id, foreign["task_links"][0]["task_id"], capability_id),
        (file_id, task_id, foreign["capabilities"][0]["capability_id"]),
        (foreign_id, task_id, capability_id),
    ):
        with pytest.raises(psycopg.errors.ForeignKeyViolation):
            database_connection.execute(
                statement, (file_value, revision_id, task_value, capability_value, 1)
            )
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        database_connection.execute(
            "INSERT INTO jd_capability_selections "
            "(job_file_id,revision_id,capability_id,content_revision_id,position) "
            "SELECT %s,%s,capability_id,content_revision_id,1 "
            "FROM jd_capability_revisions WHERE job_file_id=%s",
            (file_id, revision_id, foreign_id),
        )
