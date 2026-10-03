"""Responsibility groups retain identity, order and history across formal edits."""

from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.features.executions import service as executions
from caliburn.features.executions.models import ExecutionKind, ExecutionScope
from caliburn.features.job_description import area_service
from caliburn.features.job_description.areas import EditJdAreas

pytestmark = pytest.mark.postgres


def create_file(client: TestClient) -> str:
    response = client.post(
        "/api/job-files",
        json={"command_id": str(uuid4()), "display_name": "合成職責", "employee_name": "合成員工"},
    )
    assert response.status_code == 201
    return str(response.json()["job_file_id"])


def edit(client: TestClient, url: str, revision_id: str, change: dict) -> dict:
    response = client.post(
        url,
        json={"command_id": str(uuid4()), "expected_revision_id": revision_id, "change": change},
    )
    assert response.status_code == 200, response.text
    return response.json()


def create_command(revision_id: str, title: str = "網站交付") -> dict:
    return {
        "command_id": str(uuid4()),
        "expected_revision_id": revision_id,
        "change": {"action": "create_area", "title": title, "scope_text": None},
    }


def test_create_and_revise_area_preserves_profile_and_original_identity(client: TestClient) -> None:
    file_id = create_file(client)
    url = f"/api/job-files/{file_id}/jd/areas"
    original = client.get(url)
    assert original.status_code == 200
    assert original.json()["areas"] == []
    created = edit(
        client,
        url,
        original.json()["revision_id"],
        {
            "action": "create_area",
            "title": "網站交付",
            "scope_text": "約定的前端範圍",
        },
    )
    area_id = created["areas"][0]["area_id"]
    profile_url = f"/api/job-files/{file_id}/jd/profile"
    profile = client.post(
        profile_url,
        json={
            "command_id": str(uuid4()),
            "expected_revision_id": created["revision_id"],
            "changes": [{"action": "set_field", "field": "job_title", "value": "前端工程師"}],
        },
    )
    assert profile.status_code == 200
    assert client.get(url).json()["areas"] == created["areas"]
    revised = edit(
        client,
        url,
        profile.json()["revision_id"],
        {
            "action": "revise_area",
            "area_id": area_id,
            "changes": [{"field": "title", "value": "網站前端交付"}],
        },
    )
    assert revised["areas"] == [
        {"area_id": area_id, "title": "網站前端交付", "scope_text": "約定的前端範圍"}
    ]
    assert client.get(profile_url).json()["profile"]["job_title"] == "前端工程師"


def test_order_delete_and_original_results_preserve_fixed_history(
    client: TestClient, database_connection: psycopg.Connection
) -> None:
    file_id = create_file(client)
    url = f"/api/job-files/{file_id}/jd/areas"
    created = client.get(url).json()
    for title in ("交付", "維護", "協作"):
        created = edit(
            client,
            url,
            created["revision_id"],
            {
                "action": "create_area",
                "title": title,
                "scope_text": None,
            },
        )
    first, second, third = created["areas"]
    reordered = edit(
        client,
        url,
        created["revision_id"],
        {
            "action": "reorder_area",
            "area_id": third["area_id"],
            "before_area_id": first["area_id"],
        },
    )
    assert reordered["areas"] == [third, first, second]
    last = edit(
        client,
        url,
        reordered["revision_id"],
        {
            "action": "reorder_area",
            "area_id": third["area_id"],
            "before_area_id": None,
        },
    )
    assert last["areas"] == created["areas"]
    request = {
        "command_id": str(uuid4()),
        "expected_revision_id": last["revision_id"],
        "change": {"action": "delete_area", "area_id": second["area_id"]},
    }
    deleted = client.post(url, json=request)
    assert deleted.status_code == 200
    assert deleted.json()["areas"] == [first, third]
    recreated = edit(
        client,
        url,
        deleted.json()["revision_id"],
        {
            "action": "create_area",
            "title": second["title"],
            "scope_text": None,
        },
    )
    assert recreated["areas"][-1]["area_id"] != second["area_id"]
    assert client.post(url, json=request).json() == deleted.json()
    assert client.get(url).json() == recreated
    assert database_connection.execute("SELECT count(*) FROM jd_area_revisions").fetchone() == (
        4,
    )  # Reorder/delete copy only selection keys, not content.
    historical = database_connection.execute(
        "SELECT area_id FROM jd_area_selections WHERE revision_id = %s ORDER BY position",
        (created["revision_id"],),
    ).fetchall()
    assert [str(row[0]) for row in historical] == [area["area_id"] for area in created["areas"]]


