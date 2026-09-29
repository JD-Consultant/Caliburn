"""Shared knowledge/skills are separate from each task's ordered use of them."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.features.job_description import capability_persistence, capability_service
from caliburn.features.job_description.capabilities import Capability, EditJdCapabilities

pytestmark = pytest.mark.postgres


def create_file(client: TestClient) -> str:
    response = client.post(
        "/api/job-files",
        json={"command_id": str(uuid4()), "display_name": "合成專業", "employee_name": "合成人"},
    )
    assert response.status_code == 201
    return f"/api/job-files/{response.json()['job_file_id']}/jd"


def edit(client: TestClient, url: str, base: dict, change: dict) -> dict:
    response = client.post(
        url,
        json={
            "command_id": str(uuid4()),
            "expected_revision_id": base["revision_id"],
            "change": change,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def create_capability(kind: str = "knowledge", name: str = "資料介面") -> dict:
    return {
        "action": "create_capability",
        "kind": kind,
        "name": name,
        "description": "理解狀態與失敗訊號。",
    }


def create_task(client: TestClient, url: str, base: dict, title: str) -> dict:
    return edit(
        client,
        f"{url}/tasks",
        base,
        {
            "action": "create_task",
            "area_id": None,
            "title": title,
            "description": None,
            "outcomes": [],
            "requirements": [],
        },
    )


def test_shared_definition_preserves_links_and_rejects_delete_in_use(client: TestClient) -> None:
    url = create_file(client)
    endpoint = f"{url}/capabilities"
    empty = client.get(endpoint)
    assert empty.status_code == 200
    assert empty.json()["capabilities"] == empty.json()["task_links"] == []
    created = edit(client, endpoint, empty.json(), create_capability())
    capability_id = created["capabilities"][0]["capability_id"]
    first = create_task(client, url, created, "串接介面")
    second = create_task(client, url, first, "診斷錯誤")
    current = second
    for task in second["tasks"]:
        current = edit(
            client,
            endpoint,
            current,
            {
                "action": "set_task_capability",
                "task_id": task["task_id"],
                "capability_id": capability_id,
                "linked": True,
            },
        )
    before = current
    renamed = edit(
        client,
        endpoint,
        before,
        {
            "action": "revise_capability",
            "capability_id": capability_id,
            "changes": [{"field": "name", "value": "資料契約與錯誤訊號"}],
        },
    )
    assert renamed["task_links"] == before["task_links"]
    assert len(renamed["capabilities"]) == 1
    response = client.post(
        endpoint,
        json={
            "command_id": str(uuid4()),
            "expected_revision_id": renamed["revision_id"],
            "change": {"action": "delete_capability", "capability_id": capability_id},
        },
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "capability_in_use"
    assert client.get(endpoint).json() == renamed
    deleted_task = edit(
        client,
        f"{url}/tasks",
        renamed,
        {"action": "delete_task", "task_id": second["tasks"][0]["task_id"]},
    )
    after = client.get(endpoint).json()
    assert after["revision_id"] == deleted_task["revision_id"]
    assert after["capabilities"] == renamed["capabilities"]
    assert len(after["task_links"]) == 1
    unlinked = edit(
        client,
        endpoint,
        after,
        {
            "action": "set_task_capability",
            "task_id": second["tasks"][1]["task_id"],
            "capability_id": capability_id,
            "linked": False,
        },
    )
    removed = edit(
        client, endpoint, unlinked, {"action": "delete_capability", "capability_id": capability_id}
    )
    assert removed["capabilities"] == removed["task_links"] == []


def command_for(base: dict, change: dict) -> dict:
    return {
        "command_id": str(uuid4()),
        "expected_revision_id": base["revision_id"],
        "change": change,
    }


def test_content_reuse_noop_and_revert_keep_revision_history(
    client: TestClient,
    database_connection: psycopg.Connection,
) -> None:
    endpoint = f"{create_file(client)}/capabilities"
    original = edit(client, endpoint, client.get(endpoint).json(), create_capability())
    capability = original["capabilities"][0]
    same = {
        "action": "revise_capability",
        "capability_id": capability["capability_id"],
        "changes": [{"field": "name", "value": capability["name"]}],
    }
    assert edit(client, endpoint, original, same) == original
    renamed = edit(
        client, endpoint, original, {**same, "changes": [{"field": "name", "value": "改名"}]}
    )
    reverted = edit(client, endpoint, renamed, same)
    assert reverted["capabilities"] == original["capabilities"]
    assert len({original["revision_id"], renamed["revision_id"], reverted["revision_id"]}) == 3
    # Same-value intent has a receipt, but no new content or document revision.
    assert database_connection.execute(
        "SELECT count(*) FROM jd_capability_revisions"
    ).fetchone() == (3,)
    assert database_connection.execute("SELECT count(*) FROM jd_operations").fetchone() == (4,)
    cleared = edit(
        client, endpoint, reverted, {**same, "changes": [{"field": "name", "value": None}]}
    )
    assert cleared["capabilities"][0]["name"] is None
    assert cleared["capabilities"][0]["description"] == capability["description"]


def test_overview_and_task_orders_are_independent_within_kind(
    client: TestClient,
    database_connection: psycopg.Connection,
) -> None:
    url = create_file(client)
    endpoint = f"{url}/capabilities"
    current = client.get(endpoint).json()
    for kind, name in (("knowledge", "K1"), ("skill", "S1"), ("knowledge", "K2"), ("skill", "S2")):
        current = edit(client, endpoint, current, create_capability(kind, name))
    k1, s1, k2, s2 = [item["capability_id"] for item in current["capabilities"]]
    tasks = create_task(client, url, current, "工作")
    task_id = tasks["tasks"][0]["task_id"]
    current = tasks
    for identity in (k1, s1, k2, s2):
        current = edit(
            client,
            endpoint,
            current,
            {
                "action": "set_task_capability",
                "task_id": task_id,
                "capability_id": identity,
                "linked": True,
            },
        )
    ordered = edit(
        client,
        endpoint,
        current,
        {"action": "reorder_capability", "capability_id": k2, "before_capability_id": k1},
    )
    assert [item["capability_id"] for item in ordered["capabilities"]] == [k2, s1, k1, s2]
    assert ordered["task_links"] == current["task_links"]
    reordered = edit(
        client,
        endpoint,
        ordered,
        {
            "action": "reorder_task_capability",
            "task_id": task_id,
            "capability_id": s2,
            "before_capability_id": s1,
        },
    )
    assert reordered["capabilities"] == ordered["capabilities"]
    assert [item["capability_id"] for item in reordered["task_links"]] == [k1, s2, k2, s1]
    for change in (
        {"action": "reorder_capability", "capability_id": k1, "before_capability_id": None},
        {"action": "reorder_capability", "capability_id": k1, "before_capability_id": k1},
        {
            "action": "reorder_task_capability",
            "task_id": task_id,
            "capability_id": s1,
            "before_capability_id": None,
        },
        {"action": "set_task_capability", "task_id": task_id, "capability_id": k1, "linked": True},
    ):
        assert edit(client, endpoint, reordered, change) == reordered
    unlinked = edit(
        client,
        endpoint,
        reordered,
        {"action": "set_task_capability", "task_id": task_id, "capability_id": k1, "linked": False},
    )
    assert (
        edit(
            client,
            endpoint,
            unlinked,
            {
                "action": "set_task_capability",
                "task_id": task_id,
                "capability_id": k1,
                "linked": False,
            },
        )
        == unlinked
    )
    assert database_connection.execute(
        "SELECT count(*) FROM jd_capability_revisions"
    ).fetchone() == (4,)


def test_profile_area_and_task_changes_preserve_shared_definitions_and_links(
    client: TestClient,
) -> None:
    url = create_file(client)
    endpoint = f"{url}/capabilities"
    created = edit(client, endpoint, client.get(endpoint).json(), create_capability())
    capability_id = created["capabilities"][0]["capability_id"]
    tasks = create_task(client, url, created, "交付")
    task = tasks["tasks"][0]
    linked = edit(
        client,
        endpoint,
        tasks,
        {
            "action": "set_task_capability",
            "task_id": task["task_id"],
            "capability_id": capability_id,
            "linked": True,
        },
    )
    area = edit(
        client,
        f"{url}/areas",
        linked,
        {"action": "create_area", "title": "網站", "scope_text": None},
    )
    area_id = area["areas"][0]["area_id"]
    moved = edit(
        client,
        f"{url}/tasks",
        area,
        {
            "action": "move_task",
            "task_id": task["task_id"],
            "area_id": area_id,
            "before_task_id": None,
            "changes": [{"action": "add_detail", "kind": "outcome", "text": "頁面"}],
        },
    )
    profile = client.post(
        f"{url}/profile",
        json={
            "command_id": str(uuid4()),
            "expected_revision_id": moved["revision_id"],
            "changes": [{"action": "set_field", "field": "job_title", "value": "前端工程師"}],
        },
    )
    assert profile.status_code == 200
    removed = edit(
        client, f"{url}/areas", profile.json(), {"action": "delete_area", "area_id": area_id}
    )
    assert client.get(endpoint).json() == {**linked, "revision_id": removed["revision_id"]}
    unassigned = client.get(f"{url}/tasks").json()["tasks"][0]
    assert unassigned["area_id"] is None
    assert unassigned["outcomes"][0]["text"] == "頁面"
    revised = edit(
        client,
        endpoint,
        removed,
        {
            "action": "revise_capability",
            "capability_id": capability_id,
            "changes": [{"field": "description", "value": "資料契約"}],
        },
    )
    assert client.get(f"{url}/profile").json()["profile"] == profile.json()["profile"]
    assert client.get(f"{url}/tasks").json() == {
        "revision_id": revised["revision_id"],
        "tasks": [unassigned],
    }


def test_replay_races_stale_base_conflicts_and_active_consultant(
    client: TestClient,
    database_connection: psycopg.Connection,
) -> None:
    url = create_file(client)
    endpoint = f"{url}/capabilities"
    request = command_for(client.get(endpoint).json(), create_capability())
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: client.post(endpoint, json=request), range(8)))
    assert all(
        result.status_code == 200 and result.json() == results[0].json() for result in results
    )
    original = results[0].json()
    assert database_connection.execute(
        "SELECT count(*) FROM jd_capability_revisions"
    ).fetchone() == (1,)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda _: client.post(
                    endpoint, json=command_for(original, create_capability("skill", "診斷"))
                ),
                range(2),
            )
        )
    assert sorted(result.status_code for result in results) == [200, 409]
    for update in (
        {"change": create_capability(name="另一個")},
        {"expected_revision_id": original["revision_id"]},
    ):
        failed = client.post(endpoint, json={**request, **update})
        assert failed.status_code == 409
        assert failed.json()["detail"]["code"] == "jd_command_conflict"
    collision = client.post(
        f"{url}/areas",
        json={**request, "change": {"action": "create_area", "title": "衝突", "scope_text": None}},
    )
    assert collision.status_code == 409
    current = client.get(endpoint).json()
    removed = edit(
        client,
        endpoint,
        current,
        {
            "action": "delete_capability",
            "capability_id": original["capabilities"][0]["capability_id"],
        },
    )
    assert (
        client.post(
            url.removesuffix("/jd") + "/inputs", json={"command_id": str(uuid4()), "text": "合成"}
        ).status_code
        == 202
    )
    assert client.post(endpoint, json=request).json() == original
    blocked = client.post(endpoint, json=command_for(removed, create_capability()))
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["code"] == "consultant_turn_active"
    assert client.get(endpoint).json() == removed


@pytest.mark.parametrize(
    "replacement",
    [
        {"name": None, "description": None},
        {"name": ""},
        {"name": " \n\t"},
        {"name": "\u3000"},
        {"description": "bad\x00"},
        {"kind": "other"},
        {"name": 2},
        {"extra": True},
    ],
)
def test_invalid_definition_does_not_write(
    client: TestClient,
    database_connection: psycopg.Connection,
    replacement: dict,
) -> None:
    endpoint = f"{create_file(client)}/capabilities"
    original = client.get(endpoint).json()
    assert (
        client.post(
            endpoint, json=command_for(original, {**create_capability(), **replacement})
        ).status_code
        == 422
    )
    assert client.get(endpoint).json() == original
    assert database_connection.execute(
        "SELECT count(*) FROM jd_capability_revisions"
    ).fetchone() == (0,)
    assert database_connection.execute("SELECT count(*) FROM jd_operations").fetchone() == (0,)


def test_invalid_changes_and_foreign_targets_are_atomic(client: TestClient) -> None:
    url = create_file(client)
    endpoint = f"{url}/capabilities"
    current = edit(client, endpoint, client.get(endpoint).json(), create_capability())
    k1 = current["capabilities"][0]["capability_id"]
    current = edit(client, endpoint, current, create_capability("skill", "S"))
    s1 = current["capabilities"][1]["capability_id"]
    tasks = create_task(client, url, current, "工作")
    task_id = tasks["tasks"][0]["task_id"]
    current = client.get(endpoint).json()
    other_url = create_file(client)
    other_endpoint = f"{other_url}/capabilities"
    other = edit(client, other_endpoint, client.get(other_endpoint).json(), create_capability())
    foreign_task = create_task(client, other_url, other, "其他檔案")["tasks"][0]["task_id"]
    for change, status in (
        ({"action": "revise_capability", "capability_id": k1, "changes": []}, 422),
        (
            {
                "action": "revise_capability",
                "capability_id": k1,
                "changes": [{"field": "name", "value": "新"}, {"field": "name", "value": "重複"}],
            },
            422,
        ),
        (
            {
                "action": "revise_capability",
                "capability_id": k1,
                "changes": [
                    {"field": "name", "value": None},
                    {"field": "description", "value": None},
                ],
            },
            422,
        ),
        (
            {
                "action": "revise_capability",
                "capability_id": k1,
                "changes": [{"field": "kind", "value": "skill"}],
            },
            422,
        ),
        (
            {
                "action": "delete_capability",
                "capability_id": other["capabilities"][0]["capability_id"],
            },
            404,
        ),
        ({"action": "reorder_capability", "capability_id": k1, "before_capability_id": s1}, 404),
        (
            {
                "action": "set_task_capability",
                "task_id": foreign_task,
                "capability_id": k1,
                "linked": True,
            },
            404,
        ),
        (
            {"action": "set_task_capability", "task_id": task_id, "capability_id": k1, "linked": 1},
            422,
        ),
        (
            {
                "action": "reorder_task_capability",
                "task_id": task_id,
                "capability_id": k1,
                "before_capability_id": None,
            },
            404,
        ),
    ):
        response = client.post(endpoint, json=command_for(current, change))
        assert response.status_code == status, response.text
    assert client.get(endpoint).json() == current
    absent = f"/api/job-files/{uuid4()}/jd/capabilities"
    assert client.get(absent).status_code == 404
    assert client.post(absent, json=command_for(current, create_capability())).status_code == 404


@pytest.mark.parametrize("operation", ["content", "relation"])
def test_before_commit_failure_rolls_back_all_effects(
    client: TestClient,
    database_connection: psycopg.Connection,
    monkeypatch: pytest.MonkeyPatch,
    operation: str,
) -> None:
    url = create_file(client)
    endpoint = f"{url}/capabilities"
    current = edit(client, endpoint, client.get(endpoint).json(), create_capability())
    tasks = create_task(client, url, current, "工作")
    current = client.get(endpoint).json()
    change = (
        create_capability("skill", "診斷")
        if operation == "content"
        else {
            "action": "set_task_capability",
            "task_id": tasks["tasks"][0]["task_id"],
            "capability_id": current["capabilities"][0]["capability_id"],
            "linked": True,
        }
    )
    tables = (
        "jd_capability_revisions",
        "jd_capability_selections",
        "jd_task_capabilities",
        "jd_revisions",
        "jd_operations",
    )

    def counts() -> list:
        return [
            database_connection.execute(
                psycopg.sql.SQL("SELECT count(*) FROM {}").format(psycopg.sql.Identifier(table))
            ).fetchone()
            for table in tables
        ]

    before = counts()
    original_edit = capability_service.edit_capabilities

    async def fail_after_write(
        session: AsyncSession, file_id: UUID, command: EditJdCapabilities
    ) -> None:
        await original_edit(session, file_id, command)
        raise RuntimeError("Injected before commit")

    request = command_for(current, change)
    with monkeypatch.context() as patch:
        patch.setattr(capability_service, "edit_capabilities", fail_after_write)
        with pytest.raises(RuntimeError, match="Injected"):
            client.post(endpoint, json=request)
    assert client.get(endpoint).json() == current
    assert counts() == before
    assert client.post(endpoint, json=request).status_code == 200


def test_definition_and_task_use_are_read_from_one_fixed_revision(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    url = create_file(client)
    endpoint = f"{url}/capabilities"
    created = edit(client, endpoint, client.get(endpoint).json(), create_capability())
    tasks = create_task(client, url, created, "工作")
    current = client.get(endpoint).json()
    original_read = capability_persistence.read_capabilities
    changed = False

    async def link_after_definition_read(
        session: AsyncSession, file_id: UUID, revision_id: UUID
    ) -> tuple[Capability, ...]:
        nonlocal changed
        result = await original_read(session, file_id, revision_id)
        if not changed:
            changed = True
            response = await asyncio.to_thread(
                client.post,
                endpoint,
                json=command_for(
                    current,
                    {
                        "action": "set_task_capability",
                        "task_id": tasks["tasks"][0]["task_id"],
                        "capability_id": created["capabilities"][0]["capability_id"],
                        "linked": True,
                    },
                ),
            )
            assert response.status_code == 200
        return result

    monkeypatch.setattr(capability_persistence, "read_capabilities", link_after_definition_read)
    assert client.get(endpoint).json() == current
    latest = client.get(endpoint).json()
    assert latest["revision_id"] != current["revision_id"]
    assert len(latest["task_links"]) == 1


def test_original_capability_result_is_not_current_definition(client: TestClient) -> None:
    url = create_file(client)
    endpoint = f"{url}/capabilities"
    empty = client.get(endpoint)
    assert empty.status_code == 200
    command = {
        "command_id": str(uuid4()),
        "expected_revision_id": empty.json()["revision_id"],
        "change": create_capability(),
    }
    original = client.post(endpoint, json=command).json()
    renamed = edit(
        client,
        endpoint,
        original,
        {
            "action": "revise_capability",
            "capability_id": original["capabilities"][0]["capability_id"],
            "changes": [{"field": "name", "value": "另一名稱"}],
        },
    )
    assert client.post(endpoint, json=command).json() == original
    assert client.get(endpoint).json() == renamed
