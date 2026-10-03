"""Collaborators and job-wide conditions share the formal JD revision boundary."""

from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg import sql
from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.features.executions import service as executions
from caliburn.features.executions.models import ExecutionKind, ExecutionScope
from caliburn.features.job_description import persistence
from caliburn.features.job_description.models import JdProfileRevision

pytestmark = pytest.mark.postgres


def create_file(client: TestClient) -> str:
    response = client.post(
        "/api/job-files",
        json={
            "command_id": str(uuid4()),
            "display_name": "合成全職務",
            "employee_name": "合成員工",
        },
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


def test_collaborator_scope_can_exist_before_name_is_known(client: TestClient) -> None:
    base = f"/api/job-files/{create_file(client)}/jd"
    initial = client.get(base + "/collaborators")
    assert initial.status_code == 200
    assert initial.json()["collaborators"] == []
    created = edit(
        client,
        base + "/collaborators",
        initial.json()["revision_id"],
        {
            "action": "create_collaborator",
            "name": None,
            "scope_text": "與值班人員協調事故升級",
        },
    )
    collaborator = created["collaborators"][0]
    revised = edit(
        client,
        base + "/collaborators",
        created["revision_id"],
        {
            "action": "revise_collaborator",
            "collaborator_id": collaborator["collaborator_id"],
            "changes": [{"field": "name", "value": "值班工程師"}],
        },
    )
    assert revised["collaborators"] == [{**collaborator, "name": "值班工程師"}]


def test_job_condition_text_does_not_create_task_requirements(client: TestClient) -> None:
    base = f"/api/job-files/{create_file(client)}/jd"
    initial = client.get(base + "/conditions")
    assert initial.status_code == 200
    assert initial.json()["conditions"] == []
    created = edit(
        client,
        base + "/conditions",
        initial.json()["revision_id"],
        {
            "action": "create_condition",
            "kind": "schedule_travel",
            "text": "旺季依排班值班",
        },
    )
    assert created["conditions"][0]["text"] == "旺季依排班值班"
    assert client.get(base + "/tasks").json()["tasks"] == []


@pytest.mark.parametrize(
    "collection,change",
    [
        ("collaborators", {"action": "create_collaborator", "name": None, "scope_text": None}),
        ("collaborators", {"action": "create_collaborator", "name": "", "scope_text": None}),
        ("collaborators", {"action": "create_collaborator", "name": "\u3000", "scope_text": None}),
        ("collaborators", {"action": "create_collaborator", "name": "x\x00", "scope_text": None}),
        ("collaborators", {"action": "create_collaborator", "name": 1, "scope_text": None}),
        ("collaborators", {"action": "create_collaborator", "name": "協作"}),
        ("conditions", {"action": "create_condition", "kind": "unknown", "text": "內容"}),
        ("conditions", {"action": "create_condition", "kind": "qualification", "text": " \n\t"}),
        ("conditions", {"action": "create_condition", "kind": "qualification", "text": "\u3000"}),
        ("conditions", {"action": "create_condition", "kind": "qualification", "text": "x\x00"}),
        ("conditions", {"action": "create_condition", "kind": "qualification", "text": None}),
        ("conditions", {"action": "create_condition", "kind": "qualification", "text": 1}),
        (
            "conditions",
            {"action": "create_condition", "kind": "qualification", "text": "證照", "extra": True},
        ),
    ],
)
def test_invalid_input_leaves_no_revision_or_operation(
    client: TestClient,
    database_connection: psycopg.Connection,
    collection: str,
    change: dict,
) -> None:
    url = f"/api/job-files/{create_file(client)}/jd/{collection}"
    original = client.get(url).json()
    assert client.post(url, json=command(original["revision_id"], change)).status_code == 422
    assert client.get(url).json() == original
    assert database_connection.execute("SELECT count(*) FROM jd_revisions").fetchone() == (1,)
    assert database_connection.execute("SELECT count(*) FROM jd_operations").fetchone() == (0,)


@pytest.mark.parametrize("invalid_fields", ["duplicate", "empty", "blank", "unknown", "clear"])
def test_invalid_revision_is_rejected_as_a_whole(
    client: TestClient,
    item_kind: str,
    invalid_fields: str,
) -> None:
    url = f"/api/job-files/{create_file(client)}/jd/{item_kind}s"
    current = edit(client, url, client.get(url).json()["revision_id"], create_change(item_kind))
    field = "name" if item_kind == "collaborator" else "text"
    fields = {
        "duplicate": [{"field": field, "value": "甲"}, {"field": field, "value": "乙"}],
        "empty": [],
        "blank": [{"field": field, "value": "\u3000"}],
        "unknown": [{"field": "id", "value": "假目標"}],
        "clear": [{"field": field, "value": None}],
    }[invalid_fields]
    if invalid_fields == "clear" and item_kind == "collaborator":
        fields.append({"field": "scope_text", "value": None})
    response = client.post(
        url,
        json=command(
            current["revision_id"],
            {
                "action": f"revise_{item_kind}",
                f"{item_kind}_id": current[item_kind + "s"][0][item_kind + "_id"],
                "changes": fields,
            },
        ),
    )
    assert response.status_code == 422
    assert client.get(url).json() == current


def test_each_formal_write_preserves_other_collections_and_reuses_unchanged_content(
    client: TestClient,
    database_connection: psycopg.Connection,
) -> None:
    file_id = create_file(client)
    base = f"/api/job-files/{file_id}/jd"
    head = client.get(base + "/collaborators").json()["revision_id"]
    collab = edit(client, base + "/collaborators", head, create_change("collaborator"))
    condition = edit(
        client, base + "/conditions", collab["revision_id"], create_change("condition")
    )
    area = edit(
        client,
        base + "/areas",
        condition["revision_id"],
        {
            "action": "create_area",
            "title": "盤點",
            "scope_text": None,
        },
    )
    task = edit(
        client,
        base + "/tasks",
        area["revision_id"],
        {
            "action": "create_task",
            "area_id": area["areas"][0]["area_id"],
            "title": "盤點庫存",
            "description": None,
            "outcomes": [],
            "requirements": [],
        },
    )
    capability = edit(
        client,
        base + "/capabilities",
        task["revision_id"],
        {
            "action": "create_capability",
            "kind": "knowledge",
            "name": "盤點規則",
            "description": None,
        },
    )
    profile = client.post(
        base + "/profile",
        json={
            "command_id": str(uuid4()),
            "expected_revision_id": capability["revision_id"],
            "changes": [{"action": "set_field", "field": "job_title", "value": "倉管"}],
        },
    )
    assert profile.status_code == 200
    for collection, expected in (
        ("collaborators", collab),
        ("conditions", condition),
        ("areas", area),
        ("tasks", task),
        ("capabilities", capability),
    ):
        assert client.get(base + "/" + collection).json()[collection] == expected[collection]
    # Later writes to the new collections must likewise retain all earlier JD content.
    latest = edit(
        client,
        base + "/conditions",
        profile.json()["revision_id"],
        {
            "action": "revise_condition",
            "condition_id": condition["conditions"][0]["condition_id"],
            "changes": [{"field": "text", "value": "需在倉庫現場作業"}],
        },
    )
    edit(
        client,
        base + "/collaborators",
        latest["revision_id"],
        create_change("collaborator", "供應商"),
    )
    assert client.get(base + "/profile").json()["profile"]["job_title"] == "倉管"
    for collection, expected in (("areas", area), ("tasks", task), ("capabilities", capability)):
        assert client.get(base + "/" + collection).json()[collection] == expected[collection]
    for table in ("jd_collaborator_revisions", "jd_condition_revisions"):
        assert database_connection.execute(
            sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(table))
        ).fetchone() == (2,)