def test_explicit_clear_same_value_and_changed_back_revisions(
    client: TestClient, database_connection: psycopg.Connection
) -> None:
    url = f"/api/job-files/{create_file(client)}/jd/areas"
    initial = edit(
        client,
        url,
        client.get(url).json()["revision_id"],
        {
            "action": "create_area",
            "title": "維護",
            "scope_text": "約定範圍",
        },
    )
    area_id = initial["areas"][0]["area_id"]
    unchanged = edit(
        client,
        url,
        initial["revision_id"],
        {
            "action": "revise_area",
            "area_id": area_id,
            "changes": [{"field": "title", "value": "維護"}],
        },
    )
    assert unchanged == initial
    cleared = edit(
        client,
        url,
        unchanged["revision_id"],
        {
            "action": "revise_area",
            "area_id": area_id,
            "changes": [{"field": "title", "value": None}],
        },
    )
    assert cleared["areas"] == [{"area_id": area_id, "title": None, "scope_text": "約定範圍"}]
    restored = edit(
        client,
        url,
        cleared["revision_id"],
        {
            "action": "revise_area",
            "area_id": area_id,
            "changes": [{"field": "title", "value": "維護"}],
        },
    )
    assert restored["areas"] == initial["areas"]
    assert restored["revision_id"] != initial["revision_id"]
    assert database_connection.execute(
        "SELECT count(DISTINCT content_revision_id) FROM jd_area_revisions"
    ).fetchone() == (3,)
    for before in (None, area_id):
        assert (
            edit(
                client,
                url,
                restored["revision_id"],
                {
                    "action": "reorder_area",
                    "area_id": area_id,
                    "before_area_id": before,
                },
            )
            == restored
        )


@pytest.mark.parametrize(
    "invalid_change",
    [
        {"action": "create_area", "title": None, "scope_text": None},
        {"action": "create_area", "title": "", "scope_text": None},
        {"action": "create_area", "title": " \n\t", "scope_text": None},
        {"action": "create_area", "title": "\u3000", "scope_text": None},
        {"action": "create_area", "title": "a\u0000", "scope_text": None},
        {"action": "create_area", "title": 3, "scope_text": None},
        {"action": "create_area", "title": "交付"},
        {"action": "create_area", "title": "交付", "scope_text": None, "extra": True},
        {"action": "unknown"},
    ],
)
def test_invalid_create_leaves_no_content_or_revision(
    client: TestClient, database_connection: psycopg.Connection, invalid_change: dict
) -> None:
    url = f"/api/job-files/{create_file(client)}/jd/areas"
    original = client.get(url).json()
    request = {**create_command(original["revision_id"]), "change": invalid_change}
    assert client.post(url, json=request).status_code == 422
    assert client.get(url).json() == original
    assert database_connection.execute("SELECT count(*) FROM jd_area_revisions").fetchone() == (0,)
    assert database_connection.execute("SELECT count(*) FROM jd_operations").fetchone() == (0,)
    assert database_connection.execute("SELECT count(*) FROM jd_revisions").fetchone() == (1,)


