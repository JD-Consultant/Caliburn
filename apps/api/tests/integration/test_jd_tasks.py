"""Tasks keep their own ordered details and survive responsibility-group removal."""

from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.features.job_description import task_service
from caliburn.features.job_description.tasks import EditJdTasks

pytestmark = pytest.mark.postgres


def create_file(client: TestClient) -> str:
    response = client.post(
        "/api/job-files",
        json={
            "command_id": str(uuid4()),
            "display_name": "合成任務",
            "employee_name": "合成員工",
        },
    )
    assert response.status_code == 201
    return response.json()["job_file_id"]


def edit(client: TestClient, url: str, revision_id: str, change: dict) -> dict:
    response = client.post(
        url,
        json={
            "command_id": str(uuid4()),
            "expected_revision_id": revision_id,
            "change": change,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def create_task_change(area_id: str | None = None, title: str = "實作網頁") -> dict:
    return {
        "action": "create_task",
        "area_id": area_id,
        "title": title,
        "description": "依已確認設計完成約定前端範圍。",
        "outcomes": ["可操作頁面", "交接說明"],
        "requirements": ["核對約定主要流程"],
    }


def test_delete_area_preserves_tasks_details_order_and_old_result(client: TestClient) -> None:
    file_id = create_file(client)
    tasks_url = f"/api/job-files/{file_id}/jd/tasks"
    areas_url = f"/api/job-files/{file_id}/jd/areas"
    empty = client.get(tasks_url)
    assert empty.status_code == 200
    assert empty.json()["tasks"] == []
    area = edit(
        client,
        areas_url,
        empty.json()["revision_id"],
        {
            "action": "create_area",
            "title": "網站交付",
            "scope_text": None,
        },
    )
    area_id = area["areas"][0]["area_id"]
    unassigned = edit(
        client, tasks_url, area["revision_id"], create_task_change(title="既有未歸屬")
    )
    request = {
        "command_id": str(uuid4()),
        "expected_revision_id": unassigned["revision_id"],
        "change": create_task_change(area_id),
    }
    response = client.post(tasks_url, json=request)
    assert response.status_code == 200
    first = response.json()
    second = edit(client, tasks_url, first["revision_id"], create_task_change(area_id, "檢查頁面"))
    deleted = edit(
        client,
        areas_url,
        second["revision_id"],
        {
            "action": "delete_area",
            "area_id": area_id,
        },
    )
    assert deleted["areas"] == []
    current = client.get(tasks_url).json()
    assert current["revision_id"] == deleted["revision_id"]
    assert current["tasks"] == [{**task, "area_id": None} for task in second["tasks"]]
    assert client.post(tasks_url, json=request).json() == first
    assert client.get(tasks_url).json() == current


def test_details_are_independent_groups_and_partial_edit_retains_identity(
    client: TestClient,
) -> None:
    file_id = create_file(client)
    url = f"/api/job-files/{file_id}/jd/tasks"
    empty = client.get(url)
    assert empty.status_code == 200
    original = edit(client, url, empty.json()["revision_id"], create_task_change())
    task = original["tasks"][0]
    assert len(task["outcomes"]) == 2
    assert len(task["requirements"]) == 1
    revised = edit(
        client,
        url,
        original["revision_id"],
        {
            "action": "revise_task",
            "task_id": task["task_id"],
            "changes": [
                {"action": "set_field", "field": "title", "value": "交付前端頁面"},
                {
                    "action": "revise_detail",
                    "detail_id": task["outcomes"][0]["detail_id"],
                    "text": "符合約定的頁面",
                },
                {"action": "add_detail", "kind": "requirement", "text": "說明已知限制"},
            ],
        },
    )
    result = revised["tasks"][0]
    assert result["task_id"] == task["task_id"]
    assert result["description"] == task["description"]
    assert result["outcomes"][0] == {**task["outcomes"][0], "text": "符合約定的頁面"}
    assert result["outcomes"][1] == task["outcomes"][1]
    assert result["requirements"][0] == task["requirements"][0]
    assert result["requirements"][1]["text"] == "說明已知限制"


def create_command(revision_id: str) -> dict:
    return {
        "command_id": str(uuid4()),
        "expected_revision_id": revision_id,
        "change": create_task_change(),
    }


def test_move_reorders_without_recreating_content_and_profile_edits_preserve_tasks(
    client: TestClient,
    database_connection: psycopg.Connection,
) -> None:
    file_id = create_file(client)
    url = f"/api/job-files/{file_id}/jd/tasks"
    area_url = f"/api/job-files/{file_id}/jd/areas"
    area = edit(
        client,
        area_url,
        client.get(url).json()["revision_id"],
        {
            "action": "create_area",
            "title": "前端交付",
            "scope_text": None,
        },
    )
    area_id = area["areas"][0]["area_id"]
    first = edit(client, url, area["revision_id"], create_task_change(title="一"))
    second = edit(client, url, first["revision_id"], create_task_change(area_id, "二"))
    third = edit(client, url, second["revision_id"], create_task_change(area_id, "三"))
    one, two, three = third["tasks"]
    moved = edit(
        client,
        url,
        third["revision_id"],
        {
            "action": "move_task",
            "task_id": one["task_id"],
            "area_id": area_id,
            "before_task_id": three["task_id"],
            "changes": [],
        },
    )
    assert moved["tasks"] == [two, {**one, "area_id": area_id}, three]
    unassigned = edit(
        client,
        url,
        moved["revision_id"],
        {
            "action": "move_task",
            "task_id": three["task_id"],
            "area_id": None,
            "before_task_id": None,
            "changes": [],
        },
    )
    assert unassigned["tasks"] == [{**three, "area_id": None}, two, {**one, "area_id": area_id}]
    assert database_connection.execute("SELECT count(*) FROM jd_task_revisions").fetchone() == (3,)
    profile = client.post(
        f"/api/job-files/{file_id}/jd/profile",
        json={
            "command_id": str(uuid4()),
            "expected_revision_id": unassigned["revision_id"],
            "changes": [{"action": "set_field", "field": "job_title", "value": "工程師"}],
        },
    )
    assert profile.status_code == 200
    assert client.get(url).json()["tasks"] == unassigned["tasks"]
    changed = edit(
        client,
        url,
        profile.json()["revision_id"],
        {
            "action": "move_task",
            "task_id": three["task_id"],
            "area_id": area_id,
            "before_task_id": two["task_id"],
            "changes": [
                {"action": "set_field", "field": "description", "value": "移入約定交付範圍"}
            ],
        },
    )
    assert changed["tasks"][0] == {**three, "area_id": area_id, "description": "移入約定交付範圍"}
    assert (
        client.get(f"/api/job-files/{file_id}/jd/profile").json()["profile"]["job_title"]
        == "工程師"
    )
    assert client.get(area_url).json()["areas"] == area["areas"]
    assert database_connection.execute("SELECT count(*) FROM jd_task_revisions").fetchone() == (4,)


def test_detail_reordering_removal_noop_and_changed_back_history(
    client: TestClient,
    database_connection: psycopg.Connection,
) -> None:
    url = f"/api/job-files/{create_file(client)}/jd/tasks"
    original = edit(client, url, client.get(url).json()["revision_id"], create_task_change())
    task = original["tasks"][0]
    first, second = task["outcomes"]
    reordered = edit(
        client,
        url,
        original["revision_id"],
        {
            "action": "reorder_detail",
            "task_id": task["task_id"],
            "detail_id": second["detail_id"],
            "before_detail_id": first["detail_id"],
        },
    )
    assert reordered["tasks"][0] == {**task, "outcomes": [second, first]}
    for before in (first["detail_id"], None):
        assert (
            edit(
                client,
                url,
                reordered["revision_id"],
                {
                    "action": "reorder_detail",
                    "task_id": task["task_id"],
                    "detail_id": first["detail_id"],
                    "before_detail_id": before,
                },
            )
            == reordered
        )
    restored = edit(
        client,
        url,
        reordered["revision_id"],
        {
            "action": "reorder_detail",
            "task_id": task["task_id"],
            "detail_id": second["detail_id"],
            "before_detail_id": None,
        },
    )
    assert restored["tasks"] == original["tasks"]
    assert restored["revision_id"] != original["revision_id"]
    assert (
        edit(
            client,
            url,
            restored["revision_id"],
            {
                "action": "revise_task",
                "task_id": task["task_id"],
                "changes": [{"action": "set_field", "field": "title", "value": task["title"]}],
            },
        )
        == restored
    )
    cleared = edit(
        client,
        url,
        restored["revision_id"],
        {
            "action": "revise_task",
            "task_id": task["task_id"],
            "changes": [
                {"action": "set_field", "field": "title", "value": None},
                {"action": "remove_detail", "detail_id": first["detail_id"]},
            ],
        },
    )
    assert cleared["tasks"][0] == {**task, "title": None, "outcomes": [second]}
    removed = edit(
        client, url, cleared["revision_id"], {"action": "delete_task", "task_id": task["task_id"]}
    )
    assert removed["tasks"] == []
    recreated = edit(client, url, removed["revision_id"], create_task_change())
    assert recreated["tasks"][0]["task_id"] != task["task_id"]
    assert database_connection.execute("SELECT count(*) FROM jd_task_revisions").fetchone() == (5,)


def test_replay_concurrency_stale_base_and_command_collision(
    client: TestClient,
    database_connection: psycopg.Connection,
) -> None:
    file_id = create_file(client)
    url = f"/api/job-files/{file_id}/jd/tasks"
    request = create_command(client.get(url).json()["revision_id"])
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: client.post(url, json=request), range(8)))
    assert all(
        result.status_code == 200 and result.json() == results[0].json() for result in results
    )
    assert database_connection.execute("SELECT count(*) FROM jd_task_revisions").fetchone() == (1,)
    original = results[0].json()
    with ThreadPoolExecutor(max_workers=2) as pool:
        competing = list(
            pool.map(
                lambda _: client.post(url, json=create_command(original["revision_id"])), range(2)
            )
        )
    assert sorted(result.status_code for result in competing) == [200, 409]
    for replacement in (
        {"expected_revision_id": original["revision_id"]},
        {"change": create_task_change(title="不同意圖")},
    ):
        response = client.post(url, json={**request, **replacement})
        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "jd_command_conflict"
    area_request = {
        **request,
        "change": {"action": "create_area", "title": "衝突", "scope_text": None},
    }
    assert client.post(f"/api/job-files/{file_id}/jd/areas", json=area_request).status_code == 409
    current = client.get(url).json()
    assert (
        client.post(
            f"/api/job-files/{file_id}/inputs",
            json={
                "command_id": str(uuid4()),
                "text": "合成訪談",
            },
        ).status_code
        == 202
    )
    assert client.post(url, json=request).json() == original
    assert client.get(url).json() == current
    blocked = client.post(url, json=create_command(current["revision_id"]))
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["code"] == "consultant_turn_active"