@pytest.fixture(params=["collaborator", "condition"])
def item_kind(request: pytest.FixtureRequest) -> str:
    return str(request.param)


def create_change(item_kind: str, text: str = "已知條件") -> dict:
    if item_kind == "collaborator":
        return {"action": "create_collaborator", "name": text, "scope_text": "協調工作範圍"}
    return {"action": "create_condition", "kind": "work_environment", "text": text}


def command(revision_id: str, change: dict) -> dict:
    return {"command_id": str(uuid4()), "expected_revision_id": revision_id, "change": change}


def test_replay_keeps_original_result_after_later_edits_and_blocks_changed_intent(
    client: TestClient,
    item_kind: str,
) -> None:
    base = f"/api/job-files/{create_file(client)}/jd"
    url = base + f"/{item_kind}s"
    initial = client.get(url).json()
    request = command(initial["revision_id"], create_change(item_kind))
    first = client.post(url, json=request)
    assert first.status_code == 200
    latest = edit(client, url, first.json()["revision_id"], create_change(item_kind, "後來的內容"))
    assert client.post(url, json=request).json() == first.json()
    assert client.get(url).json() == latest
    changed = client.post(url, json={**request, "change": create_change(item_kind, "不同命令內容")})
    assert changed.status_code == 409
    assert changed.json()["detail"]["code"] == "jd_command_conflict"
    other_command = {**request, "command_id": str(uuid4())}
    assert client.post(url, json=other_command).json()["detail"]["code"] == "jd_revision_stale"
    collision = client.post(
        base + "/profile",
        json={
            "command_id": request["command_id"],
            "expected_revision_id": initial["revision_id"],
            "changes": [{"action": "set_field", "field": "job_title", "value": "不應提交"}],
        },
    )
    assert collision.status_code == 409