@pytest.mark.parametrize(
    "changes",
    [
        [],
        [{"field": "title", "value": "新標題"}, {"field": "title", "value": "歧義"}],
        [{"field": "title", "value": "新標題"}, {"field": "scope_text", "value": " "}],
        [{"field": "title", "value": None}, {"field": "scope_text", "value": None}],
        [{"field": "area_id", "value": "替換身分"}],
        [{"field": "scope_text"}],
    ],
)
def test_invalid_update_is_all_or_nothing(
    client: TestClient, database_connection: psycopg.Connection, changes: list[dict]
) -> None:
    url = f"/api/job-files/{create_file(client)}/jd/areas"
    original = client.post(url, json=create_command(client.get(url).json()["revision_id"])).json()
    request = {
        **create_command(original["revision_id"]),
        "change": {
            "action": "revise_area",
            "area_id": original["areas"][0]["area_id"],
            "changes": changes,
        },
    }
    assert client.post(url, json=request).status_code == 422
    assert client.get(url).json() == original
    assert database_connection.execute("SELECT count(*) FROM jd_area_revisions").fetchone() == (1,)
    assert database_connection.execute("SELECT count(*) FROM jd_operations").fetchone() == (1,)


def test_original_result_replayed_after_later_changes_and_active_turn(client: TestClient) -> None:
    file_id = create_file(client)
    url = f"/api/job-files/{file_id}/jd/areas"
    request = create_command(client.get(url).json()["revision_id"])
    first = client.post(url, json=request)
    assert first.status_code == 200
    current = client.post(url, json=create_command(first.json()["revision_id"], "維護"))
    assert current.status_code == 200
    accepted = client.post(
        f"/api/job-files/{file_id}/inputs",
        json={
            "command_id": str(uuid4()),
            "text": "合成訪談",
        },
    )
    assert accepted.status_code == 202
    assert client.post(url, json=request).json() == first.json()
    assert client.get(url).json() == current.json()


def test_commands_share_jd_identity_and_cannot_overwrite_a_newer_base(client: TestClient) -> None:
    file_id = create_file(client)
    url = f"/api/job-files/{file_id}/jd/areas"
    initial = client.get(url).json()
    request = create_command(initial["revision_id"])
    created = client.post(url, json=request)
    assert created.status_code == 200
    stale = client.post(url, json=create_command(initial["revision_id"], "失去更新"))
    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "jd_revision_stale"
    for changed in (
        {"expected_revision_id": created.json()["revision_id"]},
        {"change": {"action": "create_area", "title": "不同內容", "scope_text": None}},
    ):
        conflict = client.post(url, json={**request, **changed})
        assert conflict.status_code == 409
        assert conflict.json()["detail"]["code"] == "jd_command_conflict"
    profile_request = {
        "command_id": request["command_id"],
        "expected_revision_id": initial["revision_id"],
        "changes": [{"action": "set_field", "field": "job_title", "value": "企劃"}],
    }
    assert (
        client.post(f"/api/job-files/{file_id}/jd/profile", json=profile_request).status_code == 409
    )
    assert client.get(url).json() == created.json()


def test_parallel_resends_and_competing_area_edits(
    client: TestClient, database_connection: psycopg.Connection
) -> None:
    url = f"/api/job-files/{create_file(client)}/jd/areas"
    request = create_command(client.get(url).json()["revision_id"])
    with ThreadPoolExecutor(max_workers=4) as pool:
        repeated = list(pool.map(lambda _: client.post(url, json=request), range(8)))
    assert all(response.status_code == 200 for response in repeated)
    assert all(response.json() == repeated[0].json() for response in repeated)
    assert database_connection.execute("SELECT count(*) FROM jd_area_revisions").fetchone() == (1,)
    base = repeated[0].json()["revision_id"]
    with ThreadPoolExecutor(max_workers=2) as pool:
        competing = list(
            pool.map(
                lambda title: client.post(url, json=create_command(base, title)),
                ["甲", "乙"],
            )
        )
    assert sorted(response.status_code for response in competing) == [200, 409]
    assert database_connection.execute("SELECT count(*) FROM jd_operations").fetchone() == (2,)