@pytest.mark.parametrize(
    "invalid_fields",
    [
        {"title": None, "description": None},
        {"title": ""},
        {"description": " \n\t"},
        {"title": "\u3000"},
        {"title": 3},
        {"outcomes": ["\x00bad"]},
        {"requirements": [None]},
        {"extra": True},
        {"action": "unknown"},
    ],
)
def test_invalid_creation_is_rejected_before_any_write(
    client: TestClient,
    database_connection: psycopg.Connection,
    invalid_fields: dict,
) -> None:
    url = f"/api/job-files/{create_file(client)}/jd/tasks"
    original = client.get(url).json()
    request = {
        **create_command(original["revision_id"]),
        "change": {**create_task_change(), **invalid_fields},
    }
    assert client.post(url, json=request).status_code == 422
    assert client.get(url).json() == original
    assert database_connection.execute("SELECT count(*) FROM jd_task_revisions").fetchone() == (0,)
    assert database_connection.execute("SELECT count(*) FROM jd_operations").fetchone() == (0,)


def test_bad_late_changes_and_move_targets_leave_no_partial_effects(
    client: TestClient,
    database_connection: psycopg.Connection,
) -> None:
    url = f"/api/job-files/{create_file(client)}/jd/tasks"
    original = edit(client, url, client.get(url).json()["revision_id"], create_task_change())
    task = original["tasks"][0]
    for changes, status in [
        ([], 422),
        (
            [
                {"action": "set_field", "field": "title", "value": "new"},
                {"action": "set_field", "field": "title", "value": "duplicate"},
            ],
            422,
        ),
        (
            [
                {"action": "set_field", "field": "title", "value": None},
                {"action": "set_field", "field": "description", "value": None},
            ],
            422,
        ),
        (
            [
                {"action": "add_detail", "kind": "outcome", "text": "不應留下"},
                {"action": "remove_detail", "detail_id": str(uuid4())},
            ],
            404,
        ),
        (
            [
                {
                    "action": "revise_detail",
                    "detail_id": task["outcomes"][0]["detail_id"],
                    "text": "改寫",
                },
                {"action": "remove_detail", "detail_id": task["outcomes"][0]["detail_id"]},
            ],
            422,
        ),
    ]:
        response = client.post(
            url,
            json={
                **create_command(original["revision_id"]),
                "change": {
                    "action": "revise_task",
                    "task_id": task["task_id"],
                    "changes": changes,
                },
            },
        )
        assert response.status_code == status, response.text
    bad_move = client.post(
        url,
        json={
            **create_command(original["revision_id"]),
            "change": {
                "action": "move_task",
                "task_id": task["task_id"],
                "area_id": None,
                "before_task_id": str(uuid4()),
                "changes": [{"action": "add_detail", "kind": "outcome", "text": "不應留下"}],
            },
        },
    )
    assert bad_move.status_code == 404
    assert client.get(url).json() == original
    assert database_connection.execute("SELECT count(*) FROM jd_task_revisions").fetchone() == (1,)
    assert database_connection.execute("SELECT count(*) FROM jd_task_details").fetchone() == (3,)
    assert database_connection.execute("SELECT count(*) FROM jd_operations").fetchone() == (1,)