def test_order_delete_noop_and_changed_back_content_have_precise_history(
    client: TestClient,
    database_connection: psycopg.Connection,
    item_kind: str,
) -> None:
    collection, id_field = item_kind + "s", item_kind + "_id"
    url = f"/api/job-files/{create_file(client)}/jd/{collection}"
    current = client.get(url).json()
    requests, results = [], []
    for text in ("甲", "乙", "丙"):
        request = command(current["revision_id"], create_change(item_kind, text))
        response = client.post(url, json=request)
        assert response.status_code == 200
        current = response.json()
        requests.append(request)
        results.append(current)
    first, second, third = [item[id_field] for item in current[collection]]
    reordered = edit(
        client,
        url,
        current["revision_id"],
        {
            "action": f"reorder_{item_kind}",
            id_field: third,
            f"before_{id_field}": first,
        },
    )
    assert [item[id_field] for item in reordered[collection]] == [third, first, second]
    noop = edit(
        client,
        url,
        reordered["revision_id"],
        {
            "action": f"reorder_{item_kind}",
            id_field: second,
            f"before_{id_field}": None,
        },
    )
    assert noop == reordered
    field = "name" if item_kind == "collaborator" else "text"
    revised = edit(
        client,
        url,
        noop["revision_id"],
        {
            "action": f"revise_{item_kind}",
            id_field: first,
            "changes": [{"field": field, "value": "新文字"}],
        },
    )
    restored = edit(
        client,
        url,
        revised["revision_id"],
        {
            "action": f"revise_{item_kind}",
            id_field: first,
            "changes": [{"field": field, "value": "甲"}],
        },
    )
    assert restored[collection] == reordered[collection]
    assert restored["revision_id"] != reordered["revision_id"]
    unchanged = edit(
        client,
        url,
        restored["revision_id"],
        {
            "action": f"revise_{item_kind}",
            id_field: first,
            "changes": [{"field": field, "value": "甲"}],
        },
    )
    assert unchanged == restored
    deleted = edit(
        client,
        url,
        unchanged["revision_id"],
        {
            "action": f"delete_{item_kind}",
            id_field: first,
        },
    )
    assert [item[id_field] for item in deleted[collection]] == [third, second]
    recreated = edit(client, url, deleted["revision_id"], create_change(item_kind, "甲"))
    assert recreated[collection][-1][id_field] != first
    for request, original in zip(requests, results, strict=True):
        assert client.post(url, json=request).json() == original
    count = database_connection.execute(
        sql.SQL("SELECT count(*) FROM {}").format(
            sql.Identifier(f"jd_{item_kind}_revisions"),
        )
    ).fetchone()
    assert count == (6,)  # Three creates, two text revisions, one new identity.


def test_conditions_order_within_kind_and_reclassification_retains_identity(
    client: TestClient,
) -> None:
    url = f"/api/job-files/{create_file(client)}/jd/conditions"
    current = client.get(url).json()
    for kind, text in (
        ("work_environment", "室內"),
        ("schedule_travel", "輪班"),
        ("work_environment", "必要時到現場"),
        ("schedule_travel", "短期出差"),
    ):
        current = edit(
            client,
            url,
            current["revision_id"],
            {
                "action": "create_condition",
                "kind": kind,
                "text": text,
            },
        )
    first, second, third, fourth = [item["condition_id"] for item in current["conditions"]]
    rejected = client.post(
        url,
        json=command(
            current["revision_id"],
            {
                "action": "reorder_condition",
                "condition_id": first,
                "before_condition_id": second,
            },
        ),
    )
    assert rejected.status_code == 404
    assert client.get(url).json() == current
    reordered = edit(
        client,
        url,
        current["revision_id"],
        {
            "action": "reorder_condition",
            "condition_id": third,
            "before_condition_id": first,
        },
    )
    assert [item["condition_id"] for item in reordered["conditions"]] == [
        third,
        second,
        first,
        fourth,
    ]
    revised = edit(
        client,
        url,
        reordered["revision_id"],
        {
            "action": "revise_condition",
            "condition_id": first,
            "changes": [
                {"field": "kind", "value": "schedule_travel"},
                {"field": "text", "value": "固定日班"},
            ],
        },
    )
    assert revised["conditions"][-1] == {
        "condition_id": first,
        "kind": "schedule_travel",
        "text": "固定日班",
    }
    assert [
        item["condition_id"] for item in revised["conditions"] if item["kind"] == "schedule_travel"
    ] == [second, fourth, first]


