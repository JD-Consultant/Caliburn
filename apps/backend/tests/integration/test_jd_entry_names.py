"""名稱清洗、顯示大小寫與快照沿正式 HTTP／PostgreSQL 驗證。"""

from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select

from caliburn.host.app import build_app
from caliburn.modules.job_description.infrastructure.persistence.orm_models import (
    DutyRow,
    JobTaskRow,
    KnowledgeRow,
    SkillRow,
)
from tests.reference_configuration import HOST_REFERENCE_CONFIGURATION


@pytest.mark.parametrize("collection", ["duties", "tasks", "knowledge", "skills"])
def test_name_length_boundary_roundtrips_through_http_and_history(
    pg_engine: Engine, jd_workspace_id: UUID, collection: str
) -> None:
    """四類名稱去外圍空白後255字可保存與查版，256字拒絕不增版。"""
    app = build_app(
        reference_configuration=HOST_REFERENCE_CONFIGURATION,
        database_url=pg_engine.url.render_as_string(hide_password=False),
    )
    name = "😀" * 255
    with TestClient(app) as client:
        created = client.post(f"/workspaces/{jd_workspace_id}/job-description", json={})
        assert created.status_code == 201, created.text
        url = created.headers["Location"]
        added = client.post(
            url + f"/{collection}",
            json={"expected_version": 1, "name": "\u001c " + name + "\u3000\n"},
        )
        assert added.status_code == 201, added.text
        assert added.json()[collection][0]["name"] == name
        rejected = client.patch(
            url + f"/{collection}/{added.json()[collection][0]['id']}",
            json={"expected_version": 2, "name": name + "界"},
        )
        assert rejected.status_code == 422, rejected.text
        assert client.get(url).json() == added.json()
        assert (
            client.get(url + "/history/2").json()["content"][collection][0]["name"]
            == name
        )


@pytest.mark.parametrize(
    "collection,row_type",
    [
        ("duties", DutyRow),
        ("tasks", JobTaskRow),
        ("knowledge", KnowledgeRow),
        ("skills", SkillRow),
    ],
)
def test_name_values_roundtrip_and_case_edit_gets_its_own_version(
    pg_engine: Engine,
    jd_workspace_id: UUID,
    collection: str,
    row_type: type[DutyRow | JobTaskRow | KnowledgeRow | SkillRow],
) -> None:
    """大小寫不同可共存；同名拒絕且清洗、改名與歷史恢復一致。"""
    app = build_app(
        reference_configuration=HOST_REFERENCE_CONFIGURATION,
        database_url=pg_engine.url.render_as_string(hide_password=False),
    )
    with TestClient(app) as client:
        created = client.post(f"/workspaces/{jd_workspace_id}/job-description", json={})
        assert created.status_code == 201, created.text
        url = created.headers["Location"]
        added = client.post(
            url + f"/{collection}", json={"expected_version": 1, "name": " SQL "}
        )
        assert added.status_code == 201, added.text
        entry = added.json()[collection][0]
        assert entry["name"] == "SQL"
        path = url + f"/{collection}/{entry['id']}"
        with pg_engine.connect() as connection:
            assert connection.scalar(select(row_type.name)) == "SQL"

        unchanged = client.patch(path, json={"expected_version": 2, "name": " \tSQL\n"})
        assert unchanged.status_code == 200, unchanged.text
        assert unchanged.json()["version"] == 2
        renamed = client.patch(path, json={"expected_version": 2, "name": "sql"})
        assert renamed.status_code == 200, renamed.text
        assert renamed.json()["version"] == 3
        assert renamed.json()[collection][0]["name"] == "sql"
        distinct = client.post(
            url + f"/{collection}", json={"expected_version": 3, "name": " SQL "}
        )
        assert distinct.status_code == 201, distinct.text
        assert distinct.json()["version"] == 4
        assert [item["name"] for item in distinct.json()[collection]] == ["sql", "SQL"]
        with pg_engine.connect() as connection:
            assert set(connection.scalars(select(row_type.name))) == {"sql", "SQL"}
        duplicate = client.post(
            url + f"/{collection}", json={"expected_version": 4, "name": " sql "}
        )
        assert duplicate.status_code == 409, duplicate.text
        assert duplicate.json()["detail"]["code"] == "jd_name_conflict"

        history = client.get(url + "/history").json()
        assert len(history["items"]) == 4
        previous = client.get(url + "/history/2").json()
        assert previous["content"][collection][0]["name"] == "SQL"
        restored = client.post(
            url + ":restore", json={"expected_version": 4, "target_version": 2}
        )
        assert restored.status_code == 200, restored.text
        assert restored.json()["version"] == 5
        assert len(restored.json()[collection]) == 1
        assert restored.json()[collection][0] == entry
