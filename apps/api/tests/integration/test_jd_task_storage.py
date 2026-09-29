"""Task snapshots preserve fixed detail groups, file scope and unassigned order."""

from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.postgres


def create_tasks(client: TestClient) -> tuple[str, dict]:
    created = client.post(
        "/api/job-files",
        json={
            "command_id": str(uuid4()),
            "display_name": "合成保存測試",
            "employee_name": "合成人物",
        },
    )
    assert created.status_code == 201
    file_id = created.json()["job_file_id"]
    url = f"/api/job-files/{file_id}/jd/tasks"
    revision_id = client.get(url).json()["revision_id"]
    result = {}
    for title in ("盤點", "回報"):
        response = client.post(
            url,
            json={
                "command_id": str(uuid4()),
                "expected_revision_id": revision_id,
                "change": {
                    "action": "create_task",
                    "area_id": None,
                    "title": title,
                    "description": None,
                    "outcomes": ["核對表"],
                    "requirements": ["記錄差異"],
                },
            },
        )
        assert response.status_code == 200
        result = response.json()
        revision_id = result["revision_id"]
    return file_id, result


def test_task_history_cannot_be_mutated_or_extended_after_adoption(
    client: TestClient,
    database_connection: psycopg.Connection,
) -> None:
    file_id, result = create_tasks(client)
    changed = client.post(
        f"/api/job-files/{file_id}/jd/profile",
        json={
            "command_id": str(uuid4()),
            "expected_revision_id": result["revision_id"],
            "changes": [{"action": "set_field", "field": "job_title", "value": "倉管"}],
        },
    )
    assert changed.status_code == 200
    for statement in (
        "UPDATE jd_task_revisions SET title = 'changed'",
        "DELETE FROM jd_task_revisions",
        "UPDATE jd_task_details SET text = 'changed'",
        "DELETE FROM jd_task_details",
        "UPDATE jd_task_selections SET position = 10",
        "DELETE FROM jd_task_selections",
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
                "INSERT INTO jd_task_selections "
                "(job_file_id,revision_id,task_id,content_revision_id,area_id,position) "
                "SELECT job_file_id,%s,task_id,content_revision_id,NULL,2 "
                "FROM jd_task_revisions LIMIT 1",
                (revision_id,),
            )
    with pytest.raises(psycopg.errors.CheckViolation, match="Cannot append details"):
        database_connection.execute(
            "INSERT INTO jd_task_details "
            "(job_file_id,task_id,content_revision_id,detail_id,kind,text,position) "
            "SELECT job_file_id,task_id,content_revision_id,%s,'outcome','late append',3 "
            "FROM jd_task_revisions LIMIT 1",
            (uuid4(),),
        )


def test_task_selection_constraints_include_unassigned_positions_and_same_revision_area(
    client: TestClient,
    database_connection: psycopg.Connection,
) -> None:
    file_id, result = create_tasks(client)
    other_id, other = create_tasks(client)
    revision_id = uuid4()
    database_connection.execute(
        "INSERT INTO jd_revisions (job_file_id,revision_id,parent_revision_id) VALUES (%s,%s,%s)",
        (file_id, revision_id, result["revision_id"]),
    )
    contents = database_connection.execute(
        "SELECT task_id,content_revision_id FROM jd_task_selections "
        "WHERE job_file_id=%s AND revision_id=%s ORDER BY position",
        (file_id, result["revision_id"]),
    ).fetchall()
    first_task, first_content = contents[0]
    second_task, second_content = contents[1]
    statement = (
        "INSERT INTO jd_task_selections "
        "(job_file_id,revision_id,task_id,content_revision_id,area_id,position) "
        "VALUES (%s,%s,%s,%s,%s,%s)"
    )
    database_connection.execute(
        statement, (file_id, revision_id, first_task, first_content, None, 0)
    )
    with pytest.raises(psycopg.errors.UniqueViolation):
        database_connection.execute(
            statement, (file_id, revision_id, second_task, second_content, None, 0)
        )
    with pytest.raises(psycopg.errors.UniqueViolation):
        database_connection.execute(
            statement, (file_id, revision_id, first_task, first_content, None, 1)
        )
    with pytest.raises(psycopg.errors.CheckViolation):
        database_connection.execute(
            statement, (file_id, revision_id, second_task, second_content, None, -1)
        )
    # Area identity must be selected in this JD revision, not merely exist somewhere in the file.
    area_id, area_content = uuid4(), uuid4()
    database_connection.execute(
        "INSERT INTO jd_area_revisions (job_file_id,area_id,content_revision_id,title) "
        "VALUES (%s,%s,%s,'group')",
        (file_id, area_id, area_content),
    )
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        database_connection.execute(
            statement, (file_id, revision_id, second_task, second_content, area_id, 0)
        )
    database_connection.execute(
        "INSERT INTO jd_area_selections "
        "(job_file_id,revision_id,area_id,content_revision_id,position) VALUES (%s,%s,%s,%s,0)",
        (file_id, revision_id, area_id, area_content),
    )
    database_connection.execute(
        statement, (file_id, revision_id, second_task, second_content, area_id, 0)
    )
    foreign_task, foreign_content = database_connection.execute(
        "SELECT task_id,content_revision_id FROM jd_task_selections "
        "WHERE job_file_id=%s AND revision_id=%s LIMIT 1",
        (other_id, other["revision_id"]),
    ).fetchone()
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        database_connection.execute(
            statement, (file_id, revision_id, foreign_task, foreign_content, None, 2)
        )


def test_task_detail_constraints_reject_ambiguous_order_and_invalid_content(
    client: TestClient,
    database_connection: psycopg.Connection,
) -> None:
    file_id, _ = create_tasks(client)
    task_id, content_id, detail_id = uuid4(), uuid4(), uuid4()
    # Unselected content isolates row constraints from the fixed-content append guard.
    database_connection.execute(
        "INSERT INTO jd_task_revisions (job_file_id,task_id,content_revision_id,title) "
        "VALUES (%s,%s,%s,'task')",
        (file_id, task_id, content_id),
    )
    statement = (
        "INSERT INTO jd_task_details "
        "(job_file_id,task_id,content_revision_id,detail_id,kind,text,position) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s)"
    )
    database_connection.execute(
        statement, (file_id, task_id, content_id, detail_id, "outcome", "成果", 0)
    )
    database_connection.execute(
        statement, (file_id, task_id, content_id, uuid4(), "requirement", "要求", 0)
    )
    with pytest.raises(psycopg.errors.UniqueViolation):
        database_connection.execute(
            statement, (file_id, task_id, content_id, uuid4(), "outcome", "另項", 0)
        )
    with pytest.raises(psycopg.errors.UniqueViolation):
        database_connection.execute(
            statement, (file_id, task_id, content_id, detail_id, "requirement", "改型", 1)
        )
    for kind, text, position in (("unknown", "值", 1), ("outcome", " ", 1), ("outcome", "值", -1)):
        with pytest.raises(psycopg.errors.CheckViolation):
            database_connection.execute(
                statement, (file_id, task_id, content_id, uuid4(), kind, text, position)
            )
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        database_connection.execute(
            statement, (file_id, uuid4(), content_id, uuid4(), "outcome", "錯身分", 0)
        )