def test_foreign_or_missing_targets_are_rejected_without_changing_head(
    client: TestClient, item_kind: str
) -> None:
    collection, id_field = item_kind + "s", item_kind + "_id"
    url = f"/api/job-files/{create_file(client)}/jd/{collection}"
    other_url = f"/api/job-files/{create_file(client)}/jd/{collection}"
    own = edit(client, url, client.get(url).json()["revision_id"], create_change(item_kind))
    other = edit(
        client, other_url, client.get(other_url).json()["revision_id"], create_change(item_kind)
    )
    foreign_id = other[collection][0][id_field]
    for change in (
        {"action": f"delete_{item_kind}", id_field: foreign_id},
        {
            "action": f"revise_{item_kind}",
            id_field: foreign_id,
            "changes": [
                {"field": "name" if item_kind == "collaborator" else "text", "value": "不應改"}
            ],
        },
        {
            "action": f"reorder_{item_kind}",
            id_field: own[collection][0][id_field],
            f"before_{id_field}": foreign_id,
        },
    ):
        assert client.post(url, json=command(own["revision_id"], change)).status_code == 404
        assert client.get(url).json() == own
    missing_url = f"/api/job-files/{uuid4()}/jd/{collection}"
    assert client.get(missing_url).status_code == 404
    assert (
        client.post(
            missing_url, json=command(own["revision_id"], create_change(item_kind))
        ).status_code
        == 404
    )


@pytest.mark.parametrize("paused", [False, True])
def test_active_consultant_blocks_new_edits_but_not_replay(
    client: TestClient,
    item_kind: str,
    paused: bool,
) -> None:
    file_id = create_file(client)
    url = f"/api/job-files/{file_id}/jd/{item_kind}s"
    request = command(client.get(url).json()["revision_id"], create_change(item_kind))
    first = client.post(url, json=request)
    assert first.status_code == 200
    accepted = client.post(
        f"/api/job-files/{file_id}/inputs",
        json={
            "command_id": str(uuid4()),
            "text": "合成訪談",
        },
    )
    assert accepted.status_code == 202
    if paused:

        async def pause() -> None:
            scope = ExecutionScope(
                UUID(file_id), UUID(accepted.json()["execution_id"]), ExecutionKind.CONSULTANT_TURN
            )
            async with client.app.state.database.sessions.begin() as session:
                writer = await executions.claim_writer(session, scope, writer_id=uuid4())
                await executions.pause_execution(session, writer)

        client.portal.call(pause)
    blocked = client.post(url, json=command(first.json()["revision_id"], create_change(item_kind)))
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["code"] == "consultant_turn_active"
    assert client.post(url, json=request).json() == first.json()
    other_url = f"/api/job-files/{create_file(client)}/jd/{item_kind}s"
    assert (
        client.post(
            other_url,
            json=command(client.get(other_url).json()["revision_id"], create_change(item_kind)),
        ).status_code
        == 200
    )


def test_concurrent_replays_commit_once_and_competing_edits_do_not_overwrite(
    client: TestClient, item_kind: str
) -> None:
    url = f"/api/job-files/{create_file(client)}/jd/{item_kind}s"
    request = command(client.get(url).json()["revision_id"], create_change(item_kind))
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(lambda _: client.post(url, json=request), range(6)))
    assert all(result.status_code == 200 for result in results)
    assert all(result.json() == results[0].json() for result in results)
    revision_id = results[0].json()["revision_id"]
    with ThreadPoolExecutor(max_workers=2) as pool:
        competing = list(
            pool.map(
                lambda text: client.post(
                    url, json=command(revision_id, create_change(item_kind, text))
                ),
                ["甲", "乙"],
            )
        )
    assert sorted(result.status_code for result in competing) == [200, 409]
    assert len(client.get(url).json()[item_kind + "s"]) == 2


def test_failed_transaction_rolls_back_new_content_and_selections(
    client: TestClient,
    database_connection: psycopg.Connection,
    monkeypatch: pytest.MonkeyPatch,
    item_kind: str,
) -> None:
    original_insert = persistence.insert_revision

    async def fail_after_insert(
        session: AsyncSession, job_file_id: UUID, revision: JdProfileRevision, **kwargs: object
    ) -> None:
        await original_insert(session, job_file_id, revision, **kwargs)
        raise RuntimeError("Injected before adopting head")

    url = f"/api/job-files/{create_file(client)}/jd/{item_kind}s"
    initial = client.get(url).json()
    with monkeypatch.context() as patch:
        patch.setattr(persistence, "insert_revision", fail_after_insert)
        with pytest.raises(RuntimeError, match="Injected"):
            client.post(url, json=command(initial["revision_id"], create_change(item_kind)))
    assert client.get(url).json() == initial
    for table in (f"jd_{item_kind}_revisions", f"jd_{item_kind}_selections", "jd_operations"):
        assert database_connection.execute(
            sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(table))
        ).fetchone() == (0,)