def test_detail_scope_kind_and_foreign_targets(client: TestClient) -> None:
    file_id = create_file(client)
    url = f"/api/job-files/{file_id}/jd/tasks"
    first = edit(client, url, client.get(url).json()["revision_id"], create_task_change())
    current = edit(client, url, first["revision_id"], create_task_change(title="other task"))
    own, other = current["tasks"]
    foreign_url = f"/api/job-files/{create_file(client)}/jd/tasks"
    foreign = edit(
        client, foreign_url, client.get(foreign_url).json()["revision_id"], create_task_change()
    )
    cases = [
        (
            {
                "action": "reorder_detail",
                "task_id": own["task_id"],
                "detail_id": own["outcomes"][0]["detail_id"],
                "before_detail_id": own["requirements"][0]["detail_id"],
            },
            422,
        ),
        (
            {
                "action": "reorder_detail",
                "task_id": own["task_id"],
                "detail_id": own["outcomes"][0]["detail_id"],
                "before_detail_id": other["outcomes"][0]["detail_id"],
            },
            404,
        ),
        (
            {
                "action": "revise_task",
                "task_id": own["task_id"],
                "changes": [
                    {
                        "action": "revise_detail",
                        "detail_id": other["outcomes"][0]["detail_id"],
                        "text": "越界",
                    }
                ],
            },
            404,
        ),
        ({"action": "delete_task", "task_id": foreign["tasks"][0]["task_id"]}, 404),
        (
            {
                "action": "move_task",
                "task_id": own["task_id"],
                "area_id": str(uuid4()),
                "before_task_id": None,
                "changes": [],
            },
            404,
        ),
    ]
    for change, status in cases:
        response = client.post(
            url, json={**create_command(current["revision_id"]), "change": change}
        )
        assert response.status_code == status, response.text
    assert client.get(url).json() == current
    assert client.get(foreign_url).json() == foreign
    absent = f"/api/job-files/{uuid4()}/jd/tasks"
    assert client.get(absent).status_code == 404
    assert client.post(absent, json=create_command(str(uuid4()))).status_code == 404


def test_injected_failure_rolls_back_content_details_head_and_operation(
    client: TestClient,
    database_connection: psycopg.Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_edit = task_service.edit_tasks

    async def fail_after_write(session: AsyncSession, file_id: UUID, command: EditJdTasks) -> None:
        await original_edit(session, file_id, command)
        raise RuntimeError("Injected before commit")

    url = f"/api/job-files/{create_file(client)}/jd/tasks"
    original = client.get(url).json()
    request = create_command(original["revision_id"])
    with monkeypatch.context() as patch:
        patch.setattr(task_service, "edit_tasks", fail_after_write)
        with pytest.raises(RuntimeError, match="Injected"):
            client.post(url, json=request)
    assert client.get(url).json() == original
    for table in ("jd_task_revisions", "jd_task_details", "jd_task_selections", "jd_operations"):
        assert database_connection.execute(
            psycopg.sql.SQL("SELECT count(*) FROM {}").format(
                psycopg.sql.Identifier(table),
            )
        ).fetchone() == (0,)
    assert database_connection.execute("SELECT count(*) FROM jd_revisions").fetchone() == (1,)
    assert client.post(url, json=request).status_code == 200
