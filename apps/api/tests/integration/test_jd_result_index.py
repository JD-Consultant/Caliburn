"""Result-revision lookups use the same key in fresh DDL and owner metadata."""

import json
from uuid import UUID, uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient

from caliburn.features.job_description.persistence import JdOperationRecord

pytestmark = pytest.mark.postgres


def test_result_lookup_index_is_owned_and_installed(
    database_connection: psycopg.Connection,
) -> None:
    indexes = {
        index.name: tuple(column.name for column in index.columns)
        for index in JdOperationRecord.__table__.indexes
    }
    assert indexes.get("ix_jd_operations_result_revision") == ("job_file_id", "result_revision_id")
    definition = database_connection.execute(
        "SELECT indexdef FROM pg_indexes WHERE schemaname=current_schema() AND indexname=%s",
        ("ix_jd_operations_result_revision",),
    ).fetchone()
    assert definition is not None
    assert "(job_file_id, result_revision_id)" in definition[0]


@pytest.mark.parametrize("history_size", [100, 10000])
def test_result_lookup_has_selective_plan_and_preserves_sealing(
    client: TestClient, database_connection: psycopg.Connection, history_size: int, record_property
) -> None:
    file_id = UUID(
        client.post(
            "/api/job-files",
            json={
                "command_id": str(uuid4()),
                "display_name": "history",
                "employee_name": "synthetic",
            },
        ).json()["job_file_id"]
    )
    initial = database_connection.execute(
        "SELECT current_revision_id FROM job_descriptions WHERE job_file_id=%s", (file_id,)
    ).fetchone()[0]
    database_connection.execute(
        "INSERT INTO jd_revisions(job_file_id,revision_id,parent_revision_id) "
        "SELECT %s,gen_random_uuid(),%s FROM generate_series(1,%s)",
        (file_id, initial, history_size),
    )
    database_connection.execute(
        "INSERT INTO jd_operations(job_file_id,command_id,kind,expected_revision_id,"
        "result_revision_id,request_payload) SELECT job_file_id,gen_random_uuid(),'edit_areas',"
        "%s,revision_id,'{}'::jsonb FROM jd_revisions WHERE job_file_id=%s AND revision_id<>%s",
        (initial, file_id, initial),
    )
    database_connection.execute("ANALYZE jd_operations")
    adopted = database_connection.execute(
        "SELECT result_revision_id FROM jd_operations LIMIT 1"
    ).fetchone()[0]
    for result_id, expected_rows in ((adopted, 1), (uuid4(), 0)):
        plan = database_connection.execute(
            "EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) SELECT 1 FROM jd_operations "
            "WHERE job_file_id=%s AND result_revision_id=%s",
            (file_id, result_id),
        ).fetchone()[0][0]["Plan"]
        assert plan["Actual Rows"] == expected_rows
        record_property(f"lookup_{history_size}_{expected_rows}", json.dumps(plan))
        # Small histories may correctly choose a sequential scan. Large histories must
        # use the selective key instead of inspecting every result in the file.
        if history_size == 10000:
            assert "ix_jd_operations_result_revision" in str(plan)
            assert plan.get("Rows Removed by Filter", 0) < history_size
    area_id, area_revision_id = uuid4(), uuid4()
    database_connection.execute(
        "INSERT INTO jd_area_revisions(job_file_id,area_id,content_revision_id,title) "
        "VALUES (%s,%s,%s,'area')",
        (file_id, area_id, area_revision_id),
    )
    with pytest.raises(psycopg.errors.CheckViolation, match="Cannot append"):
        database_connection.execute(
            "INSERT INTO jd_area_selections"
            "(job_file_id,revision_id,area_id,content_revision_id,position) "
            "VALUES (%s,%s,%s,%s,0)",
            (file_id, adopted, area_id, area_revision_id),
        )
    fresh = uuid4()
    database_connection.execute(
        "INSERT INTO jd_revisions(job_file_id,revision_id,parent_revision_id) VALUES (%s,%s,%s)",
        (file_id, fresh, initial),
    )
    insertion = database_connection.execute(
        "EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) INSERT INTO jd_area_selections"
        "(job_file_id,revision_id,area_id,content_revision_id,position) VALUES (%s,%s,%s,%s,0)",
        (file_id, fresh, area_id, area_revision_id),
    ).fetchone()[0][0]
    record_property(f"assembly_{history_size}", json.dumps(insertion))
    assert database_connection.execute(
        "SELECT area_id FROM jd_area_selections WHERE revision_id=%s", (fresh,)
    ).fetchone() == (area_id,)