@pytest.mark.parametrize("paused", [False, True])
def test_manual_area_edit_rejected_during_consultant_but_other_file_can_continue(
    client: TestClient, paused: bool
) -> None:
    file_id = create_file(client)
    url = f"/api/job-files/{file_id}/jd/areas"
    before = client.get(url).json()
    accepted = client.post(
        f"/api/job-files/{file_id}/inputs",
        json={
            "command_id": str(uuid4()),
            "text": "合成訪談",
        },
    ).json()
    if paused:

        async def pause() -> None:
            scope = ExecutionScope(
                UUID(file_id),
                UUID(accepted["execution_id"]),
                ExecutionKind.CONSULTANT_TURN,
            )
            async with client.app.state.database.sessions.begin() as session:
                writer = await executions.claim_writer(session, scope, writer_id=uuid4())
                await executions.pause_execution(session, writer)

        client.portal.call(pause)
    blocked = client.post(url, json=create_command(before["revision_id"]))
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["code"] == "consultant_turn_active"
    assert client.get(url).json() == before
    other_url = f"/api/job-files/{create_file(client)}/jd/areas"
    assert (
        client.post(
            other_url,
            json=create_command(
                client.get(other_url).json()["revision_id"],
            ),
        ).status_code
        == 200
    )


def test_rollback_keeps_head_content_selections_and_operations_together(
    client: TestClient, database_connection: psycopg.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    edit_areas = area_service.edit_areas

    async def fail_after_write(
        session: AsyncSession, job_file_id: UUID, request: EditJdAreas
    ) -> None:
        await edit_areas(session, job_file_id, request)
        raise RuntimeError("Injected before commit")

    url = f"/api/job-files/{create_file(client)}/jd/areas"
    original = client.get(url).json()
    request = create_command(original["revision_id"])
    with monkeypatch.context() as patch:
        patch.setattr(area_service, "edit_areas", fail_after_write)
        with pytest.raises(RuntimeError, match="Injected"):
            client.post(url, json=request)
    assert client.get(url).json() == original
    for table in ("jd_area_revisions", "jd_area_selections", "jd_operations"):
        assert database_connection.execute(
            psycopg.sql.SQL("SELECT count(*) FROM {}").format(
                psycopg.sql.Identifier(table),
            )
        ).fetchone() == (0,)
    assert database_connection.execute("SELECT count(*) FROM jd_revisions").fetchone() == (1,)
    assert client.post(url, json=request).status_code == 200


def test_unknown_and_foreign_areas_are_not_valid_targets(client: TestClient) -> None:
    first_url = f"/api/job-files/{create_file(client)}/jd/areas"
    second_url = f"/api/job-files/{create_file(client)}/jd/areas"
    first = client.post(
        first_url, json=create_command(client.get(first_url).json()["revision_id"])
    ).json()
    second = client.post(
        second_url, json=create_command(client.get(second_url).json()["revision_id"])
    ).json()
    for foreign_id in (str(uuid4()), second["areas"][0]["area_id"]):
        for change in (
            {"action": "delete_area", "area_id": foreign_id},
            {
                "action": "revise_area",
                "area_id": foreign_id,
                "changes": [{"field": "title", "value": "越界"}],
            },
            {
                "action": "reorder_area",
                "area_id": first["areas"][0]["area_id"],
                "before_area_id": foreign_id,
            },
        ):
            request = {**create_command(first["revision_id"]), "change": change}
            rejected = client.post(first_url, json=request)
            assert rejected.status_code == 404
            assert rejected.json()["detail"]["code"] == "jd_area_not_found"
    assert client.get(first_url).json() == first
    assert client.get(second_url).json() == second
    absent = f"/api/job-files/{uuid4()}/jd/areas"
    assert client.get(absent).status_code == 404
    assert client.post(absent, json=create_command(str(uuid4()))).status_code == 404
